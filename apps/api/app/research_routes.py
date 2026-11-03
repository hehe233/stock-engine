from datetime import date
from threading import Lock
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.db import DataRequest, PositionLot
from app.http.dependencies import SessionDep
from app.research_schemas import (
    CsvPreview,
    FetchRequest,
    PositionImport,
    PositionInput,
    ResearchKind,
)
from app.services.portfolio import CSV_COLUMNS, import_lots, portfolio_view, preview_csv
from app.services.research_data import dataset, enqueue, history_list, request_view
from app.shared.time import utc_now

router = APIRouter(prefix="/api")
positions_lock = Lock()


@router.get("/research/data")
def research_data(
    request: Request,
    session: SessionDep,
    kind: ResearchKind,
    date: date,
    symbol: str = "",
    case_id: str = "",
    search: Annotated[str, Query(max_length=80)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    from pydantic import ValidationError

    try:
        query = FetchRequest(kind=kind, date=date, symbol=symbol, case_id=case_id)
    except ValidationError as exc:
        raise HTTPException(422, "日期或代码无效；资金排名只支持当前日期") from exc
    return dataset(session, query, request.app.state.settings, search, page, page_size)


@router.post("/research/refresh", status_code=202)
def refresh_research(payload: FetchRequest, request: Request, session: SessionDep):
    return enqueue(session, payload, request.app.state.settings)


@router.get("/research/requests/{request_id}")
def data_request(request_id: str, request: Request, session: SessionDep):
    row = session.get(DataRequest, request_id)
    if row is None or row.mode != request.app.state.settings.market_provider:
        raise HTTPException(404, "采集任务不存在")
    return request_view(row)


@router.get("/research/history")
def historical_cases(request: Request, session: SessionDep):
    return history_list(session, request.app.state.settings)


@router.get("/portfolio")
def holdings(request: Request, session: SessionDep):
    return portfolio_view(session, request.app.state.settings.market_provider)


@router.get("/portfolio/template")
def holdings_template():
    content = (
        ",".join(CSV_COLUMNS)
        + "\n600000.SH,浦发银行,stock,100,10.0000,2026-10-30,T1,示例行请修改或删除\n"
    )
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="positions-template.csv"'},
    )


@router.post("/portfolio/preview")
def preview_holdings(payload: CsvPreview):
    return preview_csv(payload.content)


@router.post("/portfolio/import")
def import_holdings(payload: PositionImport, request: Request, session: SessionDep):
    with positions_lock:
        return import_lots(session, payload.rows, request.app.state.settings.market_provider)


@router.post("/portfolio/{lot_id}/update")
def update_holding(lot_id: str, payload: PositionInput, request: Request, session: SessionDep):
    with positions_lock:
        row = session.get(PositionLot, lot_id)
        mode = request.app.state.settings.market_provider
        if row is None or row.mode != mode:
            raise HTTPException(404, "持仓不存在")
        if mode == "public" and payload.symbol.startswith("DEMO"):
            raise HTTPException(422, "公开模式不支持演示持仓")
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        row.updated_at = utc_now()
        session.commit()
    return {"updated": True}


@router.post("/portfolio/{lot_id}/delete")
def delete_holding(lot_id: str, request: Request, session: SessionDep):
    with positions_lock:
        row = session.get(PositionLot, lot_id)
        if row is None or row.mode != request.app.state.settings.market_provider:
            raise HTTPException(404, "持仓不存在")
        session.delete(row)
        session.commit()
    return {"deleted": True}
