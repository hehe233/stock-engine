from uuid import uuid4

from fastapi import HTTPException

from app.db import AnalysisRun, MarketSnapshot
from app.schemas import (
    AnalysisReport,
    AnalysisRequest,
)
from app.shared.time import as_utc, utc_now


def create_rule_report(session, payload: AnalysisRequest, graph):
    """Execute the short rules workflow and commit its archived report."""
    if payload.mode != "rules":
        raise HTTPException(422, "模型分析请使用 /api/jobs 异步任务接口")
    # 使用前端实际看到的快照，避免刷新恰好发生时分析了另一个版本的数据。
    snapshot = session.get(MarketSnapshot, payload.snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="行情快照不存在，请刷新行情后重试")
    quote = next((item for item in snapshot.quotes if item["symbol"] == payload.symbol), None)
    if quote is None:
        raise HTTPException(status_code=404, detail="该快照中不存在这只股票")

    # 同步路由在线程池内运行，不阻塞 FastAPI 的事件循环。
    result = graph.invoke(
        {"quote": quote, "trace": [], "is_demo": snapshot.source == "demo"}
    )
    report = AnalysisReport(
        id=str(uuid4()),
        snapshot_id=snapshot.id,
        symbol=quote["symbol"],
        name=quote["name"],
        created_at=utc_now(),
        as_of=quote.get("quote_time")
        or (as_utc(snapshot.as_of) if snapshot.source == "demo" and snapshot.as_of else None),
        source=snapshot.source,
        is_demo=snapshot.source == "demo",
        asset_type=snapshot.asset_type,
        heat_score=result["heat_score"],
        summary=result["summary"],
        factors=result["factors"],
        risks=result["risks"],
        trace=result["trace"],
    )
    session.add(
        AnalysisRun(
            id=report.id,
            snapshot_id=snapshot.id,
            symbol=report.symbol,
            created_at=report.created_at,
            report=report.model_dump(mode="json"),
        )
    )
    session.commit()
    return report
