from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI as BaseChatOpenAI

from app.core.config import Settings


class ChatOpenAI(BaseChatOpenAI):
    """Preserve the optional public reasoning delta from compatible providers."""

    def _convert_chunk_to_generation_chunk(self, chunk, default_chunk_class, base_generation_info):
        result = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        choices = chunk.get("choices") or chunk.get("chunk", {}).get("choices", [])
        if result is not None and choices:
            reasoning = (choices[0].get("delta") or {}).get("reasoning_content")
            if isinstance(reasoning, str):
                result.message.additional_kwargs["reasoning_content"] = reasoning
        return result


def create_chat_model(settings: Settings, mode: str, name: str):
    """统一成 LangChain ChatModel；图无需知道不同供应商的 HTTP 字段。"""
    if mode == "api":
        if not settings.llm_api_key or name not in settings.api_models:
            raise ValueError("模型 API 未配置或模型不在允许列表")
        return ChatOpenAI(
            model=name,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.model_timeout_seconds,
            max_retries=0,
            max_tokens=1800,
        )
    if mode == "ollama" and name == settings.ollama_model:
        return ChatOllama(
            model=name,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_predict=1800,
            client_kwargs={"timeout": settings.model_timeout_seconds},
        )
    raise ValueError("不支持的模型配置")
