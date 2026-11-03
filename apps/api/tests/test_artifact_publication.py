"""Publication failures must not destroy committed data or expose partial results."""

from contextlib import contextmanager
from uuid import uuid4

import pandas as pd
import pytest
from sqlalchemy import select

from app.db import QuantDataset, QuantRun
from app.quant.artifacts import ArtifactWrite, artifact_path, checksum
from app.quant.datasets import demo_frame, store_dataset
from app.quant.service import claim_experiment, execute_experiment


@pytest.mark.parametrize("durable", [False, True])
def test_dataset_commit_failure_only_discards_unreferenced_files(
    client, settings, monkeypatch, durable
):
    existing = client.post("/api/quant/datasets/demo").json()
    existing_path = artifact_path(settings, "demo", existing["id"], "bars.parquet")
    with client.app.state.sessions() as session:
        commit = session.commit

        def broken_commit():
            if durable:
                commit()
            raise OSError("commit acknowledgement lost")

        monkeypatch.setattr(session, "commit", broken_commit)
        with pytest.raises(OSError):
            store_dataset(session, settings, demo_frame().head(60), "new", "test", "raw", "manual")
    with client.app.state.sessions() as session:
        rows = session.scalars(select(QuantDataset)).all()
        assert len(rows) == (2 if durable else 1)
        assert {p.name for p in existing_path.parent.parent.iterdir()} == {row.id for row in rows}
        for row in rows:
            assert checksum(artifact_path(settings, "demo", row.id, "bars.parquet")) == row.checksum
    assert checksum(existing_path) == existing["checksum"]


def test_partial_parquet_write_is_removed(settings, monkeypatch):
    identifier = str(uuid4())

    def broken_write(self, path, **kwargs):
        path.write_bytes(b"partial parquet")
        raise OSError("disk full")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", broken_write)
    with pytest.raises(OSError):
        with ArtifactWrite(settings, "demo", identifier) as files:
            files.frame("bars.parquet", pd.DataFrame({"a": [1]}))
    assert not artifact_path(settings, "demo", identifier, "bars.parquet").parent.exists()


def test_existing_version_is_never_overwritten_or_removed(settings):
    identifier = str(uuid4())
    with ArtifactWrite(settings, "demo", identifier) as files:
        files.models({"old": True})
        files.preserve()
    path = artifact_path(settings, "demo", identifier, "models.json")
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        with ArtifactWrite(settings, "demo", identifier):
            pytest.fail("must not enter an existing version")
    assert path.read_bytes() == before


def test_model_write_failure_cleans_predictions_and_marks_experiment_failed(
    client, settings, monkeypatch
):
    dataset = client.post("/api/quant/datasets/demo").json()
    job = client.post("/api/quant/runs", json={"dataset_id": dataset["id"]}).json()
    identifier = claim_experiment(client.app.state.sessions, settings)
    monkeypatch.setattr(
        "app.quant.engine.train_experiment",
        lambda *args: ({}, pd.DataFrame({"a": [1]}), {"bad": float("nan")}),
    )
    execute_experiment(client.app.state.sessions, settings, identifier)
    assert client.get(f"/api/quant/runs/{identifier}").json()["status"] == "failed"
    assert not artifact_path(settings, "demo", job["id"], "predictions.parquet").parent.exists()
    assert artifact_path(settings, "demo", dataset["id"], "bars.parquet").is_file()


@pytest.mark.parametrize("durable", [False, True])
def test_run_commit_failure_preserves_only_durable_publication(
    client, settings, monkeypatch, durable
):
    dataset = client.post("/api/quant/datasets/demo").json()
    job = client.post("/api/quant/runs", json={"dataset_id": dataset["id"]}).json()
    identifier = claim_experiment(client.app.state.sessions, settings)
    monkeypatch.setattr(
        "app.quant.engine.train_experiment",
        lambda *args: ({}, pd.DataFrame({"a": [1]}), [{"model": "test"}]),
    )

    @contextmanager
    def broken_sessions():
        with client.app.state.sessions() as session:
            commit = session.commit

            def broken_commit():
                publishing = any(
                    isinstance(row, QuantRun) and row.result.get("artifacts")
                    for row in session.dirty
                )
                if publishing:
                    if durable:
                        commit()
                    raise OSError("commit acknowledgement lost")
                commit()

            monkeypatch.setattr(session, "commit", broken_commit)
            yield session

    execute_experiment(broken_sessions, settings, identifier)
    result = client.get(f"/api/quant/runs/{job['id']}").json()
    assert result["status"] == ("succeeded" if durable else "failed")
    path = artifact_path(settings, "demo", identifier, "predictions.parquet")
    assert path.exists() is durable
    if durable:
        assert checksum(path) == result["result"]["artifacts"]["predictions.parquet"]


def test_predictions_pages_download_and_tamper_share_integrity_guard(client, settings):
    dataset = client.post("/api/quant/datasets/demo").json()
    job = client.post("/api/quant/runs", json={"dataset_id": dataset["id"]}).json()
    identifier = job["id"]
    frame = pd.DataFrame(
        [
            {
                "symbol": f"DEMO{i:03}",
                "date": "2024-01-02",
                "label_end": "2024-01-09",
                "label": 0,
                "future_return": 0.01,
                "probability": 0.1,
                "raw_probability": 0.2,
                "fold": 1,
            }
            for i in range(105)
        ]
    )
    with ArtifactWrite(settings, "demo", identifier) as files:
        digest = files.frame("predictions.parquet", frame)
        with client.app.state.sessions() as session:
            row = session.get(QuantRun, identifier)
            row.status, row.result = "succeeded", {"artifacts": {"predictions.parquet": digest}}
            session.commit()
        files.preserve()
    pages = [
        client.get(f"/api/quant/runs/{identifier}/predictions?page={i}").json() for i in (1, 2, 3)
    ]
    assert [len(page["items"]) for page in pages] == [50, 50, 5]
    assert all(page["total"] == 105 for page in pages)
    assert [row["symbol"] for page in pages for row in page["items"]] == frame.symbol.tolist()
    assert client.get(f"/api/quant/runs/{identifier}/predictions?page=0").status_code == 422
    url = f"/api/quant/runs/{identifier}/artifacts/predictions.parquet"
    assert client.get(url).status_code == 200
    path = artifact_path(settings, "demo", identifier, "predictions.parquet")
    path.write_bytes(path.read_bytes() + b"tampered")
    assert client.get(url).status_code == 409
    assert client.get(f"/api/quant/runs/{identifier}/predictions").status_code == 409
