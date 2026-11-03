"""Public use cases keep related writes atomic and retries keep submitted evidence."""

from copy import deepcopy

import pytest
from sqlalchemy import select

from app.db import AnalysisRun, JobEvent, PositionLot, ResearchJob, ResearchSnapshot
from app.jobs.service import cancel_requested_job, create_job, retry_failed_job
from app.portfolio.schemas import PositionInput
from app.portfolio.service import delete_lot, import_lots, update_lot
from app.reports.service import create_rule_report
from app.schemas import AnalysisRequest
from app.shared.time import SHANGHAI, utc_now


def analysis_request(client):
    market = client.get("/api/market/quotes").json()
    return AnalysisRequest(snapshot_id=market["snapshot_id"], symbol="DEMO001", mode="rules")


def position():
    return PositionInput(
        symbol="DEMO001",
        name="事务验证",
        quantity=100,
        cost_price="10.0000",
        acquired_on=utc_now().astimezone(SHANGHAI).date(),
    )


def persisted_state(sessions):
    with sessions() as session:
        return {
            "jobs": [
                (r.id, r.status, r.cancel_requested, r.context)
                for r in session.scalars(select(ResearchJob).order_by(ResearchJob.id))
            ],
            "events": [
                (r.id, r.job_id, r.kind, r.payload)
                for r in session.scalars(select(JobEvent).order_by(JobEvent.id))
            ],
            "lots": [
                (r.id, r.quantity, r.cost_price, r.updated_at)
                for r in session.scalars(select(PositionLot).order_by(PositionLot.id))
            ],
            "reports": list(session.scalars(select(AnalysisRun.id).order_by(AnalysisRun.id))),
        }


@pytest.mark.parametrize("operation", ["submit", "cancel", "import", "update", "delete", "report"])
def test_failed_commit_does_not_leave_partial_business_state(
    client, settings, monkeypatch, operation
):
    sessions = client.app.state.sessions
    payload = analysis_request(client)
    with sessions() as session:
        job = create_job(session, payload, settings)
        import_lots(session, [position()], "demo")
        lot_id = session.scalar(select(PositionLot.id))
    before = persisted_state(sessions)
    with pytest.raises(RuntimeError, match="simulated commit failure"), sessions() as session:

        def failed_commit():
            # Force SQL writes first, then fail before the transaction becomes durable.
            session.flush()
            raise RuntimeError("simulated commit failure")

        monkeypatch.setattr(session, "commit", failed_commit)
        if operation == "submit":
            create_job(session, payload, settings)
        elif operation == "cancel":
            cancel_requested_job(session, job.id)
        elif operation == "import":
            import_lots(session, [position().model_copy(update={"quantity": 200})], "demo")
        elif operation == "update":
            update_lot(session, lot_id, position().model_copy(update={"quantity": 200}), "demo")
        elif operation == "delete":
            delete_lot(session, lot_id, "demo")
        else:
            create_rule_report(session, payload, client.app.state.research_graph)
    assert persisted_state(sessions) == before


def test_retry_preserves_frozen_research_and_explicit_portfolio(client, settings):
    sessions = client.app.state.sessions
    payload = analysis_request(client).model_copy(update={"include_portfolio": True})
    with sessions() as session:
        import_lots(session, [position()], "demo")
        job = create_job(session, payload, settings)
        stored = session.get(ResearchJob, job.id)
        frozen = deepcopy(stored.context)
        stored.status = "failed"
        snapshot = session.scalar(select(ResearchSnapshot).where(ResearchSnapshot.kind == "ladder"))
        snapshot.rows = []
        session.scalar(select(PositionLot)).quantity = 999
        session.commit()
    with sessions() as session:
        retry_failed_job(session, job.id, settings)
    with sessions() as session:
        retried = session.get(ResearchJob, job.id)
        assert retried.status == "queued"
        assert retried.context == frozen
        assert retried.context["portfolio"]["items"][0]["quantity"] == 100
        assert retried.context["ladder"]["rows"]
