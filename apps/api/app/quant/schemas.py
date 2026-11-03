from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
