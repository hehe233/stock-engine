import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk
from pydantic import SecretStr, ValidationError
from sqlalchemy import func, select

from app.agents.assistant import build_assistant_graph
from app.agents.research import build_research_graph
from app.agents.run_job import execute_job
from app.core.config import Settings
from app.db import AnalysisRun, ResearchJob
from app.main import create_app
from app.providers.base import ProviderError
from app.providers.normalization import source_time
from app.providers.public import normalize_rows
from app.schemas import ModelInsight
from app.services.calendar import market_session
from app.services.jobs import claim_job, recover_expired_jobs
from app.shared.securities import normalize_symbol
from app.shared.time import utc_now


def submit(client, mode="rules", **kwargs):
    market = client.get("/api/market/quotes").json()
    return client.post(
        "/api/jobs",
        json={"symbol": "DEMO001", "snapshot_id": market["snapshot_id"], "mode": mode, **kwargs},
    )


def test_job_lifecycle_events_and_idempotent_report(client, settings):
    job = submit(client).json()
    assert job["status"] == "queued"
    claimed = claim_job(client.app.state.sessions, settings)
    assert claimed[0] == job["id"]
    assert claim_job(client.app.state.sessions, settings) is None
    execute_job(client.app.state.sessions, settings, *claimed)
    response = client.get(f"/api/jobs/{job['id']}").json()
    assert response["status"] == "succeeded"
    report = client.get(f"/api/analyses/{response['report_id']}").json()
    assert report["heat_score"] == 91.94
    execute_job(client.app.state.sessions, settings, *claimed)
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 1
    stream = client.get(f"/api/jobs/{job['id']}/events")
    assert stream.status_code == 200
    assert "event: progress" in stream.text
    assert "event: done" in stream.text
    assert '"node":"factors"' in stream.text
    last = max(int(line[4:]) for line in stream.text.splitlines() if line.startswith("id: "))
    resumed = client.get(f"/api/jobs/{job['id']}/events", headers={"Last-Event-ID": str(last)})
    assert "event: progress" not in resumed.text
    assert "event: done" in resumed.text


def test_cancel_and_retry_limits(client, settings):
    job = submit(client).json()
    assert client.post(f"/api/jobs/{job['id']}/cancel").json()["status"] == "cancelled"
    assert claim_job(client.app.state.sessions, settings) is None
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409


def test_expired_lease_recovers_from_database(client, settings):
    job = submit(client).json()
    claim_job(client.app.state.sessions, settings)
    with client.app.state.sessions() as session:
        row = session.get(ResearchJob, job["id"])
        row.lease_until = utc_now() - timedelta(seconds=1)
        session.commit()
    recover_expired_jobs(client.app.state.sessions, settings.job_max_attempts)
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "queued"
    claimed = claim_job(client.app.state.sessions, settings)
    execute_job(client.app.state.sessions, settings, *claimed)
    assert client.get(f"/api/jobs/{job['id']}").json()["attempts"] == 2


class FakeModel:
    """模拟模型协议，不访问外网，用于验证真实图的工具循环与检查点恢复。"""

    def __init__(self, fail_once=False, bad_reference=False):
        self.calls = 0
        self.final_calls = 0
        self.fail_once = fail_once
        self.bad_reference = bad_reference

    def bind_tools(self, tools, **kwargs):
        if kwargs.get("tool_choice"):
            outer = self

            class FinalStream:
                def stream(self, messages):
                    insight = outer.with_structured_output(ModelInsight, "function_calling").invoke(
                        messages
                    )
                    yield AIMessageChunk(
                        content="",
                        tool_call_chunks=[
                            {
                                "id": "report",
                                "index": 0,
                                "name": "ModelInsight",
                                "args": json.dumps(insight.model_dump(), ensure_ascii=False),
                            }
                        ],
                    )

            return FinalStream()
        return self

    def stream(self, messages):
        response = self.invoke(messages)
        yield AIMessageChunk(content=response.content, tool_calls=response.tool_calls)

    def invoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[
                    {"id": str(uuid4()), "name": name, "args": {}}
                    for name in ("read_quote", "read_factors", "read_risks")
                ],
            )
        return AIMessage(content="证据已足够")

    def with_structured_output(self, schema, method):
        outer = self

        class Structured:
            def invoke(self, messages):
                outer.final_calls += 1
                if outer.fail_once and outer.final_calls == 1:
                    raise TimeoutError("simulated provider timeout")
                return ModelInsight(
                    summary="样本活跃，存在数据局限。",
                    observations=[
                        {
                            "text": "依据规则因子判断活跃程度。",
                            "evidence_ids": ["fake" if outer.bad_reference else "read_factors"],
                        }
                    ],
                    limitations=["不能推断连板概率"],
                )

        return Structured()


