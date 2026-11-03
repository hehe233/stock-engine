"""研究适配器：只标准化明确的列，不让事后收益或供应商无关字段进入 Agent。"""

from datetime import date, timedelta
from urllib.parse import urlsplit

from app.providers.base import ProviderError
from app.providers.normalization import number
from app.providers.runner import run_collector
from app.research_catalog import history_case
from app.shared.securities import normalize_symbol

NOTES = {
    "ladder": (
        "来源涨停专题不含 ST、科创板及未中断连续一字板新股；"
        "连板数是来源口径，封板资金不是可成交保证。行业聚合不是板块相关性。"
    ),
    "dragon": (
        "龙虎榜是盘后披露，可能含单日/多日不同上榜原因；同一股票多原因不能重复加总。"
        "已剔除上榜后涨幅，席位不等于个人身份。"
    ),
    "seats": "买入榜/卖出榜可能出现同一席位，勿重复加总；只展示公开席位原名，不推断游资个人身份。",
    "flow": (
        "当前资金排名无完整源日期；主力为供应商按成交单分类的超大单与大单统计，"
        "不是账户资金，不能解释为真实机构净买入。金额按来源原值元展示，不乘万元。"
    ),
    "notices": "公告日期不等于精确披露时刻。标题不是全文；只展示来源链接，无法核验历史时点可见性。",
    "history": (
        "腾讯前复权日线；复权值可能事后修订。20交易日窗口仅作描述统计，"
        "不含费用、停牌成交限制和幸存者偏差修正，不是策略回测。"
    ),
}


def safe_url(value):
    text = str(value or "")
    url = urlsplit(text)
    return (
        text
        if url.scheme == "https"
        and url.hostname
        and (url.hostname == "eastmoney.com" or url.hostname.endswith(".eastmoney.com"))
        and not url.username
        else None
    )


