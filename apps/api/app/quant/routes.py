import hashlib
from typing import Annotated, Literal

import duckdb
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy import select

from app.db import QuantDataset, QuantRun
from app.http.dependencies import SessionDep
from app.quant.data import (
    OPTIONAL,
    REQUIRED,
    artifact_path,
    audit_frame,
    dataset_view,
    demo_frame,
    import_history,
    parse_csv,
    store_dataset,
)
from app.quant.schemas import DatasetImport, ExperimentInput
from app.quant.service import cancel_experiment, enqueue_experiment, get_run, run_view

router = APIRouter(prefix="/api/quant")


@router.get("/datasets")
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


@router.post("/datasets/preview")
def preview(payload: DatasetImport, request: Request):
    frame = parse_csv(payload.content, request.app.state.settings.market_provider)
    return audit_frame(frame, payload.adjustment, payload.selection)


@router.post("/datasets", status_code=201)
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


@router.post("/datasets/history", status_code=201)
def from_history(request: Request, session: SessionDep):
    return import_history(session, request.app.state.settings)


@router.post("/datasets/demo", status_code=201)
def from_demo(request: Request, session: SessionDep):
    settings = request.app.state.settings
    if settings.market_provider != "demo":
        raise HTTPException(409, "合成实验集仅在隔离演示模式提供")
    return store_dataset(
        session, settings, demo_frame(), "合成八证券实验集", "demo:synthetic", "raw", "manual"
    )


@router.post("/runs", status_code=202)
def create_run(payload: ExperimentInput, request: Request, session: SessionDep):
    return enqueue_experiment(session, request.app.state.settings, payload)


@router.get("/runs")
def runs(request: Request, session: SessionDep):
    rows = session.scalars(
        select(QuantRun)
        .where(QuantRun.mode == request.app.state.settings.market_provider)
        .order_by(QuantRun.created_at.desc())
        .limit(50)
    ).all()
    return {"items": [run_view(row) for row in rows]}


@router.get("/runs/{identifier}")
def experiment(identifier: str, request: Request, session: SessionDep):
    return run_view(get_run(session, request.app.state.settings, identifier), True)


@router.post("/runs/{identifier}/cancel")
def cancel(identifier: str, request: Request, session: SessionDep):
    return cancel_experiment(session, get_run(session, request.app.state.settings, identifier))


def checked_artifact(request, session, identifier, filename):
    settings = request.app.state.settings
    row = get_run(session, settings, identifier)
    if row.status != "succeeded":
        raise HTTPException(409, "实验尚未成功完成")
    path = artifact_path(settings, settings.market_provider, identifier, filename)
    expected = row.result.get("artifacts", {}).get(filename)
    if (
        not path.exists()
        or not expected
        or hashlib.sha256(path.read_bytes()).hexdigest() != expected
    ):
        raise HTTPException(409, "实验产物缺失或已变化，拒绝读取")
    return path


@router.get("/runs/{identifier}/predictions")
def predictions(
    identifier: str, request: Request, session: SessionDep, page: Annotated[int, Query(ge=1)] = 1
):
    path = checked_artifact(request, session, identifier, "predictions.parquet")
    with duckdb.connect(config={"threads": 1}) as db:
        count = db.execute("SELECT count(*) FROM read_parquet(?)", [str(path)]).fetchone()[0]
        frame = (
            db.execute(
                "SELECT * FROM read_parquet(?) ORDER BY date DESC, symbol LIMIT 50 OFFSET ?",
                [str(path), (page - 1) * 50],
            )
            .to_arrow_table()
            .to_pandas()
        )
    return {"total": count, "items": frame.to_dict("records")}


@router.get("/runs/{identifier}/artifacts/{filename}")
def artifact(
    identifier: str,
    filename: Literal["predictions.parquet", "models.json"],
    request: Request,
    session: SessionDep,
):
    path = checked_artifact(request, session, identifier, filename)
    return FileResponse(path, filename=f"{identifier}-{filename}")
