from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.agents.run_job import execute_job
from app.db import DataRequest, MarketSnapshot, PositionLot, ResearchJob, ResearchSnapshot
from app.main import create_app
from app.providers.base import ProviderError
from app.providers.research import normalize_research, safe_url
from app.research_schemas import PositionInput
from app.services.jobs import claim_job
from app.services.portfolio import sellable_quantity
from app.services.research_data import (
    frozen_context,
    history_statistics,
    process_one,
    recover_requests,
)
from app.shared.time import SHANGHAI, utc_now


def today():
    return utc_now().astimezone(SHANGHAI).date().isoformat()


def position(**updates):
    return {
        "symbol": "DEMO001",
        "name": "演示持仓",
        "asset_type": "stock",
        "quantity": 100,
        "cost_price": "10.0000",
        "acquired_on": today(),
        "settlement": "T1",
        "note": "",
        **updates,
    }


def test_research_snapshot_pagination_and_mode_isolation(client, settings):
    response = client.get(f"/api/research/data?kind=ladder&date={today()}&page_size=1").json()
    assert response["total"] == 2 and len(response["snapshot"]["rows"]) == 1
    assert response["summary"]["tiers"][0] == {"boards": 3, "count": 1}
    assert response["summary"]["leaders"] == ["DEMO001"]
    with TestClient(create_app(settings.model_copy(update={"market_provider": "public"}))) as other:
        data = other.get(f"/api/research/data?kind=ladder&date={today()}").json()
        assert data["snapshot"] is None


def test_durable_collection_deduplicates_and_saves_empty_as_unconfirmed(
    client, settings, monkeypatch
):
    query = {"kind": "seats", "date": today(), "symbol": "DEMO001"}
    job = client.post("/api/research/refresh", json=query).json()
    assert client.post("/api/research/refresh", json=query).json()["id"] == job["id"]
    process_one(client.app.state.sessions, settings)
    assert client.get(f"/api/research/requests/{job['id']}").json()["status"] == "succeeded"
    result = client.get(f"/api/research/data?kind=seats&date={today()}&symbol=DEMO001").json()
    assert result["snapshot"]["rows"][0]["seat"] == "演示营业部（虚构）"
    with client.app.state.sessions() as session:
        row = session.get(DataRequest, job["id"])
        row.status = "running"
        session.commit()
    recover_requests(client.app.state.sessions)
    assert client.get(f"/api/research/requests/{job['id']}").json()["status"] == "queued"


def test_failed_collection_preserves_last_success(client, settings, monkeypatch):
    from app.services import research_data

    first = client.get(f"/api/research/data?kind=ladder&date={today()}").json()["snapshot"]["id"]
    job = client.post("/api/research/refresh", json={"kind": "ladder", "date": today()}).json()

    def fail(*_):
        raise ProviderError("模拟限流")

    monkeypatch.setattr(research_data, "fetch_research", fail)
    process_one(client.app.state.sessions, settings)
    result = client.get(f"/api/research/data?kind=ladder&date={today()}").json()
    assert result["snapshot"]["id"] == first
    assert result["request"]["id"] == job["id"] and result["request"]["status"] == "failed"


