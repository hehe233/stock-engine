"""持仓是用户提供的剩余数量快照。程序计算估值与条件，不连接券商或下单。"""

import csv
import io
from decimal import Decimal
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.db import MarketSnapshot, PositionLot, ServiceState
from app.market.calendar import market_session
from app.portfolio.schemas import PositionInput
from app.shared.time import SHANGHAI, as_utc, utc_now

positions_lock = Lock()

CSV_COLUMNS = [
    "symbol",
    "name",
    "asset_type",
    "quantity",
    "cost_price",
    "acquired_on",
    "settlement",
    "note",
]


def lot_view(row):
    result = {key: getattr(row, key) for key in PositionInput.model_fields}
    return {
        **result,
        "id": row.id,
        "cost_price": str(row.cost_price),
        "acquired_on": row.acquired_on.isoformat(),
        "updated_at": as_utc(row.updated_at).isoformat(),
    }


def preview_csv(content):
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    if reader.fieldnames != CSV_COLUMNS:
        raise HTTPException(422, "CSV 表头或顺序不正确，请下载模板；文件使用 UTF-8 编码")
    rows, errors = [], []
    for index, row in enumerate(reader, 2):
        if index > 501:
            raise HTTPException(422, "一次最多导入 500 行")
        try:
            rows.append(PositionInput.model_validate(row).model_dump(mode="json"))
        except ValidationError as exc:
            fields = ", ".join(
                str(err["loc"][0]) if err["loc"] else "行内容" for err in exc.errors()
            )
            errors.append({"line": index, "message": f"请检查字段：{fields}"})
    if not rows and not errors:
        raise HTTPException(422, "CSV 没有持仓行")
    return {"rows": rows, "errors": errors, "valid": not errors, "count": len(rows)}


def lot_key(row):
    return (
        row.symbol,
        row.asset_type,
        row.quantity,
        Decimal(row.cost_price),
        row.acquired_on,
        row.settlement,
    )


def import_lots(session, rows, mode):
    """Own deduplication, capacity validation and the complete import transaction."""
    with positions_lock:
        existing = session.scalars(select(PositionLot).where(PositionLot.mode == mode)).all()
        known, inserted, skipped = {lot_key(row) for row in existing}, 0, 0
        for data in rows:
            if mode == "public" and data.symbol.startswith("DEMO"):
                raise HTTPException(422, "公开模式不能导入 DEMO 持仓")
            key = lot_key(data)
            if key in known:
                skipped += 1
                continue
            known.add(key)
            session.add(PositionLot(id=str(uuid4()), mode=mode, **data.model_dump()))
            inserted += 1
        if len(existing) + inserted > 2000:
            raise HTTPException(422, "单机版本最多保存 2000 笔持仓")
        session.commit()
        return {"inserted": inserted, "skipped": skipped}


def sellable_quantity(row, today, dates):
    if row.settlement == "unknown":
        return None, "ETF 交易制度未确认，无法估计可卖数量"
    if row.acquired_on > today:
        return None, "持仓日期晚于分析日期"
    if row.settlement == "T0":
        return row.quantity, "按用户确认的 T+0 制度估计，仍以券商可卖为准"
    if row.acquired_on == today:
        return 0, "今日买入的普通 A 股 / T+1 ETF 当日不可卖"
    # 必须看到买入日之后、今日之前或当日的真实交易日，不能把次日等同于下个交易日。
    if dates and min(dates) <= row.acquired_on.isoformat() and max(dates) >= today.isoformat():
        after = [day for day in dates if row.acquired_on.isoformat() < day <= today.isoformat()]
        return (row.quantity if after else 0), "按已覆盖交易日历估计，券商余额为准"
    return None, "交易日历未覆盖持仓至今日，T+1 可卖数量未知"


