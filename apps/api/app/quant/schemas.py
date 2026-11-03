from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.http.schemas import WireDatetime


class DatasetImport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=200)
    adjustment: Literal["raw", "qfq"] = "raw"
    selection: Literal["manual", "historical_universe"] = "manual"
    content: str = Field(min_length=1, max_length=20_000_000)


class ExperimentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dataset_id: str
    # 第一版固定用户确定的标签，避免试到最好看的标签后误称样本外验证。
    horizon: Literal[5] = 5
    event_return: Literal[0.2] = 0.2
    train_days: int = Field(default=120, ge=60, le=1000)
    calibration_days: int = Field(default=60, ge=20, le=250)
    test_days: int = Field(default=60, ge=20, le=250)
    folds: int = Field(default=3, ge=1, le=6)
    probability_threshold: float = Field(default=0.6, ge=0.05, le=0.95)
    initial_cash: float = Field(default=100000, ge=10000, le=100000000)
    max_positions: int = Field(default=3, ge=1, le=10)
    commission_bps: float = Field(default=3, ge=0, le=100)
    slippage_bps: float = Field(default=10, ge=0, le=100)
    participation: float = Field(default=0.01, gt=0, le=0.1)
    seed: int = Field(default=42, ge=0, le=2147483647)


class SymbolAudit(BaseModel):
    symbol: str
    rows: int
    first: str
    last: str
    listed_on: str | None
    delisted_on: str | None


class DatasetAudit(BaseModel):
    model_config = ConfigDict(extra="allow")
    rows: int
    symbols: list[SymbolAudit]
    symbol_count: int
    days: int
    first: str
    last: str
    adjustment: Literal["raw", "qfq"]
    selection: Literal["manual", "historical_universe"]
    executable_rows: int
    missing_available_at: int
    coverage_verified: bool
    level2: bool = False
    warnings: list[str]
    snapshot_ids: list[str] | None = None


class DatasetResponse(BaseModel):
    id: str
    name: str
    source: str
    checksum: str
    is_demo: bool
    created_at: WireDatetime
    details: DatasetAudit


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]


class ExperimentParameters(BaseModel):
    # Versioned output must not acquire new input defaults or stricter input bounds.
    model_config = ConfigDict(extra="allow")
    dataset_id: str
    horizon: int
    event_return: float
    train_days: int
    calibration_days: int
    test_days: int
    folds: int
    probability_threshold: float
    initial_cash: float
    max_positions: int
    commission_bps: float
    slippage_bps: float
    participation: float
    seed: int


class CalibrationBin(BaseModel):
    lower: float
    upper: float
    count: int
    predicted: float
    observed: float


class Metrics(BaseModel):
    model_config = ConfigDict(extra="allow")
    count: int
    positives: int
    event_rate: float
    brier: float
    log_loss: float
    auc: float | None
    ece: float
    bins: list[CalibrationBin]


class FoldResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    fold: int
    train_start: str
    train_end: str
    train_label_end: str
    calibration_start: str
    calibration_end: str
    calibration_label_end: str
    test_start: str
    test_end: str
    train_count: int
    calibration_count: int
    metrics: Metrics
    raw_metrics: Metrics


class BacktestResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool
    reason: str | None = None
    valuation_complete: bool | None = None
    return_pct: float | None = None
    max_drawdown_pct: float | None = None
    warnings: list[str] | None = None


class QuantResult(BaseModel):
    # Lists expose a subset; queued and older versions may omit computed fields.
    model_config = ConfigDict(extra="allow")
    stage: str | None = None
    target: str | None = None
    metrics: Metrics | None = None
    raw_metrics: Metrics | None = None
    baseline_metrics: Metrics | None = None
    folds: list[FoldResponse] | None = None
    backtest: BacktestResponse | None = None
    dataset_checksum: str | None = None
    code_sha256: str | None = None
    engine_version: str | None = None
    feature_version: str | None = None
    dependencies: dict[str, str] | None = None
    artifacts: dict[str, str] | None = None
    evaluation_end: str | None = None
    research_only: bool | None = None
    warnings: list[str] | None = None


class RunResponse(BaseModel):
    id: str
    dataset_id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    params: ExperimentParameters
    result: QuantResult
    created_at: WireDatetime
    updated_at: WireDatetime
    error: str | None
    is_demo: bool
    cancel_requested: bool


class RunListResponse(BaseModel):
    items: list[RunResponse]


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str
    date: str
    label_end: str
    label: int
    future_return: float
    probability: float
    raw_probability: float
    fold: int


class PredictionPage(BaseModel):
    total: int
    items: list[PredictionResponse]
