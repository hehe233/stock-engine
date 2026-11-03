from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """后端配置的唯一入口：环境变量 > .env > 默认值。不要在业务代码里读环境变量。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./stock_engine.db"
    refresh_interval_seconds: int = Field(default=300, ge=10)
    scheduler_enabled: bool = True
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    market_provider: Literal["demo", "public"] = "public"
    public_source: Literal["eastmoney", "sina"] = "eastmoney"
    # 新浪全市场需顺序读取约 70 页，75 秒在实测中不足；总超时仍由子进程强制执行。
    provider_timeout_seconds: int = Field(default=180, ge=5, le=180)
    # API 凭证只在后端读取；前端只能选择这里明确允许的模型。
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = ""
    llm_models: list[str] = []
    # Ollama 是显式选择的备选，不会在 API 失败时自动切换。
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    model_timeout_seconds: int = Field(default=60, ge=5, le=180)
    max_tool_rounds: int = Field(default=3, ge=1, le=5)
    checkpoint_sqlite_path: str = "./checkpoints.db"
    checkpoint_postgres_url: SecretStr | None = None
    job_timeout_seconds: int = Field(default=300, ge=30, le=900)
    job_max_attempts: int = Field(default=3, ge=1, le=5)
    max_pending_jobs: int = Field(default=20, ge=1, le=100)
    app_environment: Literal["development", "production"] = "development"
    app_api_key: SecretStr | None = None
    quant_artifact_dir: str = "./quant_artifacts"
    quant_timeout_seconds: int = Field(default=600, ge=30, le=1800)

    @field_validator("llm_api_key", "app_api_key", "checkpoint_postgres_url", mode="before")
    @classmethod
    def empty_secret_is_unconfigured(cls, value):
        # .env 模板的空值和 Windows 演示启动的空白覆盖都表示“未配置”。
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def validate_runtime(self):
        if self.market_provider == "public" and self.refresh_interval_seconds < 300:
            raise ValueError("免费全市场采集间隔至少 300 秒，避免对公开数据源高频请求")
        if urlparse(self.ollama_base_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Ollama 备选只允许连接本机服务")
        api_url = urlparse(self.llm_base_url)
        if api_url.scheme not in {"http", "https"} or not api_url.hostname:
            raise ValueError("LLM_BASE_URL 必须是有效的 HTTP(S) 地址")
        if api_url.username or api_url.password:
            raise ValueError("不要把密钥放在 LLM_BASE_URL 中，请使用 LLM_API_KEY")
        if self.app_environment == "production":
            if not self.app_api_key or len(self.app_api_key.get_secret_value()) < 32:
                raise ValueError("生产模式必须设置至少 32 字符的 APP_API_KEY")
            if "*" in self.cors_origins:
                raise ValueError("生产模式不能使用通配 CORS 来源")
        return self

    @property
    def api_models(self) -> list[str]:
        return list(dict.fromkeys(name for name in [self.llm_model, *self.llm_models] if name))


@lru_cache
def get_settings() -> Settings:
    return Settings()