def test_no_historical_current_flow_or_future_queries(client):
    assert client.get("/api/research/data?kind=flow&date=2020-01-01").status_code == 422
    assert (
        client.post(
            "/api/research/refresh", json={"kind": "dragon", "date": "2099-01-01"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/research/refresh", json={"kind": "history", "date": today(), "case_id": "missing"}
        ).status_code
        == 404
    )


def test_lhb_whitelist_excludes_future_returns_and_keeps_units():
    raw = [
        {
            "代码": "600000",
            "名称": "测试",
            "上榜日": "2026-10-30",
            "龙虎榜买入额": 12345678,
            "龙虎榜净买额": -100,
            "上榜后1日": 9.9,
        }
    ]
    rows, rejected = normalize_research("dragon", raw, {"date": "2026-10-30"})
    assert rejected == 0 and rows[0]["buy_yuan"] == 12345678
    assert rows[0]["net_yuan"] == -100 and "上榜后1日" not in str(rows)
    with pytest.raises(ProviderError):
        normalize_research("dragon", raw, {"date": "2026-10-29"})
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("https://data.eastmoney.com.evil.test/a") is None
    assert safe_url("https://data.eastmoney.com/notices/detail/a") is not None


def test_history_strict_range_and_descriptive_windows():
    rows, rejected = normalize_research(
        "history",
        [
            {"date": "2015-12-31", "close": 2},
            {"date": "2016-01-04", "close": 10},
            {"date": "2016-01-05", "close": 11},
            {"date": "2016-01-06", "close": 0},
        ],
        {"case_id": "2016-000935.SZ"},
    )
    assert len(rows) == 2 and rejected == 2
    # 21个收盘点才构成20个交易日收益，不把20个价格错当20段收益。
    series = [
        {
            "date": (date(2020, 1, 1) + timedelta(days=i)).isoformat(),
            "close": 100 + i if i <= 20 else 120 - (i - 20) * 3,
        }
        for i in range(41)
    ]
    stats = history_statistics(series)
    assert stats["window_count"] == 21
    assert stats["strong"]["return_pct"] == 20
    assert stats["failure"]["return_pct"] == -50
    assert stats["failure"]["drawdown_pct"] == -50
    assert history_statistics(series[:20])["window_count"] == 0


def test_ten_year_history_queue_and_failure_comparison(client, settings):
    cases = client.get("/api/research/history").json()["items"]
    assert [item["year"] for item in cases] == list(range(2016, 2026))
    assert all(item["statistics"] is None for item in cases)
    result = client.post(
        "/api/research/refresh",
        json={"kind": "history", "date": today(), "case_id": cases[0]["id"]},
    )
    assert result.status_code == 202
    process_one(client.app.state.sessions, settings)
    first = client.get("/api/research/history").json()["items"][0]
    assert first["statistics"]["strong"]["return_pct"] > 0
    assert first["statistics"]["failure"]["return_pct"] < 0
    assert first["snapshot"]["is_demo"]


def test_csv_preview_atomic_import_duplicates_and_crud(client):
    content = (
        "symbol,name,asset_type,quantity,cost_price,acquired_on,settlement,note\n"
        + f"DEMO001,测试,stock,100,10,{today()},T1,\n"
    )
    preview = client.post("/api/portfolio/preview", json={"content": content}).json()
    assert preview["valid"] and preview["count"] == 1
    assert client.post("/api/portfolio/import", json={"rows": preview["rows"]}).json() == {
        "inserted": 1,
        "skipped": 0,
    }
    assert client.post("/api/portfolio/import", json={"rows": preview["rows"]}).json() == {
        "inserted": 0,
        "skipped": 1,
    }
    bad = client.post(
        "/api/portfolio/preview", json={"content": content.replace(",100,", ",-1,")}
    ).json()
    assert not bad["valid"] and bad["errors"][0]["line"] == 2
    assert (
        client.post(
            "/api/portfolio/import", json={"rows": [position(quantity=200), position(quantity=-1)]}
        ).status_code
        == 422
    )
    data = client.get("/api/portfolio").json()
    assert len(data["items"]) == 1 and data["items"][0]["sellable"] == 0
    assert data["items"][0]["pnl_yuan"] == pytest.approx(862)
    lot_id = data["items"][0]["id"]
    assert (
        client.post(f"/api/portfolio/{lot_id}/update", json=position(quantity=200)).status_code
        == 200
    )
    assert client.get("/api/portfolio").json()["items"][0]["quantity"] == 200
    assert client.post(f"/api/portfolio/{lot_id}/delete").status_code == 200
    assert client.get("/api/portfolio").json()["items"] == []


def test_settlement_calendar_unknown_and_etf_rules():
    lot = PositionInput.model_validate(position(acquired_on="2026-10-30"))
    assert sellable_quantity(lot, date(2026, 11, 2), [])[0] is None
    assert sellable_quantity(lot, date(2026, 11, 2), ["2026-10-30", "2026-11-02"])[0] == 100
    etf = {**position(symbol="510300.SH", asset_type="etf")}
    del etf["settlement"]
    unknown = PositionInput.model_validate(etf)
    assert unknown.settlement == "unknown"
    assert sellable_quantity(unknown, date.fromisoformat(today()), [])[0] is None
    with pytest.raises(ValidationError):
        PositionInput.model_validate(position(settlement="T0"))


def test_missing_prices_do_not_create_fake_portfolio_loss(client):
    client.post("/api/portfolio/import", json={"rows": [position(symbol="DEMONOTFOUND")]})
    result = client.get("/api/portfolio").json()
    assert result["unknown_price_count"] == 1 and result["pnl_yuan"] is None
    assert result["items"][0]["value_yuan"] is None


def test_job_freezes_research_and_opt_in_holdings(client, settings):
    client.post("/api/portfolio/import", json={"rows": [position()]})
    market = client.get("/api/market/quotes").json()
    payload = {"symbol": "DEMO001", "snapshot_id": market["snapshot_id"]}
    ordinary = client.post("/api/jobs", json=payload).json()
    included = client.post("/api/jobs", json={**payload, "include_portfolio": True}).json()
    with client.app.state.sessions() as session:
        first = session.get(ResearchJob, ordinary["id"])
        second = session.get(ResearchJob, included["id"])
        assert "portfolio" not in first.context
        assert second.context["portfolio"]["items"][0]["quantity"] == 100
        assert second.context["ladder"]["rows"][0]["boards"] == 3
        lot = session.scalar(select(PositionLot))
        lot.quantity = 999
        pool = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.kind == "ladder"))
        pool.rows = []
        session.commit()
    for _ in range(2):
        execute_job(
            client.app.state.sessions, settings, *claim_job(client.app.state.sessions, settings)
        )
    report = client.get(f"/api/analyses/{included['id']}").json()
    assert report["research_context"]["portfolio"]["items"][0]["quantity"] == 100
    assert report["research_context"]["ladder"]["rows"][0]["boards"] == 3


