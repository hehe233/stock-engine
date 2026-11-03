from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.http.dependencies import SessionDep
from app.providers import runner
from app.providers.base import ProviderError
from app.shared.securities import normalize_symbol
from app.shared.time import SHANGHAI, as_utc, utc_now


def test_session_dependency_closes_on_success_and_exception():
    active = set()
    opened = []

    @contextmanager
    def sessions():
        session = object()
        active.add(session)
        opened.append(session)
        try:
            yield session
        finally:
            active.remove(session)

    app = FastAPI()
    app.state.sessions = sessions

    @app.get("/session")
    def endpoint(session: SessionDep, fail: bool = False):
        assert session in active
        if fail:
            raise RuntimeError("expected test failure")
        return {"ok": True}

    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/session").status_code == 200
        assert not active
        assert client.get("/session?fail=true").status_code == 500
        assert not active
    assert len(opened) == 2 and opened[0] is not opened[1]


@pytest.mark.parametrize(
    ("raw", "kind", "expected"),
    [
        (" sh600000 ", "stock", "600000.SH"),
        ("000001", "stock", "000001.SZ"),
        ("920001", "stock", "920001.BJ"),
        ("510300", "etf", "510300.SH"),
        ("SZ399001", "index", "399001.SZ"),
    ],
)
def test_shared_security_formats(raw, kind, expected):
    assert normalize_symbol(raw, kind) == expected


def test_shared_rules_keep_unknown_exchange_and_utc_contract():
    with pytest.raises(ValueError, match="指数代码缺少交易所"):
        normalize_symbol("000001", "index")
    with pytest.raises(ValueError, match="无效代码"):
        normalize_symbol("unknown", "stock")
    naive = datetime(2026, 1, 2, 8)
    assert as_utc(naive) == naive.replace(tzinfo=UTC)
    assert as_utc(naive.replace(tzinfo=timezone(timedelta(hours=8)))).hour == 0
    assert utc_now().tzinfo == UTC
    assert str(SHANGHAI) == "Asia/Shanghai"


def test_collector_preserves_arguments_result_and_temporary_cleanup(monkeypatch):
    outputs = []

    def run(command, **options):
        assert command[1:3] == ["-m", "app.providers.collect"]
        assert options["timeout"] == 12
        assert options["capture_output"] and not options["check"]
        assert Path(options["cwd"]).name == "api"
        assert command[command.index("--query") + 1] == '{"symbol": "600000.SH"}'
        output = Path(command[command.index("--output") + 1])
        outputs.append(output)
        output.write_text('{"rows": []}', encoding="utf-8")
        return CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", run)
    assert runner.run_collector("research", "sina", 12, {"symbol": "600000.SH"}) == {"rows": []}
    assert not outputs[0].parent.exists()


@pytest.mark.parametrize("failure", ["timeout", "exit", "missing", "payload"])
def test_collector_preserves_safe_failure_and_cleanup(monkeypatch, failure):
    outputs = []

    def run(command, **options):
        output = Path(command[command.index("--output") + 1])
        outputs.append(output)
        if failure == "timeout":
            raise TimeoutExpired(command, options["timeout"])
        if failure == "payload":
            output.write_text('{"error": "Unavailable"}', encoding="utf-8")
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)

    monkeypatch.setattr(runner.subprocess, "run", run)
    with pytest.raises(ProviderError):
        runner.run_collector("stock", "sina", 5)
    assert not outputs[0].parent.exists()
