from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select

from app.db import AnalysisRun
from app.http.dependencies import SessionDep
from app.reports.service import create_rule_report
from app.schemas import (
    AnalysisList,
    AnalysisReport,
    AnalysisRequest,
)

router = APIRouter(prefix="/api")


@router.post("/analyses", response_model=AnalysisReport, status_code=201)
def create_analysis(payload: AnalysisRequest, request: Request, session: SessionDep):
    return create_rule_report(session, payload, request.app.state.research_graph)


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
