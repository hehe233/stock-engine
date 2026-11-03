from datetime import date, timedelta
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.db import DataRequest, ResearchSnapshot
from app.providers.base import ProviderError
from app.providers.research import fetch_research
from app.research.queries import checked_query, query_key, request_view
from app.research.schemas import FetchRequest
from app.shared.time import SHANGHAI, as_utc, utc_now

admission_lock = Lock()


def enqueue(session, query, settings):
    query = checked_query(query, settings.market_provider)
    key = query_key(query, settings.market_provider)
    with admission_lock:
        previous = session.scalar(
            select(DataRequest)
            .where(DataRequest.key == key)
            .order_by(DataRequest.created_at.desc())
            .limit(1)
        )
        if previous and (
            previous.status in {"queued", "running"}
            or (utc_now() - as_utc(previous.created_at)).total_seconds() < 300
        ):
            return request_view(previous)
        pending = session.scalar(
            select(func.count())
            .select_from(DataRequest)
            .where(DataRequest.status.in_(["queued", "running"]))
        )
        if pending >= 20:
            raise HTTPException(429, "数据采集队列已满，请稍后再试")
        row = DataRequest(
            id=str(uuid4()),
            key=key,
            mode=settings.market_provider,
            params=query.model_dump(mode="json"),
        )
        session.add(row)
        session.commit()
        return request_view(row)


def store_snapshot(session, query, mode, payload):
    row = ResearchSnapshot(
        id=str(uuid4()),
        key=query_key(query, mode),
        kind=query.kind,
        mode=mode,
        query_date=query.date,
        data_date=date.fromisoformat(payload["data_date"]) if payload.get("data_date") else None,
        source=payload["source"],
        observed_at=utc_now(),
        rows=payload["rows"],
        details=payload["details"],
    )
    session.add(row)
    session.flush()
    return row


def process_one(sessions, settings):
    with sessions() as session:
        row = session.scalar(
            select(DataRequest)
            .where(DataRequest.status == "queued", DataRequest.mode == settings.market_provider)
            .order_by(DataRequest.created_at)
            .limit(1)
        )
        if row is None:
            return
        result = session.execute(
            update(DataRequest)
            .where(DataRequest.id == row.id, DataRequest.status == "queued")
            .values(status="running", updated_at=utc_now())
        )
        if result.rowcount != 1:
            session.rollback()
            return
        session.commit()
        request_id, params, mode = row.id, row.params, row.mode
    try:
        query = FetchRequest.model_validate(params)
        payload = fetch_research(
            query.model_dump(mode="json"), mode, settings.provider_timeout_seconds
        )
        with sessions() as session:
            snapshot = store_snapshot(session, query, mode, payload)
            row = session.get(DataRequest, request_id)
            row.status, row.snapshot_id, row.updated_at = "succeeded", snapshot.id, utc_now()
            session.commit()
    except Exception as exc:
        with sessions() as session:
            row = session.get(DataRequest, request_id)
            row.status, row.updated_at = "failed", utc_now()
            row.error = (
                str(exc)[:500]
                if isinstance(exc, ProviderError)
                else f"采集失败（{type(exc).__name__}）；保留旧快照"
            )
            session.commit()


def recover_requests(sessions):
    # 只在取得单 worker 文件锁之后执行；旧进程退出后不留永久 running。
    with sessions() as session:
        session.execute(
            update(DataRequest)
            .where(DataRequest.status == "running")
            .values(status="queued", updated_at=utc_now(), error="上次采集中断，已重新排队")
        )
        session.commit()


def schedule_research(sessions, settings, calendar_dates):
    now = utc_now().astimezone(SHANGHAI)
    today = now.date()
    if today.weekday() >= 5 or not 9 <= now.hour <= 20:
        return
    prior = [
        value
        for value in calendar_dates
        if (today - timedelta(days=10)).isoformat() <= value < today.isoformat()
    ]
    disclosure_day = today if now.hour >= 16 else date.fromisoformat(max(prior)) if prior else today
    kinds = ("ladder", "flow", "dragon", "notices")
    for kind in kinds:
        query = FetchRequest(kind=kind, date=disclosure_day if kind == "dragon" else today)
        with sessions() as session:
            try:
                enqueue(session, query, settings)
            except HTTPException:
                return
