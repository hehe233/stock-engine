from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.http.schemas import WireDatetime
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


class DataRequestResponse(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    error: str | None
    snapshot_id: str | None
    updated_at: WireDatetime


class ResearchRow(BaseModel):
    # Provider-specific evidence remains visible; absent columns stay absent.
    model_config = ConfigDict(extra="allow")
    id: str
    symbol: str | None = None
    name: str | None = None
    date: str | None = None
    close: float | None = None
    boards: int | None = None
    sector: str | None = None
    main_yuan: float | None = None
    change_since_previous_yuan: float | None = None
    url: str | None = None


class SnapshotDetails(BaseModel):
    model_config = ConfigDict(extra="allow")
    warnings: list[str]
    rejected_count: int
    coverage_verified: bool
    published_at: str | None = None


class ResearchSnapshotResponse(BaseModel):
    id: str
    kind: ResearchKind
    source: str
    is_demo: bool
    query_date: date
    data_date: date | None
    observed_at: WireDatetime
    total: int
    details: SnapshotDetails
    rows: list[ResearchRow]
    stale: bool


class LadderTier(BaseModel):
    boards: int
    count: int


class SectorSummary(BaseModel):
    sector: str
    count: int
    max_boards: int
    previous_count: int | None
    count_change: int | None


class ResearchSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    tiers: list[LadderTier] | None = None
    sectors: list[SectorSummary] | None = None
    leaders: list[str] | None = None
    comparison_date: str | None = None
    previous_observed_at: str | None = None


class ResearchDatasetResponse(BaseModel):
    snapshot: ResearchSnapshotResponse | None
    request: DataRequestResponse | None
    summary: ResearchSummary
    total: int
    page: int
    page_size: int


class WindowStats(BaseModel):
    start: str
    end: str
    return_pct: float
    drawdown_pct: float


class HistoryStatistics(BaseModel):
    bars: int
    window_count: int
    positive_count: int
    negative_count: int
    strong: WindowStats | None
    failure: WindowStats | None
    first_date: str | None
    last_date: str | None


class HistoryCaseResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    year: int
    symbol: str
    name: str
    selection: str
    start: str
    end: str
    request: DataRequestResponse | None
    snapshot: ResearchSnapshotResponse | None
    statistics: HistoryStatistics | None


class HistoryResponse(BaseModel):
    items: list[HistoryCaseResponse]
    warnings: list[str]
