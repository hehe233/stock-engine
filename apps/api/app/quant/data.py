"""不可变 Parquet 数据版本与 DuckDB 查询。所有文件名由服务端 UUID 生成。"""

import hashlib
import io
from pathlib import Path
from uuid import uuid4

import duckdb
import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select

from app.db import QuantDataset, ResearchSnapshot
from app.research_catalog import HISTORY_CASES
from app.shared.securities import normalize_symbol
from app.shared.time import SHANGHAI, as_utc, utc_now

REQUIRED = ["symbol", "date", "open", "high", "low", "close"]
OPTIONAL = [
    "volume",
    "prev_close",
    "upper_limit",
    "lower_limit",
    "tradable",
    "available_at",
    "listed_on",
    "delisted_on",
]
NUMERIC = ["open", "high", "low", "close", "volume", "prev_close", "upper_limit", "lower_limit"]


def artifact_path(settings, mode, identifier, filename):
    # identifier 只由数据库记录提供；公开接口不接受文件路径或任意下载文件名。
    from uuid import UUID

    UUID(identifier)
    if mode not in {"public", "demo"} or filename not in {
        "bars.parquet",
        "predictions.parquet",
        "models.json",
    }:
        raise ValueError("无效实验文件")
    return Path(settings.quant_artifact_dir).resolve() / mode / identifier / filename


def validate_frame(frame, mode):
    if not set(REQUIRED).issubset(frame.columns):
        raise ValueError("CSV 缺少必需列：symbol,date,open,high,low,close")
    if not 30 <= len(frame) <= 100000:
        raise ValueError("数据集需要 30—100000 行日线")
    frame = frame.copy()
    for column in OPTIONAL:
        if column not in frame:
            frame[column] = None
    frame = frame[REQUIRED + OPTIONAL]
    frame["symbol"] = frame.symbol.astype(str).str.strip()
    if mode == "public":
        frame["symbol"] = frame.symbol.map(lambda value: normalize_symbol(value, "stock"))
    frame["date"] = pd.to_datetime(frame.date, format="%Y-%m-%d", errors="raise").dt.strftime(
        "%Y-%m-%d"
    )
    if (
        frame.date.isna().any()
        or frame.date.max() > utc_now().astimezone(SHANGHAI).date().isoformat()
    ):
        raise ValueError("交易日期缺失或位于未来")
    if frame.duplicated(["symbol", "date"]).any():
        raise ValueError("同一证券同一交易日重复，拒绝覆盖或自动合并")
    for column in NUMERIC:
        frame[column] = pd.to_numeric(frame[column].replace("", None), errors="raise")
        if np.isinf(frame[column]).any():
            raise ValueError("数值不能为无穷大")
    prices = frame[["open", "high", "low", "close"]]
    if prices.isna().any().any() or (prices <= 0).any().any():
        raise ValueError("OHLC 必须为完整的正数")
    if ((frame.high < prices.max(axis=1)) | (frame.low > prices.min(axis=1))).any():
        raise ValueError("OHLC 高低价关系无效")
    if (frame.volume.dropna() < 0).any() or (frame.prev_close.dropna() <= 0).any():
        raise ValueError("成交量或前收盘价无效")
    if (
        (frame.upper_limit <= 0)
        | (frame.lower_limit <= 0)
        | (frame.upper_limit < frame.lower_limit)
    ).any():
        raise ValueError("实际涨跌停价无效")
    status = frame.tradable.fillna("").astype(str).str.lower().str.strip()
    if not status.isin(["", "1", "0", "true", "false", "1.0", "0.0"]).all():
        raise ValueError("tradable 只接受 true/false/1/0，空值表示未知")
    frame["tradable"] = status.map(
        {"true": True, "false": False, "1": True, "0": False, "1.0": True, "0.0": False}
    )
    availability = frame.available_at.replace("", None)
    # 不接受没有时区的披露时间，避免把本地时间误读为 UTC。
    for value in availability.dropna():
        if pd.Timestamp(value).tzinfo is None:
            raise ValueError("available_at 必须带时区，例如 2025-01-02T16:00:00+08:00")
    frame["available_at"] = pd.to_datetime(availability, utc=True, errors="raise")
    if (frame.available_at > pd.Timestamp(utc_now())).any():
        raise ValueError("available_at 不能位于未来")
    for column in ("listed_on", "delisted_on"):
        frame[column] = pd.to_datetime(
            frame[column].replace("", None), format="%Y-%m-%d", errors="raise"
        ).dt.strftime("%Y-%m-%d")
    if (
        (frame.listed_on.notna() & (frame.date < frame.listed_on))
        | (frame.delisted_on.notna() & (frame.date > frame.delisted_on))
    ).any():
        raise ValueError("日线日期超出声明的上市/退市区间")
    for _, group in frame.groupby("symbol"):
        if any(group[c].dropna().nunique() > 1 for c in ("listed_on", "delisted_on")):
            raise ValueError("同证券上市/退市日期声明冲突")
    return frame.sort_values(["symbol", "date"]).reset_index(drop=True)


def parse_csv(content, mode):
    try:
        return validate_frame(
            pd.read_csv(io.StringIO(content.lstrip("\ufeff")), dtype=str, keep_default_na=False),
            mode,
        )
    except (ValueError, TypeError, KeyError) as exc:
        # 不回显整个 CSV 或 pandas 原始错误（可能包含用户数据）。
        if isinstance(exc, ValueError) and str(exc).startswith(
            (
                "CSV",
                "数据集",
                "交易日期",
                "同一证券",
                "数值",
                "OHLC",
                "成交量",
                "实际",
                "tradable",
                "available_at",
                "日线",
                "同证券",
            )
        ):
            raise HTTPException(422, str(exc)) from exc
        raise HTTPException(
            422, "CSV 字段格式无效，请按模板填写日期、价格、证券代码和交易状态"
        ) from exc


