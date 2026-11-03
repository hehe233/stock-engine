"""研究采集队列、不可变证据和历史描述统计。网络请求始终在 API 之外执行。"""

from collections import Counter, defaultdict
from datetime import date, timedelta
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.db import DataRequest, QuantDataset, QuantRun, ResearchSnapshot
from app.providers.base import ProviderError
from app.providers.research import fetch_research
from app.research_catalog import HISTORY_CASES, history_case
from app.research_schemas import FetchRequest
from app.shared.time import SHANGHAI, as_utc, utc_now

admission_lock = Lock()


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


def enqueue(session, query, settings):
    query = checked_query(query, settings.market_provider)
    key = query_key(query, settings.market_provider)
    with admission_lock:
        previous = session.scalar(
            select(DataRequest)
            .where(DataRequest.key == key)
            .order_by(DataRequest.created_at.desc())
            .limit(1)
        )
        if previous and (
            previous.status in {"queued", "running"}
            or (utc_now() - as_utc(previous.created_at)).total_seconds() < 300
        ):
            return request_view(previous)
        pending = session.scalar(
            select(func.count())
            .select_from(DataRequest)
            .where(DataRequest.status.in_(["queued", "running"]))
        )
        if pending >= 20:
            raise HTTPException(429, "数据采集队列已满，请稍后再试")
        row = DataRequest(
            id=str(uuid4()),
            key=key,
            mode=settings.market_provider,
            params=query.model_dump(mode="json"),
        )
        session.add(row)
        session.commit()
        return request_view(row)


def store_snapshot(session, query, mode, payload):
    row = ResearchSnapshot(
        id=str(uuid4()),
        key=query_key(query, mode),
        kind=query.kind,
        mode=mode,
        query_date=query.date,
        data_date=date.fromisoformat(payload["data_date"]) if payload.get("data_date") else None,
        source=payload["source"],
        observed_at=utc_now(),
        rows=payload["rows"],
        details=payload["details"],
    )
    session.add(row)
    session.flush()
    return row


def process_one(sessions, settings):
    with sessions() as session:
        row = session.scalar(
            select(DataRequest)
            .where(DataRequest.status == "queued", DataRequest.mode == settings.market_provider)
            .order_by(DataRequest.created_at)
            .limit(1)
        )
        if row is None:
            return
        result = session.execute(
            update(DataRequest)
            .where(DataRequest.id == row.id, DataRequest.status == "queued")
            .values(status="running", updated_at=utc_now())
        )
        if result.rowcount != 1:
            session.rollback()
            return
        session.commit()
        request_id, params, mode = row.id, row.params, row.mode
    try:
        query = FetchRequest.model_validate(params)
        payload = fetch_research(
            query.model_dump(mode="json"), mode, settings.provider_timeout_seconds
        )
        with sessions() as session:
            snapshot = store_snapshot(session, query, mode, payload)
            row = session.get(DataRequest, request_id)
            row.status, row.snapshot_id, row.updated_at = "succeeded", snapshot.id, utc_now()
            session.commit()
    except Exception as exc:
        with sessions() as session:
            row = session.get(DataRequest, request_id)
            row.status, row.updated_at = "failed", utc_now()
            row.error = (
                str(exc)[:500]
                if isinstance(exc, ProviderError)
                else f"采集失败（{type(exc).__name__}）；保留旧快照"
            )
            session.commit()


def recover_requests(sessions):
    # 只在取得单 worker 文件锁之后执行；旧进程退出后不留永久 running。
    with sessions() as session:
        session.execute(
            update(DataRequest)
            .where(DataRequest.status == "running")
            .values(status="queued", updated_at=utc_now(), error="上次采集中断，已重新排队")
        )
        session.commit()


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


def history_statistics(rows):
    """按同一标的同一年全部滚动窗口挑选强/弱对照；不是可成交策略或独立样本。"""
    windows = []
    for i in range(len(rows) - 20):
        segment = rows[i : i + 21]
        peak, drawdown = segment[0]["close"], 0.0
        for row in segment:
            peak = max(peak, row["close"])
            drawdown = min(drawdown, row["close"] / peak - 1)
        windows.append(
            {
                "start": segment[0]["date"],
                "end": segment[-1]["date"],
                "return_pct": round((segment[-1]["close"] / segment[0]["close"] - 1) * 100, 2),
                "drawdown_pct": round(drawdown * 100, 2),
            }
        )
    positive = [row for row in windows if row["return_pct"] > 0]
    negative = [row for row in windows if row["return_pct"] < 0]
    return {
        "bars": len(rows),
        "window_count": len(windows),
        "positive_count": len(positive),
        "negative_count": len(negative),
        "strong": max(positive, key=lambda row: row["return_pct"]) if positive else None,
        "failure": min(negative, key=lambda row: row["return_pct"]) if negative else None,
        "first_date": rows[0]["date"] if rows else None,
        "last_date": rows[-1]["date"] if rows else None,
    }


def history_list(session, settings):
    items = []
    for case in HISTORY_CASES:
        query = checked_query(
            FetchRequest(kind="history", date=date.fromisoformat(case["end"]), case_id=case["id"]),
            settings.market_provider,
        )
        data = dataset(session, query, settings)
        snapshot = latest_snapshot(session, query_key(query, settings.market_provider))
        items.append(
            {
                **case,
                "request": data["request"],
                "snapshot": snapshot_view(snapshot, False) if snapshot else None,
                "statistics": history_statistics(snapshot.rows) if snapshot else None,
            }
        )
    return {
        "items": items,
        "warnings": [
            "人工挑选的十年观察目录，不是完整妖股名录；名称为观察期常用名称。",
            "强势/失败窗口来自同一证券同一年度，窗口重叠，不能用比例当作胜率或妖股概率。",
            "缺少退市和全市场对照，存在幸存者与事后选择偏差；未取到日线时不生成统计。",
        ],
    }


def frozen_context(session, symbol, mode, cutoff, market_day):
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


def bootstrap_demo(sessions, settings):
    today = utc_now().astimezone(SHANGHAI).date()
    for kind in ("ladder", "dragon", "flow", "notices"):
        query = FetchRequest(kind=kind, date=today)
        with sessions() as session:
            if not latest_snapshot(session, query_key(query, "demo")):
                store_snapshot(
                    session, query, "demo", fetch_research(query.model_dump(mode="json"), "demo", 5)
                )
                session.commit()


def schedule_research(sessions, settings, calendar_dates):
    now = utc_now().astimezone(SHANGHAI)
    today = now.date()
    if today.weekday() >= 5 or not 9 <= now.hour <= 20:
        return
    prior = [
        value
        for value in calendar_dates
        if (today - timedelta(days=10)).isoformat() <= value < today.isoformat()
    ]
    disclosure_day = today if now.hour >= 16 else date.fromisoformat(max(prior)) if prior else today
    kinds = ("ladder", "flow", "dragon", "notices")
    for kind in kinds:
        query = FetchRequest(kind=kind, date=disclosure_day if kind == "dragon" else today)
        with sessions() as session:
            try:
                enqueue(session, query, settings)
            except HTTPException:
                return
