"""设置 API 的持久化、凭证处理、任务配置隔离和连接诊断回归。"""

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agents.run_job import execute_job
from app.db import ModelConfiguration, ResearchJob
from app.jobs.service import claim_job
from app.main import create_app
from app.model_settings.service import apply_configuration
from tests.test_p1 import FakeModel


def draft(client, **changes):
    current = client.get("/api/settings/models").json()
    return {
        "revision": current["revision"],
        "base_url": "https://models.example/v1",
        "key_action": "replace",
        "api_key": "test-private-key",
        "default_model": "model-a",
        "models": ["model-a", "model-b"],
        "ollama_base_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:8b",
        **changes,
    }


def test_save_persists_without_restart_and_never_returns_secret(client, settings):
    result = client.post("/api/settings/models", json=draft(client))
    assert result.status_code == 200
    assert "test-private-key" not in result.text
    assert result.json()["has_api_key"] is True
    config = client.get("/api/config").json()
    assert config["api_configured"] and config["api_models"] == ["model-a", "model-b"]
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get("/api/settings/models").json()["default_model"] == "model-a"
        assert "test-private-key" not in restarted.get("/api/settings/models").text


def test_keep_replace_clear_key_and_conflicting_edits(client):
    original = draft(client)
    first = client.post("/api/settings/models", json=original).json()
    assert client.post("/api/settings/models", json=original).status_code == 409
    kept = client.post(
        "/api/settings/models",
        json=draft(
            client,
            key_action="keep",
            api_key=None,
            default_model="model-b",
        ),
    )
    assert kept.status_code == 200 and kept.json()["has_api_key"]
    assert (
        client.post(
            "/api/settings/models",
            json=draft(
                client,
                key_action="keep",
                base_url="https://other.example/v1",
            ),
        ).status_code
        == 422
    )
    cleared = client.post("/api/settings/models", json=draft(client, key_action="clear"))
    assert not cleared.json()["has_api_key"]
    assert not client.get("/api/config").json()["api_configured"]
    with client.app.state.sessions() as session:
        assert (
            session.get(ModelConfiguration, first["revision"]).values["llm_api_key"]
            == "test-private-key"
        )


def test_job_uses_submission_configuration_after_provider_changes(client, settings):
    client.post("/api/settings/models", json=draft(client))
    market = client.get("/api/market/quotes").json()
    job = client.post(
        "/api/jobs",
        json={
            "symbol": "DEMO001",
            "snapshot_id": market["snapshot_id"],
            "mode": "api",
            "model_name": "model-b",
        },
    ).json()
    client.post(
        "/api/settings/models",
        json=draft(
            client,
            base_url="https://other.example/v1",
            api_key="new-key",
            default_model="other-model",
            models=["other-model"],
        ),
    )
    received = []

    def factory(config, mode, name):
        received.append((config.llm_base_url, config.llm_api_key.get_secret_value(), name))
        return FakeModel()

    execute_job(
        client.app.state.sessions,
        settings,
        *claim_job(client.app.state.sessions, settings),
        model_factory=factory,
    )
    assert received == [("https://models.example/v1", "test-private-key", "model-b")]
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "succeeded"
    with client.app.state.sessions() as session:
        bound = session.get(ResearchJob, job["id"])
        config = apply_configuration(
            settings, session.get(ModelConfiguration, bound.model_config_id)
        )
        assert config.llm_model == "model-a"


def test_invalid_settings_never_echo_input_or_change_config(client):
    for change in [
        {"base_url": "https://host.example/v1?key=do-not-echo"},
        {"base_url": "https://host.example/v1/chat/completions"},
        {"default_model": "missing"},
        {"ollama_base_url": "http://remote.example:11434"},
        {"unexpected": "do-not-echo"},
    ]:
        response = client.post("/api/settings/models", json=draft(client, **change))
        assert response.status_code == 422
        assert "do-not-echo" not in response.text and "test-private-key" not in response.text
    assert client.get("/api/settings/models").json()["revision"] is None


def test_connection_probe_uses_draft_without_saving_and_masks_errors(client, monkeypatch):
    from app.model_settings import service as model_settings

    class ProbeModel:
        def bind_tools(self, tools, tool_choice):
            assert tool_choice == "connection_check"
            return self

        def invoke(self, messages):
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "connection_check",
                        "args": {},
                        "id": "probe",
                    }
                ],
            )

    def factory(settings, mode, name):
        assert settings.model_timeout_seconds == 15
        assert settings.llm_api_key.get_secret_value() == "test-private-key"
        return ProbeModel()

    monkeypatch.setattr(model_settings, "create_chat_model", factory)
    response = client.post("/api/settings/models/test", json=draft(client))
    assert response.json()["ok"]
    assert client.get("/api/settings/models").json()["revision"] is None

    def fail(*_):
        raise RuntimeError("private upstream body: test-private-key")

    monkeypatch.setattr(model_settings, "create_chat_model", fail)
    response = client.post("/api/settings/models/test", json=draft(client))
    assert not response.json()["ok"] and "test-private-key" not in response.text
