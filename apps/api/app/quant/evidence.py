from sqlalchemy import select

from app.db import QuantDataset, QuantRun


def quant_evidence(session, symbol, mode, cutoff, market_day):
    context = {}
    experiments = session.execute(
        select(QuantRun, QuantDataset)
        .join(QuantDataset, QuantRun.dataset_id == QuantDataset.id)
        .where(QuantRun.mode == mode, QuantRun.status == "succeeded", QuantRun.updated_at <= cutoff)
        .order_by(QuantRun.updated_at.desc())
        .limit(20)
    ).all()
    for run, dataset in experiments:
        folds = run.result.get("folds", [])
        if (
            any(item["symbol"] == symbol for item in dataset.details.get("symbols", []))
            and folds
            and run.result.get("evaluation_end", "9999-12-31") <= market_day.isoformat()
        ):
            context["quant"] = {
                "experiment_id": run.id,
                "dataset_id": dataset.id,
                "dataset_checksum": dataset.checksum,
                "target": run.result["target"],
                "metrics": run.result["metrics"],
                "research_only": True,
                "meaning": "历史样本外实验摘要，不是该证券当前概率；数据范围与时点覆盖尚未核验",
                "warnings": run.result.get("warnings", []),
            }
            break
    return context
