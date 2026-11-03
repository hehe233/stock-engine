from datetime import date

from app.research.catalog import HISTORY_CASES
from app.research.queries import checked_query, dataset, latest_snapshot, query_key, snapshot_view
from app.research.schemas import FetchRequest


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
