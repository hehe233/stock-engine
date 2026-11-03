"""Public model deltas and structured previews on LangGraph's custom stream."""

import json
from uuid import uuid4

from langchain_core.messages import message_chunk_to_message
from langchain_core.utils.json import parse_partial_json
from langgraph.config import get_stream_writer


def emit(kind: str, **payload):
    get_stream_writer()({"kind": kind, "payload": payload})


def insight_preview(value: dict) -> dict:
    """Only project typed display fields; the complete report is validated separately."""
    result = {}
    if isinstance(value.get("summary"), str):
        result["summary"] = value["summary"]
    if isinstance(value.get("observations"), list):
        result["observations"] = [
            {
                key: item[key]
                for key in ("text", "evidence_ids")
                if (key == "text" and isinstance(item.get(key), str))
                or (
                    key == "evidence_ids"
                    and isinstance(item.get(key), list)
                    and all(isinstance(ref, str) for ref in item[key])
                )
            }
            for item in value["observations"]
            if isinstance(item, dict)
        ]
    if isinstance(value.get("limitations"), list):
        result["limitations"] = [item for item in value["limitations"] if isinstance(item, str)]
    return result


def stream_message(model, messages, *, report=False):
    block_id = str(uuid4())
    emit("model.start", block_id=block_id, message="生成研究报告" if report else "分析证据")
    if report:
        emit("report.start", block_id=block_id)
    combined = None
    previous_preview = None
    for chunk in model.stream(messages):
        combined = chunk if combined is None else combined + chunk
        reasoning = chunk.additional_kwargs.get("reasoning_content", "")
        if isinstance(reasoning, str) and reasoning:
            emit("reasoning.delta", block_id=block_id, text=reasoning)
        if isinstance(chunk.content, str):
            if chunk.content:
                emit("content.delta", block_id=block_id, text=chunk.content)
        else:
            for block in chunk.content:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                text = (
                    block.get("text")
                    if kind == "text"
                    else (block.get("reasoning") or block.get("thinking"))
                )
                if isinstance(text, str) and text:
                    emit(
                        "content.delta" if kind == "text" else "reasoning.delta",
                        block_id=block_id,
                        text=text,
                    )
        if report and combined.tool_call_chunks:
            try:
                preview = parse_partial_json(combined.tool_call_chunks[0]["args"])
            except (ValueError, TypeError):
                continue
            if isinstance(preview, dict) and preview != previous_preview:
                emit("report.delta", block_id=block_id, insight=insight_preview(preview))
                previous_preview = preview
    if combined is None:
        raise ValueError("模型没有返回内容")
    # LangChain tolerantly parses incomplete JSON for previews. Never treat a
    # truncated function call as a completed tool invocation or validated report.
    for call in combined.tool_call_chunks:
        if not isinstance(json.loads(call["args"]), dict):
            raise ValueError("工具调用参数必须是完整 JSON 对象")
    emit("model.end", block_id=block_id)
    return message_chunk_to_message(combined)
