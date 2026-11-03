import logging
import subprocess
import sys
import time
from datetime import timedelta
from uuid import uuid4

import pytest

from app.db import QuantDataset, QuantRun, ResearchJob
from app.jobs.service import recover_expired_jobs
from app.quant.schemas import ExperimentInput
from app.quant.service import enqueue_experiment, recover_experiments
from app.runtime.agent_slot import AgentSlot
from app.runtime.processes import ChildProcess
from app.runtime.quant_slot import QuantSlot
from app.shared.time import utc_now


class ControlledChild:
    def __init__(self):
        self.code, self.timed_out, self.stopped = None, False, 0

    def poll(self):
        return self.code

    def expired(self, timeout):
        return self.timed_out

    def stop(self):
        self.stopped += 1
        self.code = self.code if self.code is not None else -9
        return self.code


def queued(client, settings, kind):
    if kind == "agent":
        market = client.get("/api/market/quotes").json()
        response = client.post(
            "/api/jobs",
            json={
                "symbol": "DEMO001",
                "snapshot_id": market["snapshot_id"],
                "mode": "rules",
            },
        )
        return response.json()["id"], ResearchJob, AgentSlot
    with client.app.state.sessions() as session:
        dataset = QuantDataset(
            id=str(uuid4()), mode="demo", name="test", source="test", checksum="a" * 64, details={}
        )
        session.add(dataset)
        session.commit()
        run = enqueue_experiment(session, settings, ExperimentInput(dataset_id=dataset.id))
        return run["id"], QuantRun, QuantSlot


@pytest.mark.parametrize("kind", ["agent", "quant"])
@pytest.mark.parametrize("outcome", ["cancel", "timeout", "crash", "success"])
def test_slot_reaps_child_and_preserves_terminal_result(client, settings, kind, outcome):
    identifier, model, slot_type = queued(client, settings, kind)
    child = ControlledChild()
    slot = slot_type(client.app.state.sessions, settings, launch=lambda *_: child)
    slot.tick()
    with client.app.state.sessions() as session:
        row = session.get(model, identifier)
        assert row.status == "running"
        if outcome == "cancel":
            row.cancel_requested = True
        elif outcome == "success":
            row.status = "succeeded"
            child.code = 0
        elif outcome == "crash":
            child.code = 17
        else:
            child.timed_out = True
        session.commit()
    slot.tick()
    with client.app.state.sessions() as session:
        row = session.get(model, identifier)
        assert (
            row.status
            == {
                "cancel": "cancelled",
                "timeout": "failed",
                "crash": "failed",
                "success": "succeeded",
            }[outcome]
        )
    assert child.stopped == 1
    assert slot.child is None


@pytest.mark.parametrize("kind", ["agent", "quant"])
def test_spawn_failure_is_safe_and_does_not_stop_worker(client, settings, kind, caplog):
    identifier, model, slot_type = queued(client, settings, kind)

    def fail(*_):
        raise OSError("secret test sentinel")

    caplog.set_level(logging.INFO, logger="app.runtime.processes")
    slot_type(client.app.state.sessions, settings, launch=fail).tick()
    with client.app.state.sessions() as session:
        row = session.get(model, identifier)
        assert row.status == "failed"
        assert "secret test sentinel" not in row.error
    assert "spawn_failed" in caplog.text
    assert identifier in caplog.text
    assert "secret test sentinel" not in caplog.text


def test_old_agent_slot_cannot_overwrite_new_lease(client, settings):
    identifier, model, slot_type = queued(client, settings, "agent")
    child = ControlledChild()
    slot = slot_type(client.app.state.sessions, settings, launch=lambda *_: child)
    slot.tick()
    with client.app.state.sessions() as session:
        session.get(model, identifier).lease_owner = "replacement-owner"
        session.commit()
    slot.tick()
    with client.app.state.sessions() as session:
        row = session.get(model, identifier)
        assert row.status == "running" and row.lease_owner == "replacement-owner"
    assert child.stopped == 1


@pytest.mark.parametrize("kind", ["agent", "quant"])
def test_shutdown_reaps_child_and_keeps_domain_recovery_policy(client, settings, kind):
    identifier, model, slot_type = queued(client, settings, kind)
    child = ControlledChild()
    slot = slot_type(client.app.state.sessions, settings, launch=lambda *_: child)
    slot.tick()
    slot.close()
    assert child.stopped == 1
    with client.app.state.sessions() as session:
        row = session.get(model, identifier)
        assert row.status == "running"
        if kind == "agent":
            row.lease_until = utc_now() - timedelta(seconds=1)
            session.commit()
    if kind == "agent":
        recover_expired_jobs(client.app.state.sessions, settings.job_max_attempts)
    else:
        recover_experiments(client.app.state.sessions)
    with client.app.state.sessions() as session:
        assert session.get(model, identifier).status == ("queued" if kind == "agent" else "failed")


def test_real_child_is_killed_and_waited_without_sleeping_for_timeout():
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    child = ChildProcess(process, time.monotonic() - 100)
    try:
        assert child.expired(10)
        assert child.stop() is not None
        assert process.poll() is not None
        assert child.stop() == process.returncode
    finally:
        child.stop()