def parse_day(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def normalize_research(kind, raw, query):
    rows, rejected = [], 0
    for index, item in enumerate(raw):
        try:
            if kind == "history":
                day, close = parse_day(item.get("date")), number(item.get("close"))
                case = history_case(query["case_id"])
                if not day or not close or close <= 0 or not case["start"] <= day <= case["end"]:
                    raise ValueError("日线无效")
                row = {
                    "date": day,
                    "close": close,
                    "open": number(item.get("open")),
                    "high": number(item.get("high")),
                    "low": number(item.get("low")),
                }
            elif kind == "seats":
                seat = item.get("交易营业部名称") or item.get("营业部名称")
                if not seat:
                    raise ValueError("席位缺失")
                row = {
                    "symbol": query["symbol"],
                    "seat": str(seat),
                    "side": item.get("方向"),
                    "reason": str(item.get("类型", "未提供")),
                    "buy_yuan": number(item.get("买入金额")),
                    "sell_yuan": number(item.get("卖出金额")),
                    "net_yuan": number(item.get("净额")),
                }
            else:
                row = {
                    "symbol": normalize_symbol(str(item.get("代码", "")), "stock"),
                    "name": str(item.get("名称", "未提供")),
                }
                if kind == "ladder":
                    boards = number(item.get("连板数"))
                    if boards is not None and (boards < 1 or boards != int(boards)):
                        raise ValueError("连板数必须为正整数")
                    row.update(
                        {
                            "boards": boards,
                            "sector": str(item.get("所属行业", "未提供")),
                            "change_pct": number(item.get("涨跌幅")),
                            "turnover_pct": number(item.get("换手率")),
                            "amount_yuan": number(item.get("成交额")),
                            "seal_yuan": number(item.get("封板资金")),
                            "break_count": number(item.get("炸板次数")),
                            "first_seal": str(item.get("首次封板时间", "未知")),
                            "last_seal": str(item.get("最后封板时间", "未知")),
                        }
                    )
                elif kind == "dragon":
                    day = parse_day(item.get("上榜日"))
                    if day != query["date"]:
                        raise ValueError("上榜日期不匹配")
                    row.update(
                        {
                            "date": day,
                            "reason": str(item.get("上榜原因", "未提供")),
                            "buy_yuan": number(item.get("龙虎榜买入额")),
                            "sell_yuan": number(item.get("龙虎榜卖出额")),
                            "net_yuan": number(item.get("龙虎榜净买额")),
                            "change_pct": number(item.get("涨跌幅")),
                        }
                    )
                elif kind == "flow":
                    row.update(
                        {
                            "main_yuan": number(item.get("今日主力净流入-净额")),
                            "main_pct": number(item.get("今日主力净流入-净占比")),
                            "super_yuan": number(item.get("今日超大单净流入-净额")),
                            "large_yuan": number(item.get("今日大单净流入-净额")),
                            "medium_yuan": number(item.get("今日中单净流入-净额")),
                            "small_yuan": number(item.get("今日小单净流入-净额")),
                            "change_pct": number(item.get("今日涨跌幅")),
                        }
                    )
                else:
                    day = parse_day(item.get("公告日期"))
                    if day != query["date"]:
                        raise ValueError("公告日期不匹配")
                    row.update(
                        {
                            "date": day,
                            "title": str(item.get("公告标题", "未提供")),
                            "category": str(item.get("公告类型", "未提供")),
                            "url": safe_url(item.get("网址")),
                        }
                    )
            row["id"] = str(index)
            rows.append(row)
        except (ValueError, TypeError):
            rejected += 1
    if raw and not rows:
        raise ProviderError("来源返回了数据，但字段或日期校验全部失败；保留原快照")
    if kind == "history":
        if len({row["date"] for row in rows}) != len(rows):
            raise ProviderError("历史日线日期重复，拒绝统计")
        rows.sort(key=lambda row: row["date"])
    return rows, rejected


def fetch_research(query, mode, timeout):
    if mode == "demo":
        return demo_research(query)
    payload = run_collector("research", "eastmoney", timeout, query)
    rows, rejected = normalize_research(query["kind"], payload["rows"], query)
    kind = query["kind"]
    return {
        "rows": rows,
        "source": payload["source"],
        "data_date": (query["date"] if rows and kind in {"dragon", "notices"} else None),
        "details": {
            "warnings": [NOTES[kind]],
            "rejected_count": rejected,
            "coverage_verified": False,
            "published_at": None,
            "empty_is_unconfirmed": not rows,
        },
    }


def demo_research(query):
    """固定、显式标记的演示证据；绝不作为公开源失败后的替代。"""
    kind = query["kind"]
    common = {"id": "0", "symbol": "DEMO001", "name": "样本·算力一号"}
    rows = {
        "ladder": [
            {
                **common,
                "boards": 3,
                "sector": "演示算力",
                "seal_yuan": 80000000,
                "amount_yuan": 1280000000,
                "break_count": 2,
                "first_seal": "093100",
                "last_seal": "142000",
            },
            {
                **common,
                "id": "1",
                "symbol": "DEMO002",
                "name": "样本·机器人",
                "boards": 1,
                "sector": "演示机器人",
            },
        ],
        "dragon": [
            {
                **common,
                "date": query["date"],
                "reason": "虚构上榜原因",
                "buy_yuan": 80000000,
                "sell_yuan": 30000000,
                "net_yuan": 50000000,
            }
        ],
        "seats": [
            {
                "id": "0",
                "symbol": query["symbol"],
                "seat": "演示营业部（虚构）",
                "side": "买入",
                "buy_yuan": 80000000,
                "sell_yuan": 30000000,
                "net_yuan": 50000000,
                "reason": "演示",
            }
        ],
        "flow": [
            {
                **common,
                "main_yuan": 50000000,
                "super_yuan": 30000000,
                "large_yuan": 20000000,
                "medium_yuan": -10000000,
                "small_yuan": -40000000,
                "main_pct": 3.9,
            }
        ],
        "notices": [
            {
                **common,
                "title": "演示风险提示公告（虚构）",
                "category": "风险提示",
                "date": query["date"],
                "url": None,
            }
        ],
    }.get(kind)
    if kind == "history":
        case = history_case(query["case_id"])
        start = date.fromisoformat(case["start"])
        days = [
            start + timedelta(days=i)
            for i in range(140)
            if (start + timedelta(days=i)).weekday() < 5
        ]
        rows = [
            {
                "id": str(i),
                "date": day.isoformat(),
                "close": round(10 + i * 0.2 if i < 40 else 18 - (i - 40) * 0.1, 2),
            }
            for i, day in enumerate(days)
        ]
    return {
        "rows": rows,
        "source": "demo",
        "data_date": query["date"],
        "details": {
            "warnings": ["全部为虚构演示证据，历史价格也不是对应证券真实数据。", NOTES[kind]],
            "rejected_count": 0,
            "coverage_verified": False,
            "published_at": None,
        },
    }
