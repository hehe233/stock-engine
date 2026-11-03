import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.db import ResearchJob
from app.http.dependencies import SessionDep
from app.jobs.service import (
    TERMINAL,
    cancel_requested_job,
    create_job,
    list_events,
    retry_failed_job,
    serialize_job,
)
from app.schemas import (
    AnalysisRequest,
    JobResponse,
)

router = APIRouter(prefix="/api")


@router.post("/jobs", response_model=JobResponse, status_code=202)
def submit_job(payload: AnalysisRequest, request: Request, session: SessionDep):
    return create_job(session, payload, request.app.state.settings)


@router.get("/jobs")
def jobs(session: SessionDep, limit: Annotated[int, Query(ge=1, le=100)] = 30):
    rows = session.scalars(
        select(ResearchJob).order_by(ResearchJob.created_at.desc()).limit(limit)
    ).all()
    return {"items": [serialize_job(row) for row in rows]}


@router.get("/jobs/{job_id}", response_model=JobResponse)
def job_detail(job_id: str, session: SessionDep):
    job = session.get(ResearchJob, job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    return serialize_job(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: str, session: SessionDep):
    return cancel_requested_job(session, job_id)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: str, request: Request, session: SessionDep):
    return retry_failed_job(session, job_id, request.app.state.settings)


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, after: Annotated[int, Query(ge=0)] = 0):
    sessions = request.app.state.sessions
    with sessions() as session:
        if session.get(ResearchJob, job_id) is None:
            raise HTTPException(404, "任务不存在")
    try:
        after = max(after, int(request.headers.get("Last-Event-ID", "0")))
    except ValueError as exc:
        raise HTTPException(422, "Last-Event-ID 必须是整数") from exc

    async def stream():
        cursor = after
        while not await request.is_disconnected():
            with sessions() as session:
                job = session.get(ResearchJob, job_id)
                status = job.status
                items = list_events(session, job_id, cursor)
            for item in items:
                cursor = item.id
                yield f"id: {item.id}\nevent: progress\ndata: {item.model_dump_json()}\n\n"
            if status in TERMINAL and len(items) < 100:
                yield f"event: done\ndata: {json.dumps({'status': status})}\n\n"
                break
            yield ": heartbeat\n\n"
            if len(items) < 100:
                await asyncio.sleep(0.15)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
