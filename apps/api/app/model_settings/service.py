"""页面设置覆盖 .env；任务绑定不可变配置，API 和 worker 都从数据库读取。"""

from threading import Lock
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from sqlalchemy import func, select

from app.agents.models import create_chat_model
from app.core.config import Settings
from app.db import ModelConfiguration, ModelProfile, ServiceState
from app.shared.time import utc_now

settings_lock = Lock()
MODEL_FIELDS = (
    "llm_base_url",
    "llm_api_key",
    "llm_model",
    "llm_models",
    "ollama_base_url",
    "ollama_model",
)


class ModelSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    revision: str | None = None
    base_url: str = Field(min_length=1, max_length=500)
    api_key: SecretStr | None = None
    key_action: Literal["keep", "replace", "clear"] = "keep"
    default_model: str = Field(max_length=200)
    models: list[str] = Field(max_length=30)
    ollama_base_url: str = Field(min_length=1, max_length=500)
    ollama_model: str = Field(min_length=1, max_length=200)

    @field_validator("base_url", "ollama_base_url")
    @classmethod
    def clean_url(cls, value):
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("地址必须是无凭证、查询参数和片段的 HTTP(S) Base URL")
        if parsed.path.rstrip("/").endswith(("/chat/completions", "/responses")):
            raise ValueError("请填写 Base URL，不要填写完整生成接口路径")
        return value.rstrip("/")

    @field_validator("models")
    @classmethod
    def clean_models(cls, values):
        names = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if any(len(name) > 200 for name in names):
            raise ValueError("模型名称最多 200 字符")
        return names


def active_configuration(session):
    state = session.get(ServiceState, "model_settings")
    return session.get(ModelConfiguration, state.value["id"]) if state else None


def apply_configuration(base: Settings, row: ModelConfiguration | None) -> Settings:
    if row is None:
        return base
    return Settings.model_validate({**base.model_dump(), **row.values})


def effective_settings(session, base):
    return apply_configuration(base, active_configuration(session))


class ProfileInput(ModelSettingsInput):
    name: str = Field(min_length=1, max_length=80)


class RevisionInput(BaseModel):
    revision: str


def active_profile_id(session):
    state = session.get(ServiceState, "model_settings")
    return state.value.get("profile_id") if state else None


def settings_view(base, row):
    current = apply_configuration(base, row)
    return {
        "revision": row.id if row else None,
        "source": "saved" if row else "environment",
        "base_url": current.llm_base_url,
        "has_api_key": bool(current.llm_api_key),
        "default_model": current.llm_model,
        "models": current.api_models,
        "ollama_base_url": current.ollama_base_url,
        "ollama_model": current.ollama_model,
    }


def public_settings(session, base):
    return settings_view(base, active_configuration(session))


def draft_settings(session, base, payload: ModelSettingsInput):
    return validate_draft(base, active_configuration(session), payload)


def validate_draft(base, row, payload):
    if payload.revision != (row.id if row else None):
        raise HTTPException(409, "配置已在其他页面修改，请重新加载设置后再提交")
    current = apply_configuration(base, row)
    key = current.llm_api_key
    if payload.key_action == "replace":
        key = payload.api_key
        if not key or not key.get_secret_value().strip():
            raise HTTPException(422, "请输入新的 API Key")
        if len(key.get_secret_value()) > 4096:
            raise HTTPException(422, "API Key 过长")
    elif payload.key_action == "clear":
        key = None
    elif payload.base_url != current.llm_base_url.rstrip("/") and key:
        # 更换地址时必须重新提供密钥，避免把已有密钥发送给另一个供应商。
        raise HTTPException(422, "更换 API 地址时，请选择替换密钥并输入新密钥，或清除密钥")
    if payload.models and payload.default_model not in payload.models:
        raise HTTPException(422, "默认模型必须在可选模型列表中")
    if key and not payload.default_model:
        raise HTTPException(422, "配置 API Key 后请填写默认模型")
    try:
        return Settings.model_validate(
            {
                **base.model_dump(),
                "llm_base_url": payload.base_url,
                "llm_api_key": key,
                "llm_model": payload.default_model,
                "llm_models": payload.models,
                "ollama_base_url": payload.ollama_base_url,
                "ollama_model": payload.ollama_model,
            }
        )
    except ValidationError as exc:
        raise HTTPException(422, "模型配置无效；Ollama 地址必须指向本机服务") from exc


def snapshot_configuration(session, settings):
    values = {name: getattr(settings, name) for name in MODEL_FIELDS}
    # SecretStr 默认序列化为星号，入库时显式提取；对外响应绝不使用此对象。
    values["llm_api_key"] = (
        settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    )
    row = ModelConfiguration(id=str(uuid4()), values=values)
    session.add(row)
    session.flush()
    return row


def save_settings(session, base, payload):
    with settings_lock:
        settings = draft_settings(session, base, payload)
        row = snapshot_configuration(session, settings)
        profile_id = active_profile_id(session)
        profile = session.get(ModelProfile, profile_id) if profile_id else None
        if profile:
            profile.configuration_id = row.id
        else:
            # 兼容原单配置接口：第一次保存自动成为可管理配置。
            name = "默认配置"
            suffix = 1
            while session.scalar(select(ModelProfile.id).where(ModelProfile.name == name)):
                suffix += 1
                name = f"默认配置 {suffix}"
            profile = ModelProfile(id=str(uuid4()), name=name, configuration_id=row.id)
            session.add(profile)
        set_active(session, row.id, profile.id)
        session.commit()
        return public_settings(session, base)