def test_evidence_cutoff_excludes_later_observation(client):
    with client.app.state.sessions() as session:
        now = utc_now()
        for row in session.scalars(select(ResearchSnapshot)).all():
            row.observed_at = now + timedelta(minutes=1)
        session.commit()
        context = frozen_context(session, "DEMO001", "demo", now, date.fromisoformat(today()))
    assert context["ladder"]["available"] is False


def test_public_portfolio_cannot_see_demo_lots(client, settings):
    client.post("/api/portfolio/import", json={"rows": [position()]})
    with TestClient(create_app(settings.model_copy(update={"market_provider": "public"}))) as other:
        assert other.get("/api/portfolio").json()["items"] == []
        assert other.post("/api/portfolio/import", json={"rows": [position()]}).status_code == 422


def test_flow_delta_requires_matching_source_and_previous_observation(client):
    url = f"/api/research/data?kind=flow&date={today()}"
    assert client.get(url).json()["snapshot"]["rows"][0]["change_since_previous_yuan"] is None
    with client.app.state.sessions() as session:
        current = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.kind == "flow"))
        session.add(
            ResearchSnapshot(
                id="prior-flow",
                key=current.key,
                kind="flow",
                mode="demo",
                query_date=current.query_date,
                source=current.source,
                observed_at=current.observed_at - timedelta(minutes=5),
                rows=[{"symbol": "DEMO001", "main_yuan": 40000000}],
                details={},
            )
        )
        session.commit()
    assert client.get(url).json()["snapshot"]["rows"][0]["change_since_previous_yuan"] == 10000000
    with client.app.state.sessions() as session:
        session.get(ResearchSnapshot, "prior-flow").source = "another-provider"
        session.commit()
    assert client.get(url).json()["snapshot"]["rows"][0]["change_since_previous_yuan"] is None


def test_sector_comparison_and_invalid_board_counts(client):
    with client.app.state.sessions() as session:
        current = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.kind == "ladder"))
        session.add(
            ResearchSnapshot(
                id="prior-ladder",
                key="prior-ladder",
                kind="ladder",
                mode="demo",
                query_date=current.query_date - timedelta(days=1),
                source=current.source,
                observed_at=current.observed_at - timedelta(days=1),
                rows=[{"sector": "演示算力"}, {"sector": "演示算力"}],
                details={},
            )
        )
        session.commit()
    summary = client.get(f"/api/research/data?kind=ladder&date={today()}").json()["summary"]
    assert summary["sectors"][0]["count_change"] == -1
    assert summary["sectors"][1]["count_change"] == 1
    for boards in (-1, 0, 1.5):
        with pytest.raises(ProviderError):
            normalize_research("ladder", [{"代码": "600000", "连板数": boards}], {})


def test_job_evidence_uses_individual_quote_day(client):
    market = client.get("/api/market/quotes").json()
    with client.app.state.sessions() as session:
        snapshot = session.get(MarketSnapshot, market["snapshot_id"])
        old = (utc_now() - timedelta(days=2)).isoformat()
        snapshot.quotes = [
            {**q, "quote_time": old} if q["symbol"] == "DEMO001" else q for q in snapshot.quotes
        ]
        session.commit()
    job = client.post(
        "/api/jobs", json={"symbol": "DEMO001", "snapshot_id": market["snapshot_id"]}
    ).json()
    with client.app.state.sessions() as session:
        assert session.get(ResearchJob, job["id"]).context["ladder"]["available"] is False


def test_concentration_aggregates_same_security_lots(client):
    client.post("/api/portfolio/import", json={"rows": [position(), position(quantity=200)]})
    items = client.get("/api/portfolio").json()["items"]
    assert len(items) == 2
    assert all(item["weight_pct"] == 100 for item in items)


def test_holding_analysis_keeps_whole_book_weight_but_only_selected_details(client):
    client.post("/api/portfolio/import", json={"rows": [position(), position(symbol="DEMO002")]})
    whole = client.get("/api/portfolio").json()
    expected = next(item for item in whole["items"] if item["symbol"] == "DEMO001")
    market = client.get("/api/market/quotes").json()
    job = client.post(
        "/api/jobs",
        json={"symbol": "DEMO001", "snapshot_id": market["snapshot_id"], "include_portfolio": True},
    ).json()
    with client.app.state.sessions() as session:
        context = session.get(ResearchJob, job["id"]).context["portfolio"]
    assert len(context["items"]) == 1
    assert context["items"][0]["weight_pct"] == expected["weight_pct"] < 100
    assert context["cost_yuan"] == 1000


def test_frozen_seats_belong_to_target_security(client, settings):
    for symbol in ("DEMO001", "DEMO002"):
        client.post(
            "/api/research/refresh", json={"kind": "seats", "date": today(), "symbol": symbol}
        )
        process_one(client.app.state.sessions, settings)
    with client.app.state.sessions() as session:
        context = frozen_context(session, "DEMO001", "demo", utc_now(), date.fromisoformat(today()))
    assert context["seats"]["rows"][0]["symbol"] == "DEMO001"
