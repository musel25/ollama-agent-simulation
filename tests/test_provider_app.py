"""HTTP-level tests for provider/app.py routes that don't need anvil."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    # Provider app needs PROVIDER_PRIVATE_KEY at import time.
    monkeypatch.setenv(
        "PROVIDER_PRIVATE_KEY",
        "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    )
    monkeypatch.setenv("SDN_MOCK", "true")
    from provider.app import app
    with TestClient(app) as c:
        yield c


def test_tool_log_returns_recorded_entries(client):
    from provider import mcp_server
    mcp_server.tool_call_log.clear()
    mcp_server.tool_call_log.append({
        "tool": "get_catalog", "ts": 1.0, "args": {}, "status": "ok",
    })

    resp = client.get("/tool_log")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[-1]["tool"] == "get_catalog"
    assert data[-1]["status"] == "ok"


def test_tool_log_since_ts_filters(client):
    from provider import mcp_server
    mcp_server.tool_call_log.clear()
    mcp_server.tool_call_log.append({"tool": "a", "ts": 1.0, "args": {}, "status": "ok"})
    mcp_server.tool_call_log.append({"tool": "b", "ts": 5.0, "args": {}, "status": "ok"})

    resp = client.get("/tool_log", params={"since_ts": 2.0})
    assert resp.status_code == 200
    data = resp.json()
    assert [e["tool"] for e in data] == ["b"]


def test_tool_log_since_ts_excludes_equal_timestamps(client):
    from provider import mcp_server
    mcp_server.tool_call_log.clear()
    mcp_server.tool_call_log.append({"tool": "a", "ts": 1.0, "args": {}, "status": "ok"})
    resp = client.get("/tool_log", params={"since_ts": 1.0})
    assert resp.status_code == 200
    assert resp.json() == []  # strict > means equal-ts entries are excluded
