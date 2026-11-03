from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetType = Literal["stock", "etf", "index"]
AnalysisMode = Literal["rules", "api", "ollama"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class Quote(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    symbol: str
    name: str
    sector: str = "未提供"
    asset_type: AssetType = "stock"
    # 未提供的字段保留 null；缺失价格不会被伪造为 0 元。
    price: float | None = Field(default=None, gt=0)
    change_pct: float | None = Field(default=None, ge=-100)
    turnover_pct: float | None = Field(default=None, ge=0)
    volume_ratio: float | None = Field(default=None, ge=0)
    amount_yuan: float | None = Field(default=None, ge=0)
    quote_time: datetime | None = None


class MarketResponse(BaseModel):
    snapshot_id: str
    source: str
    is_demo: bool
    asset_type: AssetType = "stock"
    as_of: datetime | None
    fetched_at: datetime
    stale: bool
    refresh_interval_seconds: int
    quotes: list[Quote]
    total: int = 0
    universe_count: int = 0
    page: int = 1
    page_size: int = 100
    source_time_known_count: int = 0
    missing_from_previous: list[str] = []
    rejected_count: int = 0
    coverage_verified: bool = False
    warnings: list[str] = []


class AnalysisRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9.]{1,16}$")
    snapshot_id: str = Field(min_length=36, max_length=36)
    mode: AnalysisMode = "rules"
    model_name: str | None = Field(default=None, min_length=1, max_length=200)
    include_portfolio: bool = False


class Factor(BaseModel):
    name: str
    value: float | None
    points: float | None
    max_points: int
    explanation: str


class TraceStep(BaseModel):
    node: str
    title: str
    detail: str


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1000)
    evidence_ids: list[str] = Field(min_length=1, max_length=3)


class ModelInsight(BaseModel):
    """模型只解释证据，不通过输出字段改写规则分数或生成所谓妖股概率。"""

    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=2000)
    observations: list[Observation] = Field(min_length=1, max_length=5)
    limitations: list[str] = Field(min_length=1, max_length=5)


class AnalysisReport(BaseModel):
    id: str
    snapshot_id: str
    symbol: str
    name: str
    created_at: datetime
    as_of: datetime | None
    source: str = "demo"
    is_demo: bool = True
    asset_type: AssetType = "stock"
    analysis_mode: AnalysisMode = "rules"
    score_version: str = "heat-v1"
    heat_score: float | None = Field(default=None, ge=0, le=100)
    summary: str
    factors: list[Factor]
    risks: list[str]
    trace: list[TraceStep]
    insight: ModelInsight | None = None
    evidence: dict[str, dict] = Field(default_factory=dict)
    research_context: dict = Field(default_factory=dict)
    model_name: str | None = None


class AnalysisList(BaseModel):
    items: list[AnalysisReport]
    total: int


class JobResponse(BaseModel):
    id: str
    snapshot_id: str
    symbol: str
    mode: AnalysisMode
    model_name: str | None
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    attempts: int
    cancel_requested: bool
    error: str | None
    report_id: str | None


class EventResponse(BaseModel):
    id: int
    kind: str
    created_at: datetime
    payload: dict
