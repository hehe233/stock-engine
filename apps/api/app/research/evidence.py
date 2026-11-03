from datetime import timedelta

from sqlalchemy import select

from app.db import ResearchSnapshot
from app.research.history import history_statistics
from app.research.queries import snapshot_view
from app.shared.time import as_utc


def research_evidence(session, symbol, mode, cutoff, market_day):
    context = {}
    for kind in ("ladder", "dragon", "seats", "flow", "notices"):
        row = session.scalar(
            select(ResearchSnapshot)
            .where(
                ResearchSnapshot.kind == kind,
                ResearchSnapshot.mode == mode,
                ResearchSnapshot.observed_at <= cutoff,
                ResearchSnapshot.query_date <= market_day,
                ResearchSnapshot.query_date >= market_day - timedelta(days=7),
                # 席位批次属于单只证券，不能选到另一只证券的最新席位后误报空结果。
                ResearchSnapshot.key.contains(f":{symbol}:") if kind == "seats" else True,
            )
            .order_by(ResearchSnapshot.query_date.desc(), ResearchSnapshot.observed_at.desc())
            .limit(1)
        )
        if row:
            evidence = snapshot_view(row, False)
            evidence["rows"] = [r for r in row.rows if r.get("symbol") == symbol][:20]
            # SQLAlchemy datetime/date 转成 JSON 原生字符串后才能进入任务 JSON 列。
            for key in ("query_date", "data_date", "observed_at"):
                evidence[key] = evidence[key].isoformat() if evidence[key] else None
            evidence["meaning"] = "未出现只表示本来源本批未收录，不能推断没有事件"
            context[kind] = evidence
        else:
            context[kind] = {"available": False, "reason": "提交时缺少日期匹配且已入库的研究证据"}
    historical = session.scalars(
        select(ResearchSnapshot)
        .where(
            ResearchSnapshot.kind == "history",
            ResearchSnapshot.mode == mode,
            ResearchSnapshot.observed_at <= cutoff,
            ResearchSnapshot.query_date <= market_day,
        )
        .order_by(ResearchSnapshot.observed_at.desc())
    ).all()
    for row in historical:
        if f":{symbol}:" in row.key:
            context["history"] = {
                "source": row.source,
                "snapshot_id": row.id,
                "statistics": history_statistics(row.rows),
                "details": row.details,
                "observed_at": as_utc(row.observed_at).isoformat(),
            }
            break
    return context
