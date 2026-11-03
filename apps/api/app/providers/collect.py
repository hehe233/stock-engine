"""隔离第三方采集：父进程设置超时并回收进程，避免无超时的 SDK 阻塞 API。"""

import argparse
import json
from pathlib import Path


def collect(asset_type: str, source: str):
    import akshare as ak

    if asset_type == "calendar":
        return {
            "dates": [str(value)[:10] for value in ak.tool_trade_date_hist_sina()["trade_date"]]
        }
    if asset_type == "stock":
        frame = ak.stock_zh_a_spot_em() if source == "eastmoney" else ak.stock_zh_a_spot()
    elif asset_type == "etf":
        frame = (
            ak.fund_etf_spot_em()
            if source == "eastmoney"
            else ak.fund_etf_category_sina(symbol="ETF基金")
        )
    else:
        # 新浪接口按文档返回指数集合，避免将仅几个大盘指数冒充全量指数。
        frame = ak.stock_zh_index_spot_sina()
    return {"rows": json.loads(frame.to_json(orient="records", date_format="iso"))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--asset-type", choices=["stock", "etf", "index", "calendar", "research"], required=True
    )
    parser.add_argument("--source", choices=["eastmoney", "sina"], required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--query")
    args = parser.parse_args()
    try:
        if args.asset_type == "research":
            from app.providers.research_collect import collect_research

            result = collect_research(json.loads(args.query))
        else:
            result = collect(args.asset_type, args.source)
    except Exception as exc:
        # 不把网络环境、代理凭证或完整请求内容返回给浏览器。
        result = {"error": type(exc).__name__}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