def set_active(session, configuration_id, profile_id):
    state = session.get(ServiceState, "model_settings")
    value = {"id": configuration_id, "profile_id": profile_id}
    if state:
        state.value, state.updated_at = value, utc_now()
    else:
        session.add(ServiceState(key="model_settings", value=value))


def profile_view(session, base, profile):
    return {
        **settings_view(base, session.get(ModelConfiguration, profile.configuration_id)),
        "id": profile.id,
        "name": profile.name,
        "active": profile.id == active_profile_id(session),
    }


def list_profiles(session, base):
    profiles = session.scalars(
        select(ModelProfile).order_by(ModelProfile.created_at, ModelProfile.id)
    ).all()
    return {
        "items": [profile_view(session, base, p) for p in profiles],
        "active_id": active_profile_id(session),
    }


def get_profile(session, profile_id, revision):
    profile = session.get(ModelProfile, profile_id)
    if profile is None:
        raise HTTPException(404, "配置不存在或已删除，请重新加载")
    if profile.configuration_id != revision:
        raise HTTPException(409, "配置已在其他页面修改，请重新加载后再操作")
    return profile


def profile_draft(session, base, payload, profile_id=None):
    profile = get_profile(session, profile_id, payload.revision) if profile_id else None
    row = session.get(ModelConfiguration, profile.configuration_id) if profile else None
    # 新配置绝不能继承环境或其他配置的密钥。
    clean_base = base if profile else base.model_copy(update={"llm_api_key": None})
    return validate_draft(clean_base, row, payload)


def save_profile(session, base, payload, profile_id=None):
    with settings_lock:
        settings = profile_draft(session, base, payload, profile_id)
        duplicate = session.scalar(select(ModelProfile).where(ModelProfile.name == payload.name))
        if duplicate and duplicate.id != profile_id:
            raise HTTPException(409, "配置名称已存在，请使用其他名称")
        if (
            profile_id is None
            and session.scalar(select(func.count()).select_from(ModelProfile)) >= 30
        ):
            raise HTTPException(422, "最多保存 30 套模型配置")
        row = snapshot_configuration(session, settings)
        if profile_id:
            profile = session.get(ModelProfile, profile_id)
            profile.name, profile.configuration_id = payload.name, row.id
            if active_profile_id(session) == profile_id:
                set_active(session, row.id, profile_id)
        else:
            profile = ModelProfile(id=str(uuid4()), name=payload.name, configuration_id=row.id)
            session.add(profile)
        session.commit()
        return profile_view(session, base, profile)


def activate_profile(session, base, profile_id, revision):
    with settings_lock:
        profile = get_profile(session, profile_id, revision)
        set_active(session, profile.configuration_id, profile.id)
        session.commit()
        return profile_view(session, base, profile)


def delete_profile(session, base, profile_id, revision):
    with settings_lock:
        profile = get_profile(session, profile_id, revision)
        if active_profile_id(session) == profile_id:
            # 删除当前配置后显式停用 API，不偷偷启用另一家或退回 .env 密钥。
            current = apply_configuration(
                base, session.get(ModelConfiguration, profile.configuration_id)
            )
            disabled = current.model_copy(
                update={"llm_api_key": None, "llm_model": "", "llm_models": []}
            )
            row = snapshot_configuration(session, disabled)
            set_active(session, row.id, None)
        session.delete(profile)
        session.commit()
        return {"deleted": True}


def probe_connection(settings):
    """一次小型工具调用检查；不执行模型返回的工具，不发行情，最多等待 15 秒。"""
    if not settings.llm_api_key or not settings.llm_model:
        raise HTTPException(422, "请先填写 API Key 和默认模型")
    bounded = settings.model_copy(update={"model_timeout_seconds": 15})
    tool = {
        "type": "function",
        "function": {
            "name": "connection_check",
            "description": "确认工具调用格式可用。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
    try:
        model = create_chat_model(bounded, "api", settings.llm_model)
        response = model.bind_tools([tool], tool_choice="connection_check").invoke(
            [HumanMessage(content="请调用 connection_check 工具，无需其他输出。")]
        )
        valid = any(
            call["name"] == "connection_check" and call["args"] == {}
            for call in response.tool_calls
        )
        if not valid:
            return {
                "ok": False,
                "message": "服务已响应，但未返回有效工具调用，请更换支持工具调用的模型。",
            }
        return {"ok": True, "message": "连接与工具调用测试通过。尚未保存，请点击保存设置。"}
    except Exception as exc:
        # 供应商错误可能包含请求头、URL 或响应原文，只返回状态码与安全分类。
        status = getattr(exc, "status_code", None)
        detail = f"HTTP {status}" if isinstance(status, int) else type(exc).__name__
        return {
            "ok": False,
            "message": f"连接测试失败（{detail}），请检查地址、密钥、模型名称和工具调用支持。",
        }
