from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request

from app.db import DataRequest
from app.http.dependencies import SessionDep
from app.research.collection import enqueue
from app.research.history import history_list
from app.research.queries import dataset, request_view
from app.research.schemas import (
    DataRequestResponse,
    FetchRequest,
    HistoryResponse,
    ResearchDatasetResponse,
    ResearchKind,
)

router = APIRouter(prefix="/api")


@router.get(
    "/research/data", response_model=ResearchDatasetResponse, response_model_exclude_unset=True
)
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


@router.post(
    "/research/refresh",
    status_code=202,
    response_model=DataRequestResponse,
    response_model_exclude_unset=True,
)
def refresh_research(payload: FetchRequest, request: Request, session: SessionDep):
    return enqueue(session, payload, request.app.state.settings)


@router.get(
    "/research/requests/{request_id}",
    response_model=DataRequestResponse,
    response_model_exclude_unset=True,
)
def data_request(request_id: str, request: Request, session: SessionDep):
    row = session.get(DataRequest, request_id)
    if row is None or row.mode != request.app.state.settings.market_provider:
        raise HTTPException(404, "采集任务不存在")
    return request_view(row)


@router.get("/research/history", response_model=HistoryResponse, response_model_exclude_unset=True)
def historical_cases(request: Request, session: SessionDep):
    return history_list(session, request.app.state.settings)
