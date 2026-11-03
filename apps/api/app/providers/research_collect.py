"""仅在受超时控制的采集子进程运行第三方 SDK，输出允许使用的原始字段。"""

import json

from app.research.catalog import history_case


def collect_research(query):
    import akshare as ak

    kind, day = query["kind"], query["date"].replace("-", "")
    source = "akshare:eastmoney"
    if kind == "ladder":
        frame = ak.stock_zt_pool_em(date=day)
    elif kind == "dragon":
        frame = ak.stock_lhb_detail_em(start_date=day, end_date=day)
    elif kind == "seats":
        import pandas as pd

        sides = []
        for side in ("买入", "卖出"):
            data = ak.stock_lhb_stock_detail_em(symbol=query["symbol"][:6], date=day, flag=side)
            data["方向"] = side
            sides.append(data)
        frame = pd.concat(sides, ignore_index=True)
    elif kind == "flow":
        frame = ak.stock_individual_fund_flow_rank(indicator="今日")
    elif kind == "notices":
        frame = ak.stock_notice_report(symbol="全部", date=day)
    else:
        case = history_case(query["case_id"])
        code, exchange = case["symbol"].split(".")
        # 腾讯接受带交易所代码。按 ISO 日期限定年份，避免 SDK 多抓到当前年份。
        frame = ak.stock_zh_a_hist_tx(
            symbol=f"{exchange.lower()}{code}",
            start_date=case["start"],
            end_date=case["end"],
            adjust="qfq",
        )
        source = "akshare:tencent:qfq"
    return {
        "rows": json.loads(frame.to_json(orient="records", date_format="iso")),
        "source": source,
    }
