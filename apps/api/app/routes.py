import asyncio
import json
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text

from app.db import AnalysisRun, MarketSnapshot, ResearchJob, ServiceState
from app.http.dependencies import SessionDep
from app.schemas import (
    AnalysisList,
    AnalysisReport,
    AnalysisRequest,
    AssetType,
    JobResponse,
    MarketResponse,
)
from app.services.calendar import market_session
from app.services.jobs import (
    TERMINAL,
    create_job,
    event,
    list_events,
    queue_admission,
    retry_failed_job,
    serialize_job,
)
from app.services.market import set_service_state
from app.services.model_settings import (
    ModelSettingsInput,
    ProfileInput,
    RevisionInput,
    activate_profile,
    delete_profile,
    draft_settings,
    effective_settings,
    list_profiles,
    probe_connection,
    profile_draft,
    public_settings,
    save_profile,
    save_settings,
    settings_lock,
)
from app.shared.time import as_utc, utc_now

router = APIRouter(prefix="/api")


@router.get("/health")
def health(request: Request, session: SessionDep):
    session.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "data_mode": request.app.state.settings.market_provider,
        "version": "0.2.0",
    }


@router.get("/config")
def config(request: Request, session: SessionDep):
    settings = effective_settings(session, request.app.state.settings)
    return {
        "market_provider": settings.market_provider,
        "refresh_interval_seconds": settings.refresh_interval_seconds,
        "api_configured": bool(settings.llm_api_key and settings.api_models),
        "api_models": settings.api_models,
        "default_model": settings.llm_model,
        "ollama_model": settings.ollama_model,
    }


@router.get("/settings/models")
def get_model_settings(request: Request, session: SessionDep):
    return public_settings(session, request.app.state.settings)


@router.post("/settings/models")
def update_model_settings(payload: ModelSettingsInput, request: Request, session: SessionDep):
    with settings_lock:
        return save_settings(session, request.app.state.settings, payload)


@router.post("/settings/models/test")
def test_model_settings(payload: ModelSettingsInput, request: Request, session: SessionDep):
    candidate = draft_settings(session, request.app.state.settings, payload)
    return probe_connection(candidate)


@router.get("/settings/models/profiles")
def model_profiles(request: Request, session: SessionDep):
    return list_profiles(session, request.app.state.settings)


@router.post("/settings/models/profiles", status_code=201)
def create_model_profile(payload: ProfileInput, request: Request, session: SessionDep):
    with settings_lock:
        return save_profile(session, request.app.state.settings, payload)


@router.post("/settings/models/profiles/test")
def test_new_profile(payload: ProfileInput, request: Request, session: SessionDep):
    return probe_connection(profile_draft(session, request.app.state.settings, payload))


@router.post("/settings/models/profiles/{profile_id}/update")
def update_model_profile(
    profile_id: str, payload: ProfileInput, request: Request, session: SessionDep
):
    with settings_lock:
        return save_profile(session, request.app.state.settings, payload, profile_id)


@router.post("/settings/models/profiles/{profile_id}/test")
def test_saved_profile(
    profile_id: str, payload: ProfileInput, request: Request, session: SessionDep
):
    return probe_connection(profile_draft(session, request.app.state.settings, payload, profile_id))


@router.post("/settings/models/profiles/{profile_id}/activate")
def activate_model_profile(
    profile_id: str, payload: RevisionInput, request: Request, session: SessionDep
):
    with settings_lock:
        return activate_profile(session, request.app.state.settings, profile_id, payload.revision)


@router.post("/settings/models/profiles/{profile_id}/delete")
def delete_model_profile(
    profile_id: str, payload: RevisionInput, request: Request, session: SessionDep
):
    with settings_lock:
        return delete_profile(session, request.app.state.settings, profile_id, payload.revision)


@router.get("/market/status")
def market_status(request: Request, session: SessionDep):
    worker = session.get(ServiceState, "worker")
    calendar = session.get(ServiceState, "calendar")
    collection = {}
    for asset in ("stock", "etf", "index"):
        row = session.get(ServiceState, f"collection:{asset}")
        collection[asset] = (
            {**row.value, "updated_at": as_utc(row.updated_at)} if row else {"status": "pending"}
        )
    return {
        "worker_online": bool(
            worker and (utc_now() - as_utc(worker.updated_at)).total_seconds() < 15
        ),
        "session": market_session(utc_now(), calendar.value.get("dates", []) if calendar else []),
        "collection": collection,
    }


