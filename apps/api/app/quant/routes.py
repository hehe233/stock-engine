from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from app.db import QuantDataset, QuantRun
from app.http.dependencies import SessionDep
from app.quant.artifacts import checked_artifact, prediction_page
from app.quant.datasets import (
    OPTIONAL,
    REQUIRED,
    audit_frame,
    dataset_view,
    demo_frame,
    import_history,
    parse_csv,
    store_dataset,
)
from app.quant.schemas import (
    DatasetAudit,
    DatasetImport,
    DatasetListResponse,
    DatasetResponse,
    ExperimentInput,
    PredictionPage,
    RunListResponse,
    RunResponse,
)
from app.quant.service import cancel_experiment, enqueue_experiment, get_run, run_view

router = APIRouter(prefix="/api/quant")


@router.get("/datasets", response_model=DatasetListResponse, response_model_exclude_unset=True)
def datasets(request: Request, session: SessionDep):
    rows = session.scalars(
        select(QuantDataset)
        .where(QuantDataset.mode == request.app.state.settings.market_provider)
        .order_by(QuantDataset.created_at.desc())
        .limit(100)
    ).all()
    return {"items": [dataset_view(row) for row in rows]}


@router.get("/template")
def template():
    content = (
        ",".join(REQUIRED + OPTIONAL)
        + "\n600000.SH,2025-01-02,10,10.5,9.9,10.2,1000000,10,11,9,true,"
        "2025-01-02T16:00:00+08:00,1999-11-10,\n"
    )
    return Response(
        "\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="quant-bars.csv"'},
    )


@router.post("/datasets/preview", response_model=DatasetAudit, response_model_exclude_unset=True)
def preview(payload: DatasetImport, request: Request):
    frame = parse_csv(payload.content, request.app.state.settings.market_provider)
    return audit_frame(frame, payload.adjustment, payload.selection)


@router.post(
    "/datasets", status_code=201, response_model=DatasetResponse, response_model_exclude_unset=True
)
def import_dataset(payload: DatasetImport, request: Request, session: SessionDep):
    settings = request.app.state.settings
    frame = parse_csv(payload.content, settings.market_provider)
    return store_dataset(
        session,
        settings,
        frame,
        payload.name,
        payload.source,
        payload.adjustment,
        payload.selection,
    )


@router.post(
    "/datasets/history",
    status_code=201,
    response_model=DatasetResponse,
    response_model_exclude_unset=True,
)
def from_history(request: Request, session: SessionDep):
    return import_history(session, request.app.state.settings)


@router.post(
    "/datasets/demo",
    status_code=201,
    response_model=DatasetResponse,
    response_model_exclude_unset=True,
)
def from_demo(request: Request, session: SessionDep):
    settings = request.app.state.settings
    if settings.market_provider != "demo":
        raise HTTPException(409, "合成实验集仅在隔离演示模式提供")
    return store_dataset(
        session, settings, demo_frame(), "合成八证券实验集", "demo:synthetic", "raw", "manual"
    )


@router.post(
    "/runs", status_code=202, response_model=RunResponse, response_model_exclude_unset=True
)
def create_run(payload: ExperimentInput, request: Request, session: SessionDep):
    return enqueue_experiment(session, request.app.state.settings, payload)


@router.get("/runs", response_model=RunListResponse, response_model_exclude_unset=True)
def runs(request: Request, session: SessionDep):
    rows = session.scalars(
        select(QuantRun)
        .where(QuantRun.mode == request.app.state.settings.market_provider)
        .order_by(QuantRun.created_at.desc())
        .limit(50)
    ).all()
    return {"items": [run_view(row) for row in rows]}


@router.get("/runs/{identifier}", response_model=RunResponse, response_model_exclude_unset=True)
def experiment(identifier: str, request: Request, session: SessionDep):
    return run_view(get_run(session, request.app.state.settings, identifier), True)


@router.post(
    "/runs/{identifier}/cancel", response_model=RunResponse, response_model_exclude_unset=True
)
def cancel(identifier: str, request: Request, session: SessionDep):
    return cancel_experiment(session, get_run(session, request.app.state.settings, identifier))


@router.get(
    "/runs/{identifier}/predictions",
    response_model=PredictionPage,
    response_model_exclude_unset=True,
)
def predictions(
    identifier: str, request: Request, session: SessionDep, page: Annotated[int, Query(ge=1)] = 1
):
    settings = request.app.state.settings
    return prediction_page(settings, get_run(session, settings, identifier), page)


@router.get("/runs/{identifier}/artifacts/{filename}")
def artifact(
    identifier: str,
    filename: Literal["predictions.parquet", "models.json"],
    request: Request,
    session: SessionDep,
):
    settings = request.app.state.settings
    path = checked_artifact(settings, get_run(session, settings, identifier), filename)
    return FileResponse(path, filename=f"{identifier}-{filename}")
