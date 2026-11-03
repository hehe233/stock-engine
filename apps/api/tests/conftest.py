from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    # 测试也走真实迁移，避免 create_all 掩盖 migration 和 ORM 不一致的问题。
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    yield Settings(
        _env_file=None,
        database_url=database_url,
        scheduler_enabled=False,
        market_provider="demo",
        llm_api_key=None,
        llm_model="",
        llm_models=[],
        app_api_key=None,
        app_environment="development",
        checkpoint_postgres_url=None,
        checkpoint_sqlite_path=str(tmp_path / "checkpoints.db"),
        quant_artifact_dir=str(tmp_path / "quant_artifacts"),
    )
    get_settings.cache_clear()


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
