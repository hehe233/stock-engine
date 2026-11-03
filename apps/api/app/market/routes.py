from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.db import ServiceState
from app.http.dependencies import SessionDep
from app.market.calendar import market_session
from app.market.service import set_service_state
from app.schemas import (
    AssetType,
    MarketResponse,
)
from app.shared.time import as_utc, utc_now

router = APIRouter(prefix="/api")


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
