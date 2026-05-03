"""Unit tests for consumer/graph.py nodes. MCP tool functions are monkey-patched."""
import json
import pytest

from consumer import graph as g


@pytest.fixture
def fake_catalog():
    return [
        {"packageId": "small",  "mbps": 2.0, "durationSeconds": 600, "priceWei": 10**16, "availableSlots": 1},
        {"packageId": "medium", "mbps": 5.0, "durationSeconds": 600, "priceWei": 2 * 10**16, "availableSlots": 1},
        {"packageId": "large",  "mbps": 8.0, "durationSeconds": 600, "priceWei": 8 * 10**16, "availableSlots": 1},
    ]


@pytest.mark.asyncio
async def test_browse_node_populates_catalog(monkeypatch, fake_catalog):
    async def fake_browse(provider_url):
        return json.dumps(fake_catalog)
    monkeypatch.setattr(g, "_browse_catalog_tool", fake_browse)

    state = {"provider_url": "http://provider:8002", "log": []}
    out = await g.browse_node(state)

    assert out["catalog"] == fake_catalog
    assert any("[MCP] browse_catalog" in e["message"] for e in out["log"])
    assert any(e["from"] == "provider" for e in out["log"])
    assert "error" not in out


@pytest.mark.asyncio
async def test_browse_node_handles_error(monkeypatch):
    async def fake_browse(provider_url):
        return "ERROR: provider unreachable"
    monkeypatch.setattr(g, "_browse_catalog_tool", fake_browse)

    out = await g.browse_node({"provider_url": "http://x", "log": []})
    assert out["error"]
    assert "provider unreachable" in out["error"]
