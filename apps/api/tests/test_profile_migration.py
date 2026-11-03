"""从已有单套设置升级时保留凭证和活动配置指针。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.db import ModelConfiguration, ModelProfile, ServiceState, build_database


def test_migration_preserves_legacy_active_configuration(settings):
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.downgrade(config, "0004")
    engine, sessions = build_database(settings.database_url)
    try:
        with sessions() as session:
            session.add(
                ModelConfiguration(
                    id="existing-version", values={"llm_api_key": "migration-secret"}
                )
            )
            session.add(ServiceState(key="model_settings", value={"id": "existing-version"}))
            session.commit()
        command.upgrade(config, "head")
        with sessions() as session:
            profile = session.scalar(select(ModelProfile))
            assert profile.name == "默认配置"
            assert profile.configuration_id == "existing-version"
            assert session.get(ServiceState, "model_settings").value == {
                "id": "existing-version",
                "profile_id": profile.id,
            }
            assert (
                session.get(ModelConfiguration, "existing-version").values["llm_api_key"]
                == "migration-secret"
            )
    finally:
        engine.dispose()
