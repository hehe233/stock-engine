"""Response models validate contracts without rewriting missing/versioned evidence."""

from datetime import date

from fastapi.encoders import jsonable_encoder

from app.db import QuantRun
from app.quant.service import run_view
from app.research.history import history_list
from app.research.queries import dataset
from app.research.schemas import FetchRequest


def test_research_wire_response_matches_service_including_absent_columns(client, settings):
    query = FetchRequest(kind="ladder", date=date(2026, 1, 1))
    with client.app.state.sessions() as session:
        expected = jsonable_encoder(dataset(session, query, settings, page=2, page_size=10))
    response = client.get("/api/research/data?kind=ladder&date=2026-01-01&page=2&page_size=10")
    assert response.status_code == 200
    assert response.json() == expected
    assert response.json()["snapshot"] is None
    assert response.json()["summary"] == {}
    with client.app.state.sessions() as session:
        expected = jsonable_encoder(history_list(session, settings))
    assert client.get("/api/research/history").json() == expected


def test_quant_sparse_and_versioned_result_is_not_filled_or_filtered(client):
    dataset = client.post("/api/quant/datasets/demo").json()
    assert "snapshot_ids" not in dataset["details"]
    job = client.post("/api/quant/runs", json={"dataset_id": dataset["id"]}).json()
    assert job["result"] == {"dataset_checksum": dataset["checksum"]}
    with client.app.state.sessions() as session:
        row = session.get(QuantRun, job["id"])
        row.result = {
            "research_only": True,
            "future_version_evidence": {"source_time": None},
            "backtest": {"enabled": False, "return_pct": None, "reason": "unknown"},
        }
        session.commit()
        expected = jsonable_encoder(run_view(row, True))
    assert client.get(f"/api/quant/runs/{job['id']}").json() == expected


def test_portfolio_decimal_unknown_prices_and_source_times_preserved(client):
    content = (
        "symbol,name,asset_type,quantity,cost_price,acquired_on,settlement,note\n"
        "DEMO999,missing,stock,100,10.1234,2025-01-02,T1,test\n"
    )
    preview = client.post("/api/portfolio/preview", json={"content": content}).json()
    assert preview["rows"][0]["cost_price"] == "10.1234"
    assert client.post("/api/portfolio/import", json={"rows": preview["rows"]}).status_code == 200
    portfolio = client.get("/api/portfolio").json()
    row = next(row for row in portfolio["items"] if row["symbol"] == "DEMO999")
    assert row["cost_price"] == "10.1234"
    for field in (
        "price",
        "value_yuan",
        "pnl_yuan",
        "pnl_pct",
        "quote_time",
        "fetched_at",
        "weight_pct",
    ):
        assert row[field] is None
    assert portfolio["pnl_yuan"] is None
    assert "updated_at" in row and "calendar_verified" in portfolio["session"]


def test_openapi_has_domain_response_models(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path, model in [
        ("/api/research/data", "ResearchDatasetResponse"),
        ("/api/portfolio", "PortfolioResponse"),
        ("/api/quant/runs/{identifier}", "RunResponse"),
        ("/api/quant/runs/{identifier}/predictions", "PredictionPage"),
    ]:
        assert paths[path]["get"]["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/" + model)