def audit_frame(frame, adjustment, selection):
    executable = (
        frame[["volume", "prev_close", "upper_limit", "lower_limit", "tradable"]]
        .notna()
        .all(axis=1)
    )
    symbols = []
    for symbol, group in frame.groupby("symbol"):
        symbols.append(
            {
                "symbol": symbol,
                "rows": len(group),
                "first": group.date.min(),
                "last": group.date.max(),
                "listed_on": next(iter(group.listed_on.dropna()), None),
                "delisted_on": next(iter(group.delisted_on.dropna()), None),
            }
        )
    warnings = [
        "证券范围、交易日历及退市覆盖尚未与交易所历史主表核验；结构校验通过不等于完整覆盖。",
        "日线回测无法还原委托队列、逐笔撮合或实际成交；禁止当作实盘收益保证。",
    ]
    if selection == "manual":
        warnings.append("人工/精选证券范围有事后选择和幸存者偏差，不能外推全市场。")
    if adjustment != "raw":
        warnings.append("前复权价格可能事后修订，仅做概率研究，交易模拟停用。")
    if not executable.all():
        warnings.append("部分日线缺成交量、实际涨跌停价或交易状态，交易模拟逐笔拒绝，不猜测制度。")
    if frame.available_at.isna().any():
        warnings.append("部分数据缺精确可见时间，按收盘后可见的研究假设处理；不是时点数据保证。")
    return {
        "rows": len(frame),
        "symbols": symbols,
        "symbol_count": len(symbols),
        "days": frame.date.nunique(),
        "first": frame.date.min(),
        "last": frame.date.max(),
        "adjustment": adjustment,
        "selection": selection,
        "executable_rows": int(executable.sum()),
        "missing_available_at": int(frame.available_at.isna().sum()),
        "coverage_verified": False,
        "level2": False,
        "warnings": warnings,
    }


def store_dataset(session, settings, frame, name, source, adjustment, selection, extra=None):
    identifier = str(uuid4())
    path = artifact_path(settings, settings.market_provider, identifier, "bars.parquet")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    frame.to_parquet(temp, index=False)
    temp.replace(path)
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    details = {**audit_frame(frame, adjustment, selection), **(extra or {})}
    row = QuantDataset(
        id=identifier,
        mode=settings.market_provider,
        name=name,
        source=source,
        checksum=checksum,
        details=details,
    )
    session.add(row)
    session.commit()
    return dataset_view(row)


def dataset_view(row):
    return {
        "id": row.id,
        "name": row.name,
        "source": row.source,
        "checksum": row.checksum,
        "is_demo": row.mode == "demo",
        "created_at": as_utc(row.created_at),
        "details": row.details,
    }


def load_frame(settings, row):
    path = artifact_path(settings, row.mode, row.id, "bars.parquet")
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != row.checksum:
        raise ValueError("数据文件缺失或哈希不匹配，请重新导入；拒绝使用变更后的数据")
    with duckdb.connect(config={"threads": 1}) as db:
        # 参数绑定文件路径；不会拼接客户端 SQL、筛选表达式或表名。
        return (
            db.execute("SELECT * FROM read_parquet(?) ORDER BY symbol, date", [str(path)])
            .to_arrow_table()
            .to_pandas()
        )


def import_history(session, settings):
    rows, references = [], []
    for case in HISTORY_CASES:
        snap = session.scalar(
            select(ResearchSnapshot)
            .where(
                ResearchSnapshot.kind == "history",
                ResearchSnapshot.mode == settings.market_provider,
                ResearchSnapshot.key.endswith(":" + case["id"]),
            )
            .order_by(ResearchSnapshot.observed_at.desc())
            .limit(1)
        )
        if snap:
            references.append(snap.id)
            for bar in snap.rows:
                if all(bar.get(c) for c in ("open", "high", "low", "close")):
                    rows.append(
                        {**{c: bar[c] for c in REQUIRED if c != "symbol"}, "symbol": case["symbol"]}
                    )
    if not rows:
        raise HTTPException(422, "尚无完整 OHLC 历史批次，请先在历史案例页获取真实日线，或导入 CSV")
    frame = validate_frame(pd.DataFrame(rows), settings.market_provider)
    return store_dataset(
        session,
        settings,
        frame,
        "P2 精选案例实验集",
        "P2:archived:tencent:qfq",
        "qfq",
        "manual",
        {"snapshot_ids": references},
    )


def demo_frame():
    """固定种子合成行情，只在 demo 模式开放；用多种趋势段检验校准闭环。"""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2022-01-03", periods=620)
    rows = []
    for stock in range(8):
        close = 10 + stock
        for i, day in enumerate(dates):
            previous = close
            trend = 0.048 if (i + stock * 7) % 80 < 18 else -0.014
            change = np.clip(trend + rng.normal(0, 0.012), -0.085, 0.085)
            opening = previous * (1 + rng.normal(0, 0.003))
            close = previous * (1 + change)
            rows.append(
                {
                    "symbol": f"DEMOQ{stock:03}",
                    "date": day.strftime("%Y-%m-%d"),
                    "open": opening,
                    "high": max(opening, close) * 1.005,
                    "low": min(opening, close) * 0.995,
                    "close": close,
                    "prev_close": previous,
                    "upper_limit": round(previous * 1.1, 2),
                    "lower_limit": round(previous * 0.9, 2),
                    "volume": int(rng.integers(1000000, 3000000)),
                    "tradable": True,
                    "available_at": day.strftime("%Y-%m-%d") + "T16:00:00+08:00",
                    "listed_on": "2020-01-01",
                }
            )
    return validate_frame(pd.DataFrame(rows), "demo")
