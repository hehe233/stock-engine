import hashlib
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.db import QuantRun
from app.jobs.context import frozen_context
from app.main import create_app
from app.quant.backtest import simulate
from app.quant.data import artifact_path, demo_frame, parse_csv
from app.quant.features import FEATURES, build_features, time_folds
from app.quant.schemas import ExperimentInput
from app.quant.service import claim_experiment, execute_experiment, recover_experiments
from app.shared.time import utc_now


@pytest.fixture
def bars():
    return demo_frame()


def params(**updates):
    return ExperimentInput(dataset_id="test", **updates)


def test_features_do_not_read_future_and_label_is_exact_horizon(bars):
    first = build_features(bars)
    day = sorted(bars.date.unique())[100]
    altered = bars.copy()
    altered.loc[altered.date > day, "close"] *= 2
    second = build_features(altered)
    pd.testing.assert_frame_equal(
        first.loc[first.date <= day, FEATURES], second.loc[second.date <= day, FEATURES]
    )
    sample = first[(first.symbol == "DEMOQ000") & (first.date == day)].iloc[0]
    group = bars[bars.symbol == "DEMOQ000"].reset_index(drop=True)
    assert sample.future_return == pytest.approx(group.iloc[105].close / group.iloc[100].close - 1)


def test_split_purges_labels_and_keeps_dates_together(bars):
    frame = build_features(bars)
    sample = frame[frame.feature_valid & frame.label_valid]
    seen = set()
    for _, train, calibration, test in time_folds(sample, params()):
        assert train.label_end.max() < calibration.date.min()
        assert calibration.label_end.max() < test.date.min()
        assert not seen.intersection(test.date.unique())
        seen.update(test.date.unique())
        assert set(test.groupby("date").size()) == {8}


def test_missing_sessions_and_late_historical_data_are_excluded(bars):
    day = sorted(bars.date.unique())[100]
    changed = bars.copy()
    changed.loc[(changed.symbol == "DEMOQ000") & (changed.date == day), "available_at"] = (
        pd.Timestamp("2030-01-01", tz="UTC")
    )
    features = build_features(changed)
    assert (
        not features[(features.symbol == "DEMOQ000") & (features.date >= day)]
        .head(21)
        .feature_valid.any()
    )
    missing = bars[~((bars.symbol == "DEMOQ000") & (bars.date == day))]
    features = build_features(missing)
    before = features[(features.symbol == "DEMOQ000") & (features.date < day)].tail(1).iloc[0]
    assert not before.label_valid


def test_corporate_action_and_late_labels_cannot_leak_into_training(bars):
    changed = bars.copy()
    day = sorted(bars.date.unique())[100]
    changed.loc[(changed.symbol == "DEMOQ000") & (changed.date == day), "prev_close"] *= 0.5
    frame = build_features(changed)
    assert not frame[(frame.symbol == "DEMOQ000") & (frame.date < day)].tail(1).label_valid.iloc[0]
    assert not frame[(frame.symbol == "DEMOQ000") & (frame.date == day)].feature_valid.iloc[0]
    samples = frame[frame.feature_valid & frame.label_valid].copy()
    samples["label_available_at"] = pd.Timestamp("2030-01-01", tz="UTC")
    for _, train, calibration, _ in time_folds(samples, params()):
        assert train.empty and calibration.empty


def test_csv_rejects_duplicates_nonfinite_and_missing_prices(bars):
    data = bars.head(100)
    for frame in [pd.concat([data, data]), data.assign(close=float("inf")), data.assign(high=0)]:
        with pytest.raises(Exception) as exc:
            parse_csv(frame.to_csv(index=False), "demo")
        assert exc.value.status_code == 422


def simple_bars(bars):
    frame = bars[bars.symbol == "DEMOQ000"].head(15).copy()
    for key in ("open", "close", "prev_close"):
        frame[key] = 10.0
    frame["high"], frame["low"] = 10.5, 9.5
    frame["upper_limit"], frame["lower_limit"] = 11.0, 9.0
    return frame


def signal(frame):
    return pd.DataFrame([{"date": frame.iloc[0].date, "symbol": "DEMOQ000", "probability": 0.9}])


def test_backtest_next_open_t1_lots_costs_and_tax(bars):
    frame = simple_bars(bars)
    result = simulate(frame, signal(frame), params(max_positions=1), "raw")
    assert result["trade_count"] == 1
    trade = result["trades"][0]
    assert trade["buy_date"] == frame.iloc[1].date
    assert trade["sell_date"] == frame.iloc[6].date
    assert trade["quantity"] % 100 == 0
    assert trade["fees"] > 0 and trade["net_pnl"] < 0
    assert min(point["cash"] for point in result["curve"]) >= 0
    assert result["return_pct"] < 0