@router.get("/market/quotes", response_model=MarketResponse)
def market_quotes(
    request: Request,
    session: SessionDep,
    asset_type: AssetType = "stock",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str, Query(max_length=80)] = "",
    sort_by: Literal[
        "symbol", "price", "change_pct", "turnover_pct", "volume_ratio", "amount_yuan"
    ] = "change_pct",
    descending: bool = True,
):
    result = request.app.state.market.latest(
        session, asset_type, page, page_size, search, sort_by, descending
    )
    if result is None:
        raise HTTPException(status_code=503, detail="暂无行情快照，请稍后刷新")
    return result


@router.post("/market/refresh", status_code=202)
def refresh_market(request: Request):
    with request.app.state.sessions() as session:
        previous = session.get(ServiceState, "refresh_request")
        if previous and (utc_now() - as_utc(previous.updated_at)).total_seconds() < 300:
            raise HTTPException(429, "免费全量采集每五分钟最多请求一次，请等待当前采集")
    set_service_state(request.app.state.sessions, "refresh_request", {"pending": True})
    return {"accepted": True, "message": "已请求后台刷新，可在数据状态中查看结果"}


@router.post("/analyses", response_model=AnalysisReport, status_code=201)
def create_analysis(payload: AnalysisRequest, request: Request, session: SessionDep):
    if payload.mode != "rules":
        raise HTTPException(422, "模型分析请使用 /api/jobs 异步任务接口")
    # 使用前端实际看到的快照，避免刷新恰好发生时分析了另一个版本的数据。
    snapshot = session.get(MarketSnapshot, payload.snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="行情快照不存在，请刷新行情后重试")
    quote = next((item for item in snapshot.quotes if item["symbol"] == payload.symbol), None)
    if quote is None:
        raise HTTPException(status_code=404, detail="该快照中不存在这只股票")

    # 同步路由在线程池内运行，不阻塞 FastAPI 的事件循环。
    result = request.app.state.research_graph.invoke(
        {"quote": quote, "trace": [], "is_demo": snapshot.source == "demo"}
    )
    report = AnalysisReport(
        id=str(uuid4()),
        snapshot_id=snapshot.id,
        symbol=quote["symbol"],
        name=quote["name"],
        created_at=utc_now(),
        as_of=quote.get("quote_time")
        or (as_utc(snapshot.as_of) if snapshot.source == "demo" and snapshot.as_of else None),
        source=snapshot.source,
        is_demo=snapshot.source == "demo",
        asset_type=snapshot.asset_type,
        heat_score=result["heat_score"],
        summary=result["summary"],
        factors=result["factors"],
        risks=result["risks"],
        trace=result["trace"],
    )
    session.add(
        AnalysisRun(
            id=report.id,
            snapshot_id=snapshot.id,
            symbol=report.symbol,
            created_at=report.created_at,
            report=report.model_dump(mode="json"),
        )
    )
    session.commit()
    return report


@router.get("/analyses", response_model=AnalysisList)
def list_analyses(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows = session.scalars(
        select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).offset(offset).limit(limit)
    ).all()
    total = session.scalar(select(func.count()).select_from(AnalysisRun)) or 0
    return {"items": [row.report for row in rows], "total": total}


@router.get("/analyses/{run_id}", response_model=AnalysisReport)
def get_analysis(run_id: str, session: SessionDep):
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return run.report


@router.post("/jobs", response_model=JobResponse, status_code=202)
def submit_job(payload: AnalysisRequest, request: Request, session: SessionDep):
    with queue_admission:
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
    job = session.get(ResearchJob, job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    if job.status not in TERMINAL:
        job.cancel_requested, job.updated_at = True, utc_now()
        if job.status == "queued":
            job.status = "cancelled"
        event(session, job.id, "cancel_requested", message="取消请求已记录")
        session.commit()
    return serialize_job(job)


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: str, request: Request, session: SessionDep):
    with queue_admission:
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
