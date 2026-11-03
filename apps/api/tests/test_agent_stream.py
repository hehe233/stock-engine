"""Exercise real model SSE, graph persistence and replay without external model calls."""

import json

import httpx
import pytest
from sqlalchemy import select

from app.agents.models import ChatOpenAI
from app.agents.run_job import execute_job
from app.db import JobEvent
from app.jobs.service import claim_job, finish_failed


def make_stream_model(*, bad_reference=False, disconnect=False):
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        assert body["stream"] is True
        if len(requests) == 1:
            deltas = [
                {"role": "assistant", "content": "", "reasoning_content": "先读取"},
                {"reasoning_content": "行情证据。"},
                {"content": "正在核验"},
                {"content": "行情与数据时间。"},
                {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "quote-call",
                            "type": "function",
                            "function": {"name": "read_quote", "arguments": "{"},
                        }
                    ]
                },
                {"tool_calls": [{"index": 0, "function": {"arguments": "}"}}]},
            ]
        elif len(requests) == 2:
            assert any(item["role"] == "tool" for item in body["messages"])
            deltas = [{"role": "assistant", "content": "证据已取得。"}]
        else:
            assert body["tool_choice"]["function"]["name"] == "ModelInsight"
            report = json.dumps(
                {
                    "summary": "根据当前快照，样本活跃，但不能推断连板概率。" * 8,
                    "observations": [
                        {
                            "text": "标的是演示样本。",
                            "evidence_ids": ["invented" if bad_reference else "read_quote"],
                        }
                    ],
                    "limitations": ["样本不代表真实市场。"],
                },
                ensure_ascii=False,
            )
            deltas = [{"role": "assistant", "reasoning_content": "整理引用证据。"}]
            for offset in range(0, len(report), 2):
                call = {"index": 0, "function": {"arguments": report[offset : offset + 2]}}
                if offset == 0:
                    call.update(id="report-call", type="function")
                    call["function"]["name"] = "ModelInsight"
                deltas.append({"tool_calls": [call]})
            if disconnect:
                deltas = deltas[:12]
        chunks = [
            json.dumps(
                {
                    "id": f"completion-{len(requests)}",
                    "object": "chat.completion.chunk",
                    "created": 1,
                    "model": "stream-test",
                    "choices": [
                        {
                            "index": 0,
                            "delta": delta,
                            "finish_reason": None,
                        }
                    ],
                },
                ensure_ascii=False,
            )
            for delta in deltas
        ]
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text="".join(f"data: {chunk}\n\n" for chunk in chunks) + "data: [DONE]\n\n",
        )

    http_client = httpx.Client(transport=httpx.MockTransport(respond))
    return (
        ChatOpenAI(
            model="stream-test",
            api_key="test-only",
            http_client=http_client,
            base_url="https://stream.example/v1",
            max_retries=0,
        ),
        http_client,
        requests,
    )


def submit_and_claim(client, settings):
    market = client.get("/api/market/quotes").json()
    job = client.post(
        "/api/jobs",
        json={"symbol": "DEMO001", "snapshot_id": market["snapshot_id"], "mode": "ollama"},
    ).json()
    claimed = claim_job(client.app.state.sessions, settings)
    assert claimed[0] == job["id"]
    return job, claimed


def read_events(client, job_id):
    with client.app.state.sessions() as session:
        return list(
            session.scalars(select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.id))
        )


def test_real_stream_preserves_reasoning_tools_text_and_partial_report(client, settings):
    job, claimed = submit_and_claim(client, settings)
    model, transport, requests = make_stream_model()
    try:
        execute_job(client.app.state.sessions, settings, *claimed, model_factory=lambda *_: model)
    finally:
        transport.close()
    assert len(requests) == 3
    events = read_events(client, job["id"])
    reasoning = "".join(e.payload["text"] for e in events if e.kind == "reasoning.delta")
    assert reasoning == "先读取行情证据。整理引用证据。"
    assert (
        "".join(e.payload["text"] for e in events if e.kind == "content.delta")
        == "正在核验行情与数据时间。证据已取得。"
    )
    start = next(e for e in events if e.kind == "tool.start")
    end = next(e for e in events if e.kind == "tool.end")
    assert start.id < end.id
    assert start.payload["call_id"] == end.payload["call_id"] == "quote-call"
    assert end.payload["result"]["quote"]["symbol"] == "DEMO001"
    previews = [e.payload["insight"] for e in events if e.kind == "report.delta"]
    assert len(previews) > 10
    assert len(previews[2].get("summary", "")) < len(previews[-1]["summary"])
    report = client.get(f"/api/analyses/{job['id']}").json()
    assert report["insight"] == previews[-1]
    # More than one DB page must be drained before 'done'.
    assert len(events) > 100
    replay = client.get(f"/api/jobs/{job['id']}/events").text
    ids = [int(line[4:]) for line in replay.splitlines() if line.startswith("id: ")]
    assert ids == [e.id for e in events]
    resumed = client.get(
        f"/api/jobs/{job['id']}/events", headers={"Last-Event-ID": str(ids[30])}
    ).text
    assert [int(line[4:]) for line in resumed.splitlines() if line.startswith("id: ")] == ids[31:]
    assert replay.rstrip().endswith('data: {"status": "succeeded"}')


@pytest.mark.parametrize("bad_reference,disconnect", [(True, False), (False, True)])
def test_invalid_or_truncated_stream_keeps_draft_but_never_saves_report(
    client, settings, bad_reference, disconnect
):
    job, claimed = submit_and_claim(client, settings)
    model, transport, _ = make_stream_model(bad_reference=bad_reference, disconnect=disconnect)
    try:
        with pytest.raises(ValueError):
            execute_job(
                client.app.state.sessions, settings, *claimed, model_factory=lambda *_: model
            )
    finally:
        transport.close()
    finish_failed(client.app.state.sessions, *claimed, "测试：模型输出未通过校验")
    assert client.get(f"/api/analyses/{job['id']}").status_code == 404
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "failed"
    assert any(e.kind == "report.delta" for e in read_events(client, job["id"]))