def test_limit_up_and_unknown_rules_never_fill(bars):
    frame = simple_bars(bars)
    frame.loc[frame.index[1], "upper_limit"] = 10
    result = simulate(frame, signal(frame), params(), "raw")
    assert result["trade_count"] == 0 and result["rejected"]["limit_up"] == 1
    frame["upper_limit"] = None
    assert simulate(frame, signal(frame), params(), "raw")["rejected"]["unknown_trading_rules"] == 1
    assert not simulate(frame, signal(frame), params(), "qfq")["enabled"]


def test_blocked_exit_remains_open_and_corporate_action_invalidates_return(bars):
    frame = simple_bars(bars)
    frame.loc[frame.index[6:], "lower_limit"] = 10
    result = simulate(frame, signal(frame), params(), "raw")
    assert result["trade_count"] == 0 and len(result["open_positions"]) == 1
    assert result["rejected"]["limit_down"] > 0
    frame.loc[frame.index[3], "prev_close"] = 9
    result = simulate(frame, signal(frame), params(), "raw")
    assert result["return_pct"] is None and not result["valuation_complete"]


def test_experiment_full_pipeline_persistence_artifacts_and_mode_isolation(client, settings):
    dataset = client.post("/api/quant/datasets/demo").json()
    assert dataset["is_demo"] and dataset["details"]["rows"] == 4960
    job = client.post("/api/quant/runs", json={"dataset_id": dataset["id"]}).json()
    identifier = claim_experiment(client.app.state.sessions, settings)
    assert identifier == job["id"]
    execute_experiment(client.app.state.sessions, settings, identifier)
    report = client.get(f"/api/quant/runs/{identifier}").json()
    assert report["status"] == "succeeded", report["error"]
    result = report["result"]
    assert len(result["folds"]) == 3
    assert 0 <= result["metrics"]["brier"] <= 1
    assert result["research_only"] and result["dataset_checksum"] == dataset["checksum"]
    assert result["backtest"]["trade_count"] > 0
    with client.app.state.sessions() as session:
        context = frozen_context(session, "DEMOQ000", "demo", utc_now(), date(2026, 1, 1))
    assert context["quant"]["experiment_id"] == identifier
    assert context["quant"]["research_only"]
    with client.app.state.sessions() as session:
        before_outcome = frozen_context(
            session,
            "DEMOQ000",
            "demo",
            utc_now(),
            date.fromisoformat(result["folds"][-1]["test_end"]),
        )
    assert "quant" not in before_outcome
    predictions = client.get(f"/api/quant/runs/{identifier}/predictions").json()
    assert len(predictions["items"]) == 50
    artifact = client.get(f"/api/quant/runs/{identifier}/artifacts/models.json")
    assert hashlib.sha256(artifact.content).hexdigest() == result["artifacts"]["models.json"]
    with TestClient(create_app(settings.model_copy(update={"market_provider": "public"}))) as other:
        assert other.get("/api/quant/datasets").json()["items"] == []
        assert other.get(f"/api/quant/runs/{identifier}").status_code == 404
        assert other.post("/api/quant/datasets/demo").status_code == 409


def test_hash_change_rejected_and_interruption_recoverable(client, settings):
    dataset = client.post("/api/quant/datasets/demo").json()
    job = client.post("/api/quant/runs", json={"dataset_id": dataset["id"]}).json()
    identifier = claim_experiment(client.app.state.sessions, settings)
    path = artifact_path(settings, "demo", dataset["id"], "bars.parquet")
    path.write_bytes(path.read_bytes() + b"corrupted")
    execute_experiment(client.app.state.sessions, settings, identifier)
    assert client.get(f"/api/quant/runs/{identifier}").json()["status"] == "failed"
    with client.app.state.sessions() as session:
        row = session.get(QuantRun, job["id"])
        row.status = "running"
        session.commit()
    recover_experiments(client.app.state.sessions)
    assert "中断" in client.get(f"/api/quant/runs/{identifier}").json()["error"]


def test_queued_cancel_and_insufficient_data_fail_clearly(client, settings, bars):
    frame = bars[bars.symbol == "DEMOQ000"].head(50)
    result = client.post(
        "/api/quant/datasets",
        json={"name": "small", "source": "test", "content": frame.to_csv(index=False)},
    )
    assert result.status_code == 201
    payload = {"dataset_id": result.json()["id"]}
    job = client.post("/api/quant/runs", json=payload).json()
    assert client.post(f"/api/quant/runs/{job['id']}/cancel").json()["status"] == "cancelled"
    job = client.post("/api/quant/runs", json=payload).json()
    execute_experiment(
        client.app.state.sessions, settings, claim_experiment(client.app.state.sessions, settings)
    )
    failed = client.get(f"/api/quant/runs/{job['id']}").json()
    assert failed["status"] == "failed" and "滚动分区" in failed["error"]
