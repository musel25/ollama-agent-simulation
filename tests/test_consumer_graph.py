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


@pytest.mark.asyncio
async def test_pick_tier_explicit_word(monkeypatch, fake_catalog):
    async def fake_llm(prompt: str, model: str) -> str:
        return "medium"
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.pick_tier_node({
        "user_message": "I want medium please",
        "catalog": fake_catalog,
        "log": [],
    })
    assert out["chosen_tier"] == "medium"
    assert out["chosen_mbps"] == 5.0


@pytest.mark.asyncio
async def test_pick_tier_numeric_request_falls_back_to_rule(monkeypatch, fake_catalog):
    # Even if the LLM returns garbage, the deterministic fallback picks the
    # smallest tier whose mbps >= user's requested number.
    async def fake_llm(prompt, model):
        return "I think probably the great one"  # not parseable
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.pick_tier_node({
        "user_message": "I need 4 Mbps",
        "catalog": fake_catalog,
        "log": [],
    })
    assert out["chosen_tier"] == "medium"


@pytest.mark.asyncio
async def test_pick_tier_request_exceeds_largest(monkeypatch, fake_catalog):
    async def fake_llm(prompt, model):
        return "???"
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.pick_tier_node({
        "user_message": "I need 100 Mbps",
        "catalog": fake_catalog,
        "log": [],
    })
    assert out["chosen_tier"] == "large"


@pytest.mark.asyncio
async def test_quote_node(monkeypatch):
    async def fake_quote(provider_url, package_id):
        return json.dumps({
            "agreementId": "12345",
            "priceWei": 2 * 10**16,
            "bandwidthMbps": 5.0,
            "durationSeconds": 600,
        })
    monkeypatch.setattr(g, "_request_quote_tool", fake_quote)

    out = await g.quote_node({
        "provider_url": "http://provider:8002",
        "chosen_tier": "medium",
        "log": [],
    })
    assert out["agreement_id"] == "12345"
    assert any("[MCP] request_quote" in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_quote_node_propagates_error(monkeypatch):
    async def fake_quote(provider_url, package_id):
        return "ERROR: tier sold out"
    monkeypatch.setattr(g, "_request_quote_tool", fake_quote)

    out = await g.quote_node({
        "provider_url": "http://x", "chosen_tier": "medium", "log": [],
    })
    assert "tier sold out" in out["error"]


@pytest.mark.asyncio
async def test_lock_node(monkeypatch):
    def fake_lock(agreement_id):
        return "OK 0xabc123"
    monkeypatch.setattr(g, "_lock_payment_tool", fake_lock)

    out = await g.lock_node({"agreement_id": "12345", "log": []})
    assert out["tx_hash"] == "0xabc123"
    assert any("requestAgreement() sent." in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_lock_node_propagates_error(monkeypatch):
    def fake_lock(agreement_id):
        return "ERROR: insufficient funds"
    monkeypatch.setattr(g, "_lock_payment_tool", fake_lock)

    out = await g.lock_node({"agreement_id": "12345", "log": []})
    assert "insufficient funds" in out["error"]