def test_graph_rejects_fabricated_reference(client):
    quote = client.get("/api/market/quotes").json()["quotes"][0]
    with pytest.raises(ValueError, match="不存在的证据"):
        build_assistant_graph(FakeModel(bad_reference=True)).invoke(
            {
                "quote": quote,
                "source": "demo",
                "is_demo": True,
                "trace": [],
            }
        )


def test_model_checkpoint_resume_does_not_replay_completed_tool_nodes(client, settings):
    job = submit(client, mode="ollama").json()
    claimed = claim_job(client.app.state.sessions, settings)
    model = FakeModel(fail_once=True)
    with pytest.raises(TimeoutError):
        execute_job(client.app.state.sessions, settings, *claimed, model_factory=lambda *_: model)
    calls_before = model.calls
    execute_job(client.app.state.sessions, settings, *claimed, model_factory=lambda *_: model)
    assert model.calls == calls_before
    assert model.final_calls == 2
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    report = client.get(f"/api/analyses/{job['id']}").json()
    assert report["evidence"]["read_quote"]["quote"]["symbol"] == "DEMO001"


def test_unconfigured_api_and_disallowed_model_are_rejected(client):
    assert submit(client, mode="api", model_name="unknown").status_code == 409
    assert submit(client, mode="ollama", model_name="arbitrary").status_code == 422


def test_missing_values_and_non_stock_do_not_get_score(client):
    quote = client.get("/api/market/quotes").json()["quotes"][0]
    quote["volume_ratio"] = None
    result = build_research_graph().invoke({"quote": quote, "trace": []})
    assert result["heat_score"] is None
    assert result["factors"][2]["points"] is None
    quote["volume_ratio"], quote["asset_type"] = 3, "etf"
    assert build_research_graph().invoke({"quote": quote, "trace": []})["heat_score"] is None


def test_normalization_preserves_unknown_time_and_missing_price():
    rows = [
        {
            "代码": "920001",
            "名称": "测试证券",
            "最新价": "-",
            "涨跌幅": None,
            "成交额": 12345,
            "更新时间": "15:00:00",
        },
        {"代码": "bad", "名称": "无效"},
    ]
    quotes, rejected = normalize_rows(rows, "stock")
    assert quotes[0].symbol == "920001.BJ"
    assert quotes[0].price is None and quotes[0].quote_time is None
    assert quotes[0].amount_yuan == 12345
    assert rejected == 1
    assert normalize_symbol("sh000001", "index") == "000001.SH"
    assert normalize_symbol("000001", "stock") == "000001.SZ"
    assert source_time("2026-10-30 15:00:00") == datetime(2026, 10, 30, 7, tzinfo=UTC)


def test_calendar_does_not_guess_holidays():
    assert market_session(datetime(2026, 11, 2, 2, tzinfo=UTC), ["2025-12-31"])["code"] == "unknown"
    dates = ["2026-11-02", "2026-11-03"]
    assert market_session(datetime(2026, 11, 2, 2, tzinfo=UTC), dates)["code"] == "trading"
    assert market_session(datetime(2026, 11, 2, 4, tzinfo=UTC), dates)["code"] == "break"


def test_public_mode_never_displays_old_demo_snapshot(client, settings):
    public = settings.model_copy(update={"market_provider": "public"})
    with TestClient(create_app(public)) as other:
        assert other.get("/api/market/quotes").status_code == 503
        assert other.get("/api/health").status_code == 200


