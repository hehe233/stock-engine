from pydantic import ValidationError

from app.providers.base import ProviderError, QuoteBatch
from app.providers.normalization import number, source_time
from app.providers.runner import run_collector
from app.schemas import Quote
from app.shared.securities import normalize_symbol


def normalize_rows(rows: list[dict], asset_type: str) -> tuple[list[Quote], int]:
    quotes, rejected = [], 0
    for row in rows:
        try:
            symbol = normalize_symbol(str(row.get("代码", "")), asset_type)
            price = number(row.get("最新价"))
            quotes.append(
                Quote(
                    symbol=symbol,
                    name=str(row["名称"]),
                    asset_type=asset_type,
                    price=price if price is not None and price > 0 else None,
                    change_pct=number(row.get("涨跌幅")),
                    turnover_pct=number(row.get("换手率")),
                    volume_ratio=number(row.get("量比")),
                    amount_yuan=number(row.get("成交额")),
                    quote_time=source_time(row.get("更新时间")),
                )
            )
        except (ValueError, KeyError, ValidationError):
            rejected += 1
    return quotes, rejected


class PublicQuoteProvider:
    def __init__(self, primary_source: str = "eastmoney", timeout: int = 180):
        self.primary_source = primary_source
        self.timeout = timeout

    def fetch_quotes(self, asset_type: str = "stock") -> QuoteBatch:
        sources = (
            ["sina"]
            if asset_type == "index"
            else [
                self.primary_source,
                "sina" if self.primary_source == "eastmoney" else "eastmoney",
            ]
        )
        errors = []
        for source in sources:
            try:
                payload = run_collector(asset_type, source, self.timeout)
                quotes, rejected = normalize_rows(payload.get("rows", []), asset_type)
                if not quotes:
                    raise ProviderError(f"{source} 没有返回可用行情")
                times = [quote.quote_time for quote in quotes if quote.quote_time]
                return QuoteBatch(
                    source=f"akshare:{source}",
                    asset_type=asset_type,
                    as_of=max(times) if times else None,
                    quotes=quotes,
                    details={
                        "rejected_count": rejected,
                        "source_time_known_count": len(times),
                        "warnings": errors,
                        "coverage_verified": False,
                    },
                )
            except ProviderError as exc:
                errors.append(str(exc))
        raise ProviderError("；".join(errors))
