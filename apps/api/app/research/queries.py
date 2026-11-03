from collections import Counter, defaultdict
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.db import DataRequest, ResearchSnapshot
from app.research.catalog import HISTORY_CASES, history_case
from app.shared.time import as_utc, utc_now


def query_key(query, mode):
    # 资金只有当前观测，不把 date 当作它的源交易日。
    return f"{mode}:{query.kind}:{query.date}:{query.symbol}:{query.case_id}"


def checked_query(query, mode):
    if query.kind == "history":
        case = history_case(query.case_id)
        if case is None:
            raise HTTPException(404, "历史案例不存在")
        query = query.model_copy(
            update={"date": date.fromisoformat(case["end"]), "symbol": case["symbol"]}
        )
    if mode == "public" and query.symbol.startswith("DEMO"):
        raise HTTPException(422, "公开模式不能查询演示代码")
    return query


def latest_snapshot(session, key):
    return session.scalar(
        select(ResearchSnapshot)
        .where(ResearchSnapshot.key == key)
        .order_by(ResearchSnapshot.observed_at.desc())
        .limit(1)
    )


def request_view(row):
    return {
        "id": row.id,
        "status": row.status,
        "error": row.error,
        "updated_at": as_utc(row.updated_at),
        "snapshot_id": row.snapshot_id,
    }


def ladder_summary(rows):
    tiers, sectors = Counter(), defaultdict(list)
    for row in rows:
        if row.get("boards") is not None:
            tiers[int(row["boards"])] += 1
        sectors[row.get("sector", "未提供")].append(row)
    return {
        "tiers": [
            {"boards": key, "count": value} for key, value in sorted(tiers.items(), reverse=True)
        ],
        "sectors": sorted(
            [
                {
                    "sector": key,
                    "count": len(items),
                    "max_boards": max((r.get("boards") or 0 for r in items), default=0),
                }
                for key, items in sectors.items()
            ],
            key=lambda row: (-row["max_boards"], -row["count"]),
        ),
        "leaders": [
            r["symbol"] for r in rows if r.get("boards") and r["boards"] == max(tiers, default=0)
        ],
    }


def snapshot_view(snapshot, include_rows=True):
    return {
        "id": snapshot.id,
        "kind": snapshot.kind,
        "source": snapshot.source,
        "is_demo": snapshot.mode == "demo",
        "query_date": snapshot.query_date,
        "data_date": snapshot.data_date,
        "observed_at": as_utc(snapshot.observed_at),
        "total": len(snapshot.rows),
        "details": snapshot.details,
        "rows": snapshot.rows if include_rows else [],
        "stale": (utc_now() - as_utc(snapshot.observed_at)).total_seconds() > 600,
    }


def dataset(session, query, settings, search="", page=1, page_size=50):
    query = checked_query(query, settings.market_provider)
    key = query_key(query, settings.market_provider)
    snapshot = latest_snapshot(session, key)
    request = session.scalar(
        select(DataRequest)
        .where(DataRequest.key == key)
        .order_by(DataRequest.created_at.desc())
        .limit(1)
    )
    result = {
        "snapshot": None,
        "request": request_view(request) if request else None,
        "summary": {},
        "total": 0,
        "page": page,
        "page_size": page_size,
    }
    if snapshot:
        rows = snapshot.rows
        if query.kind == "ladder":
            result["summary"] = ladder_summary(rows)
            prior = session.scalar(
                select(ResearchSnapshot)
                .where(
                    ResearchSnapshot.kind == "ladder",
                    ResearchSnapshot.mode == snapshot.mode,
                    ResearchSnapshot.source == snapshot.source,
                    ResearchSnapshot.query_date < snapshot.query_date,
                    ResearchSnapshot.query_date >= snapshot.query_date - timedelta(days=10),
                )
                .order_by(ResearchSnapshot.query_date.desc(), ResearchSnapshot.observed_at.desc())
                .limit(1)
            )
            result["summary"]["comparison_date"] = prior.query_date.isoformat() if prior else None
            prior_sectors = (
                Counter(r.get("sector", "未提供") for r in prior.rows) if prior else None
            )
            for sector in result["summary"]["sectors"]:
                sector["previous_count"] = (
                    prior_sectors.get(sector["sector"], 0) if prior_sectors is not None else None
                )
                sector["count_change"] = (
                    sector["count"] - sector["previous_count"]
                    if sector["previous_count"] is not None
                    else None
                )
            rows = sorted(
                rows,
                key=lambda row: (row.get("boards") or 0, row.get("seal_yuan") or 0),
                reverse=True,
            )
        if query.kind == "flow":
            prior = session.scalar(
                select(ResearchSnapshot)
                .where(
                    ResearchSnapshot.key == snapshot.key,
                    ResearchSnapshot.source == snapshot.source,
                    ResearchSnapshot.observed_at < snapshot.observed_at,
                )
                .order_by(ResearchSnapshot.observed_at.desc())
                .limit(1)
            )
            previous = {row["symbol"]: row.get("main_yuan") for row in prior.rows} if prior else {}
            result["summary"]["previous_observed_at"] = (
                as_utc(prior.observed_at).isoformat() if prior else None
            )
            rows = [
                {
                    **row,
                    "change_since_previous_yuan": row["main_yuan"] - previous[row["symbol"]]
                    if row.get("main_yuan") is not None and previous.get(row["symbol"]) is not None
                    else None,
                }
                for row in rows
            ]
            rows = sorted(
                rows,
                key=lambda row: (
                    row.get("main_yuan") if row.get("main_yuan") is not None else float("-inf")
                ),
                reverse=True,
            )
        filtered = [
            row for row in rows if search.lower() in " ".join(str(v) for v in row.values()).lower()
        ]
        result["total"] = len(filtered)
        result["snapshot"] = snapshot_view(snapshot, False)
        result["snapshot"]["rows"] = filtered[(page - 1) * page_size : page * page_size]
    return result


def archived_history(session, mode):
    """Read the latest archived batch per catalog case without exposing ORM objects."""
    batches = []
    for case in HISTORY_CASES:
        snap = session.scalar(
            select(ResearchSnapshot)
            .where(
                ResearchSnapshot.kind == "history",
                ResearchSnapshot.mode == mode,
                ResearchSnapshot.key.endswith(":" + case["id"]),
            )
            .order_by(ResearchSnapshot.observed_at.desc())
            .limit(1)
        )
        if snap:
            batches.append({"snapshot_id": snap.id, "symbol": case["symbol"], "rows": snap.rows})
    return batches
