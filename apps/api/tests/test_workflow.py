from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.agents.research import build_research_graph
from app.db import AnalysisRun, MarketSnapshot
from app.main import create_app
from app.providers.base import QuoteBatch
from app.services.market import MarketService
from app.shared.time import utc_now


def analyze_first(client):
    market = client.get("/api/market/quotes").json()
    response = client.post(
        "/api/analyses",
        json={"symbol": market["quotes"][0]["symbol"], "snapshot_id": market["snapshot_id"]},
    )
    assert response.status_code == 201
    return market, response.json()


def test_complete_workflow_and_history(client):
    assert client.get("/api/health").json()["status"] == "ok"
    market, report = analyze_first(client)
    assert market["is_demo"] is True
    assert market["stale"] is False
    assert market["refresh_interval_seconds"] == 300
    assert report["snapshot_id"] == market["snapshot_id"]
    assert report["heat_score"] == 91.94
    assert report["analysis_mode"] == "rules"
    assert [step["node"] for step in report["trace"]] == ["validate", "factors", "risk", "report"]
    assert client.get(f"/api/analyses/{report['id']}").json() == report
    history = client.get("/api/analyses").json()
    assert history["total"] == 1
    assert history["items"][0] == report
    assert client.get("/api/analyses?offset=1").json()["items"] == []


def test_refresh_preserves_original_analysis_and_market_time(client):
    market, report = analyze_first(client)
    assert client.post("/api/market/refresh").status_code == 202
    refreshed = client.app.state.market.refresh().model_dump(mode="json")
    assert refreshed["snapshot_id"] != market["snapshot_id"]
    assert refreshed["as_of"] == market["as_of"]
    assert refreshed["fetched_at"] >= market["fetched_at"]
    assert client.get(f"/api/analyses/{report['id']}").json() == report
    # 即使系统已经刷新，前端看到的旧快照仍然可以被准确分析。
    response = client.post(
        "/api/analyses", json={"symbol": "DEMO001", "snapshot_id": market["snapshot_id"]}
    )
    assert response.json()["snapshot_id"] == market["snapshot_id"]


def test_history_survives_application_restart(client, settings):
    _, report = analyze_first(client)
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/api/analyses/{report['id']}").json() == report


def test_unknown_symbol_and_snapshot_never_create_reports(client):
    market = client.get("/api/market/quotes").json()
    assert (
        client.post(
            "/api/analyses", json={"symbol": "MISSING", "snapshot_id": market["snapshot_id"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/analyses", json={"symbol": "DEMO001", "snapshot_id": str(uuid4())}
        ).status_code
        == 404
    )
    with client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 0


@pytest.mark.parametrize(
    "url", ["/api/analyses?limit=0", "/api/analyses?limit=101", "/api/analyses?offset=-1"]
)
def test_invalid_pagination_is_rejected(client, url):
    assert client.get(url).status_code == 422


def test_stale_snapshot_is_visible(client):
    market = client.get("/api/market/quotes").json()
    with client.app.state.sessions() as session:
        snapshot = session.get(MarketSnapshot, market["snapshot_id"])
        snapshot.fetched_at = utc_now() - timedelta(minutes=11)
        session.commit()
    assert client.get("/api/market/quotes").json()["stale"] is True


def test_empty_provider_does_not_replace_valid_snapshot(client):
    class EmptyProvider:
        def fetch_quotes(self, asset_type="stock"):
            return QuoteBatch(source="demo", as_of=utc_now(), quotes=[])

    before = client.get("/api/market/quotes").json()
    service = MarketService(client.app.state.sessions, EmptyProvider(), 300)
    with pytest.raises(ValueError, match="空数据"):
        service.refresh()
    assert client.get("/api/market/quotes").json()["snapshot_id"] == before["snapshot_id"]


def test_invalid_quote_cannot_be_scored(client):
    quote = client.get("/api/market/quotes").json()["quotes"][0]
    quote["price"] = float("nan")
    with pytest.raises(ValidationError):
        build_research_graph().invoke({"quote": quote, "trace": []})


def test_score_is_bounded_and_negative_change_has_no_strength_points(client):
    quote = client.get("/api/market/quotes").json()["quotes"][0]
    quote.update(change_pct=-10, turnover_pct=100, volume_ratio=100, amount_yuan=1e15)
    result = build_research_graph().invoke({"quote": quote, "trace": []})
    assert result["heat_score"] == 70
    assert result["factors"][0]["points"] == 0


def test_worker_collection_without_browser_request(client, settings):
    from app.worker import collect_market

    first = client.get("/api/market/quotes").json()["snapshot_id"]
    collect_market(client.app.state.sessions, settings, client.app.state.market)
    assert client.get("/api/market/quotes").json()["snapshot_id"] != first
    for asset in ("stock", "etf", "index"):
        result = client.get(f"/api/market/quotes?asset_type={asset}")
        assert result.status_code == 200
        assert result.json()["asset_type"] == asset
