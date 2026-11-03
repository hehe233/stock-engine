from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.schemas import Quote


@dataclass(frozen=True)
class QuoteBatch:
    source: str
    as_of: datetime | None
    quotes: list[Quote]
    asset_type: str = "stock"
    details: dict = field(default_factory=dict)


class QuoteProvider(Protocol):
    """数据源边界：供应商字段先转成 Quote，服务层无需关心接口差异。"""

    def fetch_quotes(self, asset_type: str = "stock") -> QuoteBatch: ...


class ProviderError(RuntimeError):
    pass
