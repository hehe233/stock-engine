import json
from datetime import datetime
from pathlib import Path

from app.providers.base import QuoteBatch
from app.schemas import Quote


class DemoQuoteProvider:
    def fetch_quotes(self, asset_type: str = "stock") -> QuoteBatch:
        path = Path(__file__).parent / "fixtures" / "quotes.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if asset_type != "stock":
            label = "ETF" if asset_type == "etf" else "指数"
            payload["quotes"] = [
                {
                    "symbol": f"DEMO{asset_type.upper()}",
                    "name": f"样本·{label}",
                    "asset_type": asset_type,
                    "price": 2.56,
                    "change_pct": 1.2,
                    "amount_yuan": 200_000_000,
                }
            ]
        # 不用当前时间伪造行情时间。刷新只改变 fetched_at，样本的 as_of 保持不变。
        return QuoteBatch(
            source="demo",
            as_of=datetime.fromisoformat(payload["as_of"]),
            quotes=[Quote.model_validate(item) for item in payload["quotes"]],
            asset_type=asset_type,
        )
