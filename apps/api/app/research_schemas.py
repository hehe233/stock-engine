"""P2 契约：外部数据缺失保持 None，不能用零或今日日期替代。"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.securities import normalize_symbol
from app.shared.time import SHANGHAI, utc_now

ResearchKind = Literal["ladder", "dragon", "seats", "flow", "notices", "history"]


class FetchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ResearchKind
    date: date
    symbol: str = Field(default="", max_length=20)
    case_id: str = Field(default="", max_length=40)

    @model_validator(mode="after")
    def validate_query(self):
        if self.date > utc_now().astimezone(SHANGHAI).date():
            raise ValueError("不能请求未来日期")
        if self.kind == "seats":
            if not self.symbol.startswith("DEMO"):
                self.symbol = normalize_symbol(self.symbol, "stock")
        if self.kind == "flow" and self.date != utc_now().astimezone(SHANGHAI).date():
            raise ValueError("资金排名仅提供当前快照，不能按历史日期查询")
        return self


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