def portfolio_view(session, mode, symbol=None, snapshot_override=None):
    today = utc_now().astimezone(SHANGHAI).date()
    calendar = session.get(ServiceState, "calendar")
    dates = calendar.value.get("dates", []) if calendar else []
    lots = session.scalars(
        select(PositionLot).where(PositionLot.mode == mode).order_by(PositionLot.updated_at.desc())
    ).all()
    quote_map = {}
    for asset in ("stock", "etf"):
        snap = session.scalar(
            select(MarketSnapshot)
            .where(
                MarketSnapshot.asset_type == asset,
                MarketSnapshot.source == "demo"
                if mode == "demo"
                else MarketSnapshot.source != "demo",
            )
            .order_by(MarketSnapshot.fetched_at.desc())
            .limit(1)
        )
        if snap:
            for row in snap.quotes:
                quote_map[(asset, row["symbol"])] = (row, snap)
    if snapshot_override is not None:
        for row in snapshot_override.quotes:
            quote_map[(snapshot_override.asset_type, row["symbol"])] = (row, snapshot_override)
    items, total_cost, known_value = [], Decimal(0), Decimal(0)
    unknown = 0
    for lot in lots:
        quote, snapshot = quote_map.get((lot.asset_type, lot.symbol), (None, None))
        cost = lot.cost_price * lot.quantity
        total_cost += cost
        price = Decimal(str(quote["price"])) if quote and quote.get("price") else None
        value = price * lot.quantity if price is not None else None
        if value is None:
            unknown += 1
        else:
            known_value += value
        available, reason = sellable_quantity(lot, today, dates)
        conditions = [reason]
        if price is None:
            conditions.append("无对应行情，无法估值；不能将缺失价格当作零")
        elif price < lot.cost_price:
            conditions.append("当前参考价低于录入成本；核验仓位、流动性与自己的止损条件")
        if quote and (quote.get("change_pct") or 0) >= 9:
            conditions.append("涨幅较大，卖出可成交性不能由当前价格推断")
        if quote and not quote.get("quote_time"):
            conditions.append("源时间未知，盈亏仅为参考估算")
        stale = (
            snapshot is not None and (utc_now() - as_utc(snapshot.fetched_at)).total_seconds() > 600
        )
        if stale:
            conditions.append("参考行情采集已超过两个周期")
        items.append(
            {
                **lot_view(lot),
                "price": float(price) if price is not None else None,
                "cost_yuan": float(cost),
                "value_yuan": float(value) if value is not None else None,
                "pnl_yuan": float(value - cost) if value is not None else None,
                "pnl_pct": float((value / cost - 1) * 100) if value is not None else None,
                "sellable": available,
                "conditions": conditions,
                "quote_time": quote.get("quote_time") if quote else None,
                "quote_snapshot_id": snapshot.id if snapshot else None,
                "fetched_at": as_utc(snapshot.fetched_at).isoformat() if snapshot else None,
            }
        )
    exposures = {}
    for item in items:
        key = (item["asset_type"], item["symbol"])
        exposures[key] = exposures.get(key, 0) + (item["value_yuan"] or 0)
    for item in items:
        item["weight_pct"] = (
            round(exposures[(item["asset_type"], item["symbol"])] / float(known_value) * 100, 2)
            if not unknown and known_value > 0
            else None
        )
        if item["weight_pct"] is not None and item["weight_pct"] >= 30:
            item["conditions"].append("该证券合计占已录入证券市值至少 30%；不含现金与未录入资产")
    if symbol:
        # 集中度先按完整账本计算，再限制发送给模型的明细；不能把单证券筛选结果当成 100% 仓位。
        items = [item for item in items if item["symbol"] == symbol]
        selected = [lot for lot in lots if lot.symbol == symbol]
        total_cost = sum((lot.cost_price * lot.quantity for lot in selected), Decimal(0))
        known_value = sum(
            (Decimal(str(item["value_yuan"])) for item in items if item["value_yuan"] is not None),
            Decimal(0),
        )
        unknown = sum(item["value_yuan"] is None for item in items)
    return {
        "items": items,
        "is_demo": mode == "demo",
        "as_of": utc_now().isoformat(),
        "session": market_session(utc_now(), dates),
        "unknown_price_count": unknown,
        "cost_yuan": float(total_cost),
        "known_value_yuan": float(known_value),
        "pnl_yuan": float(known_value - total_cost) if not unknown else None,
        "warnings": [
            "剩余持仓由用户录入，不连接券商。导入相同代码、日期、数量、成本和制度的重复行会跳过。",
            "参考盈亏不另扣佣金税费；可卖估计不等于券商可卖余额，不保证可成交。",
            "ETF 的交易制度必须按具体产品确认，不能仅凭 ETF 类别推断 T+0。",
        ],
    }


def update_lot(session, lot_id: str, payload: PositionInput, mode: str):
    with positions_lock:
        row = session.get(PositionLot, lot_id)
        if row is None or row.mode != mode:
            raise HTTPException(404, "持仓不存在")
        if mode == "public" and payload.symbol.startswith("DEMO"):
            raise HTTPException(422, "公开模式不支持演示持仓")
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        row.updated_at = utc_now()
        session.commit()
    return {"updated": True}


def delete_lot(session, lot_id: str, mode: str):
    with positions_lock:
        row = session.get(PositionLot, lot_id)
        if row is None or row.mode != mode:
            raise HTTPException(404, "持仓不存在")
        session.delete(row)
        session.commit()
    return {"deleted": True}
