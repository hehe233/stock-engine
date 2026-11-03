from datetime import timedelta
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.core.config import Settings
from app.db import JobEvent, MarketSnapshot, ResearchJob
from app.schemas import AnalysisRequest, EventResponse, JobResponse, Quote
from app.services.model_settings import effective_settings, snapshot_configuration
from app.services.portfolio import portfolio_view
from app.services.research_data import frozen_context
from app.shared.time import SHANGHAI, as_utc, utc_now

TERMINAL = {"succeeded", "failed", "cancelled"}
# 本版部署一个 API 进程。新建和手动重试共用入口锁，避免并发请求绕过容量检查。
# 多 API 实例时需要把容量控制迁入数据库锁或专用队列。
queue_admission = Lock()


def event(session, job_id: str, kind: str, **payload):
    session.add(JobEvent(job_id=job_id, kind=kind, payload=payload))


def serialize_job(job: ResearchJob) -> JobResponse:
    values = {field: getattr(job, field) for field in JobResponse.model_fields}
    for key in ("created_at", "updated_at"):
        values[key] = as_utc(values[key])
    return JobResponse(**values)


def list_events(session, job_id: str, after: int = 0) -> list[EventResponse]:
    rows = session.scalars(
        select(JobEvent)
        .where(JobEvent.job_id == job_id, JobEvent.id > after)
        .order_by(JobEvent.id)
        .limit(100)
    ).all()
    return [
        EventResponse(
            id=row.id, kind=row.kind, created_at=as_utc(row.created_at), payload=row.payload
        )
        for row in rows
    ]


def ensure_queue_capacity(session, settings: Settings):
    pending = session.scalar(
        select(func.count())
        .select_from(ResearchJob)
        .where(ResearchJob.status.in_(["queued", "running"]))
    )
    if pending >= settings.max_pending_jobs:
        raise HTTPException(429, "研究队列已满，请等待已有任务完成")


def create_job(session, payload: AnalysisRequest, settings: Settings) -> JobResponse:
    settings = effective_settings(session, settings)
    snapshot = session.get(MarketSnapshot, payload.snapshot_id)
    if snapshot is None or not any(q["symbol"] == payload.symbol for q in snapshot.quotes):
        raise HTTPException(404, "股票或行情快照不存在，请刷新行情后重试")
    model_name = None
    if payload.mode == "api":
        model_name = payload.model_name or settings.llm_model
        if not settings.llm_api_key or model_name not in settings.api_models:
            raise HTTPException(409, "请在顶部导航的模型设置中配置 API 地址、密钥和可选模型")
    elif payload.mode == "ollama":
        model_name = payload.model_name or settings.ollama_model
        if model_name != settings.ollama_model:
            raise HTTPException(422, "Ollama 模型不在配置列表中")
    ensure_queue_capacity(session, settings)
    target_quote = Quote.model_validate(
        next(q for q in snapshot.quotes if q["symbol"] == payload.symbol)
    )
    evidence_day = (
        as_utc(target_quote.quote_time or snapshot.fetched_at).astimezone(SHANGHAI).date()
    )
    context = frozen_context(
        session,
        payload.symbol,
        settings.market_provider,
        utc_now(),
        evidence_day,
    )
    if payload.include_portfolio:
        context["portfolio"] = portfolio_view(
            session, settings.market_provider, payload.symbol, snapshot
        )
    job = ResearchJob(
        id=str(uuid4()),
        snapshot_id=snapshot.id,
        symbol=payload.symbol,
        mode=payload.mode,
        model_name=model_name,
        context=context,
        model_config_id=(
            snapshot_configuration(session, settings).id if payload.mode != "rules" else None
        ),
    )
    session.add(job)
    session.flush()
    event(session, job.id, "queued", message="任务已入库，等待 worker 执行")
    session.commit()
    return serialize_job(job)


def retry_failed_job(session, job_id: str, settings: Settings) -> JobResponse:
    job = session.get(ResearchJob, job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    if job.status != "failed" or job.attempts >= settings.job_max_attempts:
        raise HTTPException(409, "只有未达到重试次数上限的失败任务可以恢复")
    ensure_queue_capacity(session, settings)
    job.status, job.error, job.updated_at = "queued", None, utc_now()
    job.lease_owner, job.lease_until = None, None
    event(session, job.id, "queued", message="已请求从检查点恢复，模型调用可能产生新费用")
    session.commit()
    return serialize_job(job)


def claim_job(sessions, settings: Settings) -> tuple[str, str] | None:
    with sessions() as session:
        job_id = session.scalar(
            select(ResearchJob.id)
            .where(ResearchJob.status == "queued")
            .order_by(ResearchJob.created_at)
            .limit(1)
        )
        if job_id is None:
            return None
        owner, now = str(uuid4()), utc_now()
        result = session.execute(
            update(ResearchJob)
            .where(ResearchJob.id == job_id, ResearchJob.status == "queued")
            .values(
                status="running",
                lease_owner=owner,
                lease_until=now + timedelta(seconds=settings.job_timeout_seconds + 30),
                attempts=ResearchJob.attempts + 1,
                updated_at=now,
            )
        )
        if result.rowcount != 1:
            session.rollback()
            return None
        event(session, job_id, "running", message="开始执行；已有检查点将用于恢复")
        session.commit()
        return job_id, owner


def finish_failed(sessions, job_id: str, owner: str, message: str, cancelled=False):
    with sessions() as session:
        job = session.get(ResearchJob, job_id)
        if job and job.status == "running" and job.lease_owner == owner:
            job.status = "cancelled" if cancelled or job.cancel_requested else "failed"
            job.error, job.updated_at = message, utc_now()
            job.lease_until = None
            event(session, job.id, job.status, message=message)
            session.commit()


def recover_expired_jobs(sessions, max_attempts: int):
    with sessions() as session:
        jobs = session.scalars(
            select(ResearchJob).where(
                ResearchJob.status == "running", ResearchJob.lease_until < utc_now()
            )
        ).all()
        for job in jobs:
            job.status = (
                "cancelled"
                if job.cancel_requested
                else ("queued" if job.attempts < max_attempts else "failed")
            )
            job.error = "上次执行中断，检查点已保留"
            job.updated_at, job.lease_owner, job.lease_until = utc_now(), None, None
            event(session, job.id, job.status, message=job.error)
        session.commit()
