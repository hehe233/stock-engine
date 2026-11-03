from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.securities import normalize_symbol
from app.shared.time import SHANGHAI, utc_now


class PositionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    symbol: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    asset_type: Literal["stock", "etf"] = "stock"
    quantity: int = Field(gt=0, le=1_000_000_000)
    cost_price: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    acquired_on: date
    settlement: Literal["T1", "T0", "unknown"] = "T1"
    note: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def valid_lot(self):
        if self.asset_type == "etf" and "settlement" not in self.model_fields_set:
            self.settlement = "unknown"
        if not self.symbol.startswith("DEMO"):
            self.symbol = normalize_symbol(self.symbol, self.asset_type)
        if self.asset_type == "stock" and self.settlement != "T1":
            raise ValueError("普通 A 股持仓按 T+1，不允许设置为 T+0")
        if self.acquired_on > utc_now().astimezone(SHANGHAI).date():
            raise ValueError("持仓日期不能在未来")
        return self


class PositionImport(BaseModel):
    rows: list[PositionInput] = Field(min_length=1, max_length=500)


class CsvPreview(BaseModel):
    content: str = Field(min_length=1, max_length=200_000)


class PositionRecord(BaseModel):
    # Output is independent of today's input validation (e.g. date constraints).
    symbol: str
    name: str
    asset_type: Literal["stock", "etf"]
    quantity: int
    cost_price: str
    acquired_on: str
    settlement: Literal["T0", "T1", "unknown"]
    note: str


class PositionResponse(PositionRecord):
    id: str
    updated_at: str
    price: float | None
    cost_yuan: float
    value_yuan: float | None
    pnl_yuan: float | None
    pnl_pct: float | None
    sellable: int | None
    conditions: list[str]
    quote_time: str | None
    quote_snapshot_id: str | None
    fetched_at: str | None
    weight_pct: float | None


class MarketSessionResponse(BaseModel):
    code: Literal["unknown", "closed", "auction", "trading", "break"]
    label: str
    calendar_verified: bool


class PortfolioResponse(BaseModel):
    items: list[PositionResponse]
    is_demo: bool
    as_of: str
    session: MarketSessionResponse
    unknown_price_count: int
    cost_yuan: float
    known_value_yuan: float
    pnl_yuan: float | None
    warnings: list[str]


class PreviewError(BaseModel):
    line: int
    message: str


class PreviewResponse(BaseModel):
    rows: list[PositionRecord]
    errors: list[PreviewError]
    valid: bool
    count: int


class ImportResponse(BaseModel):
    inserted: int
    skipped: int


class UpdateResponse(BaseModel):
    updated: bool


class DeleteResponse(BaseModel):
    deleted: bool
