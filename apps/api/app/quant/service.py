"""实验任务持久化协调；HTTP 只入队，独立进程承担训练与回测。"""

import hashlib
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.db import QuantDataset, QuantRun
from app.quant.artifacts import ArtifactWrite, load_frame
from app.quant.schemas import ExperimentInput
from app.shared.time import as_utc, utc_now

quant_lock = Lock()


def get_dataset(session, settings, identifier):
    row = session.get(QuantDataset, identifier)
    if row is None or row.mode != settings.market_provider:
        raise HTTPException(404, "数据集不存在")
    return row


def get_run(session, settings, identifier):
    row = session.get(QuantRun, identifier)
    if row is None or row.mode != settings.market_provider:
        raise HTTPException(404, "实验不存在")
    return row


def run_view(row, full=False):
    return {
        "id": row.id,
        "dataset_id": row.dataset_id,
        "status": row.status,
        "params": row.params,
        "created_at": as_utc(row.created_at),
        "updated_at": as_utc(row.updated_at),
        "error": row.error,
        "is_demo": row.mode == "demo",
        "cancel_requested": row.cancel_requested,
        "result": row.result
        if full
        else {
            key: row.result[key]
            for key in ("stage", "target", "metrics", "dataset_checksum")
            if key in row.result
        },
    }


def enqueue_experiment(session, settings, payload):
    dataset = get_dataset(session, settings, payload.dataset_id)
    with quant_lock:
        pending = session.scalar(
            select(func.count())
            .select_from(QuantRun)
            .where(QuantRun.status.in_(["queued", "running"]))
        )
        if pending >= 5:
            raise HTTPException(429, "实验队列最多 5 个待处理任务")
        row = QuantRun(
            id=str(uuid4()),
            dataset_id=dataset.id,
            mode=settings.market_provider,
            params=payload.model_dump(),
            result={"dataset_checksum": dataset.checksum},
        )
        session.add(row)
        session.commit()
        return run_view(row, True)


def claim_experiment(sessions, settings):
    with sessions() as session:
        identifier = session.scalar(
            select(QuantRun.id)
            .where(QuantRun.status == "queued", QuantRun.mode == settings.market_provider)
            .order_by(QuantRun.created_at)
            .limit(1)
        )
        if identifier is None:
            return None
        claimed = session.execute(
            update(QuantRun)
            .where(QuantRun.id == identifier, QuantRun.status == "queued")
            .values(status="running", updated_at=utc_now())
        )
        session.commit()
        return identifier if claimed.rowcount == 1 else None


def fail_experiment(sessions, identifier, message, cancelled=False):
    with sessions() as session:
        row = session.get(QuantRun, identifier)
        if row and row.status == "running":
            row.status = "cancelled" if cancelled or row.cancel_requested else "failed"
            row.error, row.updated_at = message, utc_now()
            session.commit()


def recover_experiments(sessions):
    # 仅在 worker 单实例锁内执行。训练不做隐式重试，避免用户看不见的重复实验。
    with sessions() as session:
        session.execute(
            update(QuantRun)
            .where(QuantRun.status == "running")
            .values(
                status="failed", error="上次实验进程中断，请用原参数重新运行", updated_at=utc_now()
            )
        )
        session.commit()


def cancel_experiment(session, row):
    if row.status in {"queued", "running"}:
        row.cancel_requested = True
        if row.status == "queued":
            row.status = "cancelled"
        row.updated_at = utc_now()
        session.commit()
    return run_view(row, True)


def execute_experiment(sessions, settings, identifier):
    from app.quant.engine import train_experiment

    try:
        with sessions() as session:
            run = session.get(QuantRun, identifier)
            if run is None or run.status != "running":
                return
            dataset = get_dataset(session, settings, run.dataset_id)
            params = ExperimentInput.model_validate(run.params)
            frame = load_frame(settings, dataset)
            details, checksum = dataset.details, dataset.checksum

        def progress(stage):
            with sessions() as session:
                row = session.get(QuantRun, identifier)
                if row.cancel_requested:
                    raise InterruptedError("实验已取消")
                row.result = {"stage": stage, "dataset_checksum": checksum}
                row.updated_at = utc_now()
                session.commit()

        result, predictions, models = train_experiment(frame, params, details, progress)
        with ArtifactWrite(settings, settings.market_provider, identifier) as files:
            artifacts = {
                "predictions.parquet": files.frame("predictions.parquet", predictions),
                "models.json": files.models(models),
            }
            code = b"".join(
                (Path(__file__).parent / name).read_bytes()
                for name in (
                    "engine.py",
                    "features.py",
                    "backtest.py",
                    "datasets.py",
                    "artifacts.py",
                )
            )
            result.update(
                {
                    "dataset_checksum": checksum,
                    "code_sha256": hashlib.sha256(code).hexdigest(),
                    "artifacts": artifacts,
                }
            )
            with sessions() as session:
                row = session.get(QuantRun, identifier)
                if row.status == "running":
                    row.status = "cancelled" if row.cancel_requested else "succeeded"
                    row.result, row.updated_at = result, utc_now()
                    try:
                        session.commit()
                    except Exception:
                        files.preserve()
                        session.rollback()
                        stored = session.get(QuantRun, identifier)
                        if stored.result.get("artifacts") != artifacts:
                            files.discard()
                        raise
                    files.preserve()
    except InterruptedError:
        fail_experiment(sessions, identifier, "实验已取消", True)
    except ValueError as exc:
        fail_experiment(sessions, identifier, str(exc)[:500])
    except Exception as exc:
        fail_experiment(
            sessions, identifier, f"实验失败（{type(exc).__name__}），请检查数据和运行日志"
        )
