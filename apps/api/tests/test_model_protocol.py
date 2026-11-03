"""用真实 ChatOpenAI 客户端验证 HTTP 协议，不向外部服务发送请求或密钥。"""

import json

import httpx
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.agents import models
from app.agents.assistant import build_assistant_graph


def test_configured_api_model_tools_and_structured_output(client, settings, monkeypatch):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert str(request.url) == "https://models.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer protocol-test-key"
        assert body["model"] == "model-b"
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-quote",
                        "type": "function",
                        "function": {
                            "name": "read_quote",
                            "arguments": "{}",
                        },
                    }
                ],
            }
        elif len(requests) == 2:
            evidence = next(item for item in body["messages"] if item["role"] == "tool")
            assert evidence["tool_call_id"] == "call-quote"
            assert json.loads(evidence["content"])["data"]["quote"]["symbol"] == "DEMO001"
            message = {"role": "assistant", "content": "已取得行情证据"}
        else:
            assert body["tool_choice"]["function"]["name"] == "ModelInsight"
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-report",
                        "type": "function",
                        "function": {
                            "name": "ModelInsight",
                            "arguments": json.dumps(
                                {
                                    "summary": "仅解读演示行情。",
                                    "observations": [
                                        {"text": "标的是虚构样本。", "evidence_ids": ["read_quote"]}
                                    ],
                                    "limitations": ["不代表真实市场。"],
                                },
                                ensure_ascii=False,
                            ),
                        },
                    }
                ],
            }
        return httpx.Response(
            200,
            json={
                "id": f"completion-{len(requests)}",
                "object": "chat.completion",
                "created": 1,
                "model": "model-b",
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
        )

    configured = settings.model_copy(
        update={
            "llm_base_url": "https://models.example/v1",
            "llm_api_key": SecretStr("protocol-test-key"),
            "llm_model": "model-a",
            "llm_models": ["model-b"],
        }
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as http_client:
        monkeypatch.setattr(
            models,
            "ChatOpenAI",
            lambda **kwargs: ChatOpenAI(
                **kwargs,
                http_client=http_client,
            ),
        )
        model = models.create_chat_model(configured, "api", "model-b")
        quote = client.get("/api/market/quotes?search=DEMO001").json()["quotes"][0]
        result = build_assistant_graph(model).invoke(
            {
                "quote": quote,
                "source": "demo",
                "is_demo": True,
                "trace": [],
            }
        )
    assert len(requests) == 3
    assert {item["function"]["name"] for item in requests[0]["tools"]} == {
        "read_quote",
        "read_factors",
        "read_risks",
        "read_research",
        "read_portfolio",
    }
    assert result["heat_score"] == 91.94
    assert result["insight"]["observations"][0]["evidence_ids"] == ["read_quote"]
