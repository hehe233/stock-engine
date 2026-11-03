"""多供应商配置管理：凭证隔离、切换、删除和既有任务的不可变绑定。"""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.db import ModelConfiguration, ResearchJob
from app.main import create_app
from tests.test_model_settings import draft

ROOT = "/api/settings/models/profiles"


def create(client, name="供应商 A", **changes):
    payload = {**draft(client), "revision": None, "name": name, **changes}
    result = client.post(ROOT, json=payload)
    assert result.status_code == 201, result.status_code
    assert "test-private-key" not in result.text
    return result.json()


def command(client, row, action):
    return client.post(f"{ROOT}/{row['id']}/{action}", json={"revision": row["revision"]})


def test_profiles_persist_and_switch_without_activating_edits(client, settings):
    a = create(client)
    b = create(
        client,
        "供应商 B",
        base_url="https://other.example/v1",
        api_key="b-secret",
        models=["b-model"],
        default_model="b-model",
    )
    assert not client.get("/api/config").json()["api_configured"]
    assert command(client, a, "activate").status_code == 200
    assert client.get("/api/config").json()["default_model"] == "model-a"
    updated = client.post(
        f"{ROOT}/{b['id']}/update",
        json={
            **draft(client),
            "revision": b["revision"],
            "name": "备用 B",
            "base_url": b["base_url"],
            "key_action": "keep",
            "api_key": None,
            "default_model": "b-new",
            "models": ["b-new"],
        },
    )
    assert updated.status_code == 200
    assert client.get("/api/config").json()["default_model"] == "model-a"
    assert command(client, updated.json(), "activate").status_code == 200
    with TestClient(create_app(settings)) as restarted:
        listed = restarted.get(ROOT)
        assert len(listed.json()["items"]) == 2
        assert listed.json()["active_id"] == b["id"]
        assert "b-secret" not in listed.text and "test-private-key" not in listed.text
        assert restarted.get("/api/config").json()["default_model"] == "b-new"


def test_delete_active_disables_api_without_environment_fallback_and_keeps_jobs(client, settings):
    a = create(client)
    command(client, a, "activate")
    market = client.get("/api/market/quotes").json()
    job = client.post(
        "/api/jobs", json={"symbol": "DEMO001", "snapshot_id": market["snapshot_id"], "mode": "api"}
    ).json()
    b = create(client, "供应商 B", api_key="second-key")
    command(client, b, "activate")
    assert command(client, a, "delete").status_code == 200
    assert client.get(ROOT).json()["active_id"] == b["id"]
    assert command(client, b, "delete").status_code == 200
    assert client.get(ROOT).json() == {"items": [], "active_id": None}
    env = settings.model_copy(
        update={"llm_api_key": SecretStr("env-key"), "llm_model": "env-model"}
    )
    with TestClient(create_app(env)) as restarted:
        assert not restarted.get("/api/config").json()["api_configured"]
    with client.app.state.sessions() as session:
        bound = session.get(ResearchJob, job["id"])
        assert (
            session.get(ModelConfiguration, bound.model_config_id).values["llm_api_key"]
            == "test-private-key"
        )
    assert command(client, a, "activate").status_code == 404


def test_new_profile_never_borrows_another_or_environment_key(client, settings):
    client.post("/api/settings/models", json=draft(client))
    env = settings.model_copy(update={"llm_api_key": SecretStr("environment-secret")})
    with TestClient(create_app(env)) as other:
        b = create(other, "无密钥备用", key_action="keep", api_key=None)
        assert not b["has_api_key"]
    with client.app.state.sessions() as session:
        assert session.get(ModelConfiguration, b["revision"]).values["llm_api_key"] is None


def test_profile_conflicts_validation_and_legacy_save_stay_consistent(client):
    a = create(client)
    assert (
        client.post(ROOT, json={**draft(client), "revision": None, "name": a["name"]}).status_code
        == 409
    )
    assert (
        client.post(ROOT, json={**draft(client), "revision": None, "name": "   "}).status_code
        == 422
    )
    command(client, a, "activate")
    # 旧单配置接口应更新同一套配置，而不是创建一个管理列表看不到的新配置。
    result = client.post("/api/settings/models", json=draft(client, default_model="model-b"))
    assert result.status_code == 200
    assert len(client.get(ROOT).json()["items"]) == 1
    for action in ("activate", "delete"):
        assert command(client, a, action).status_code == 409
    bad = client.post(
        f"{ROOT}/{a['id']}/update",
        json={
            **draft(client),
            "name": a["name"],
            "base_url": "https://other.example/v1",
            "key_action": "keep",
        },
    )
    assert bad.status_code == 422
    assert "test-private-key" not in bad.text


def test_profile_connection_test_uses_selected_profile_key_without_saving(client, monkeypatch):
    from app.model_settings import service as model_settings

    a = create(client)
    b = create(client, "供应商 B", api_key="b-secret")
    command(client, a, "activate")
    seen = []

    def probe(settings):
        seen.append(settings.llm_api_key.get_secret_value())
        return {"ok": True, "message": "mock"}

    monkeypatch.setattr(model_settings, "probe_connection", probe)
    monkeypatch.setattr("app.model_settings.routes.probe_connection", probe)
    response = client.post(
        f"{ROOT}/{b['id']}/test",
        json={
            **draft(client),
            "revision": b["revision"],
            "name": b["name"],
            "key_action": "keep",
            "api_key": None,
        },
    )
    assert response.json()["ok"]
    assert seen == ["b-secret"]
    assert client.get(ROOT).json()["active_id"] == a["id"]
    assert (
        next(p for p in client.get(ROOT).json()["items"] if p["id"] == b["id"])["revision"]
        == b["revision"]
    )
