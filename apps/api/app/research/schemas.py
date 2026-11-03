from datetime import date
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