def test_auth_and_secrets_are_not_exposed(settings):
    key = "application-secret-not-model-key-123456789"
    secured = settings.model_copy(
        update={
            "app_api_key": SecretStr(key),
            "llm_api_key": SecretStr("private-model-key"),
            "llm_model": "model-a",
            "llm_models": ["model-b"],
        }
    )
    with TestClient(create_app(secured)) as client:
        assert client.get("/api/config").status_code == 401
        assert client.post("/api/auth/login", json={"key": "bad"}).status_code == 401
        assert client.post("/api/auth/login", json={"key": "错误密钥"}).status_code == 401
        response = client.post("/api/auth/login", json={"key": key})
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        config = client.get("/api/config")
        assert config.json()["api_models"] == ["model-a", "model-b"]
        assert "private-model-key" not in config.text and key not in config.text
        assert (
            client.post(
                "/api/market/refresh", headers={"Origin": "https://untrusted.test"}
            ).status_code
            == 403
        )
        assert client.post("/api/auth/logout").status_code == 200
        assert client.get("/api/config").status_code == 401


def test_market_search_pagination_and_refresh_limit(client):
    result = client.get("/api/market/quotes?search=DEMO001&page_size=1").json()
    assert result["total"] == 1 and len(result["quotes"]) == 1
    assert result["universe_count"] == 8
    assert client.post("/api/market/refresh").status_code == 202
    assert client.post("/api/market/refresh").status_code == 429
    assert client.get("/api/market/quotes?page_size=101").status_code == 422


def test_public_provider_records_failover(monkeypatch):
    from app.providers import public

    calls = []

    def collect(asset, source, timeout):
        calls.append(source)
        if source == "eastmoney":
            raise ProviderError("primary unavailable")
        return {"rows": [{"代码": "sh600000", "名称": "测试", "最新价": 10}]}

    monkeypatch.setattr(public, "run_collector", collect)
    batch = public.PublicQuoteProvider().fetch_quotes()
    assert calls == ["eastmoney", "sina"]
    assert batch.source == "akshare:sina"
    assert batch.as_of is None
    assert batch.details["warnings"]


def test_production_requires_auth_and_public_polling_has_floor():
    with pytest.raises(ValidationError):
        Settings(app_environment="production", app_api_key=None)
    with pytest.raises(ValidationError):
        Settings(market_provider="public", refresh_interval_seconds=10)


def test_foreign_key_prevents_orphan_report(client):
    from sqlalchemy.exc import IntegrityError

    with client.app.state.sessions() as session:
        session.add(
            AnalysisRun(
                id=str(uuid4()),
                snapshot_id=str(uuid4()),
                symbol="DEMO001",
                created_at=utc_now(),
                report={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_blank_credentials_disable_optional_services():
    settings = Settings(
        _env_file=None, llm_api_key=" ", app_api_key="", app_environment="development"
    )
    assert settings.llm_api_key is None and settings.app_api_key is None


def test_retry_cannot_bypass_queue_capacity(client, settings):
    from app.services.jobs import finish_failed

    settings.max_pending_jobs = 1
    first = submit(client).json()
    assert submit(client).status_code == 429
    claimed = claim_job(client.app.state.sessions, settings)
    finish_failed(client.app.state.sessions, *claimed, "模拟失败")
    second = submit(client).json()
    assert client.post(f"/api/jobs/{first['id']}/retry").status_code == 429
    assert client.post(f"/api/jobs/{second['id']}/cancel").status_code == 200
    assert client.post(f"/api/jobs/{first['id']}/retry").json()["status"] == "queued"


def test_report_never_borrows_another_quotes_source_time(client, settings):
    from app.db import MarketSnapshot

    market = client.get("/api/market/quotes").json()
    with client.app.state.sessions() as session:
        row = session.get(MarketSnapshot, market["snapshot_id"])
        row.source = "akshare:sina"
        row.quotes = [{**quote, "quote_time": None} for quote in row.quotes]
        # 批次有时间，目标个股无时间：报告不可借用别的记录或采集时间。
        session.commit()
    payload = {"symbol": "DEMO001", "snapshot_id": market["snapshot_id"]}
    assert client.post("/api/analyses", json=payload).json()["as_of"] is None
    job = client.post("/api/jobs", json=payload).json()
    execute_job(
        client.app.state.sessions, settings, *claim_job(client.app.state.sessions, settings)
    )
    assert client.get(f"/api/analyses/{job['id']}").json()["as_of"] is None
