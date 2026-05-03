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


@pytest.mark.asyncio
async def test_settle_node_active(monkeypatch):
    def fake_settle(agreement_id):
        return "OK tokenId=42"
    monkeypatch.setattr(g, "_await_settlement_tool", fake_settle)

    out = await g.settle_node({"agreement_id": "12345", "log": [], "settle_attempts": 0})
    assert out["token_id"] == 42
    assert any("Agreement ACTIVE." in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_settle_node_pending_increments_counter(monkeypatch):
    def fake_settle(agreement_id):
        return "PENDING"
    monkeypatch.setattr(g, "_await_settlement_tool", fake_settle)

    out = await g.settle_node({"agreement_id": "12345", "log": [], "settle_attempts": 0})
    assert "token_id" not in out
    assert out["settle_attempts"] == 1
    assert "error" not in out


@pytest.mark.asyncio
async def test_settle_should_retry_routing():
    assert g._settle_route({"settle_attempts": 0}) == "settle_node"
    assert g._settle_route({"settle_attempts": 2}) == "settle_node"
    assert g._settle_route({"settle_attempts": 3}) == "error_node"
    assert g._settle_route({"token_id": 7, "settle_attempts": 1}) == "present_node"
    assert g._settle_route({"error": "boom"}) == "error_node"


@pytest.mark.asyncio
async def test_present_node(monkeypatch):
    async def fake_present(provider_url, token_id):
        return json.dumps({"status": "active", "bandwidthMbps": 5.0, "tokenId": token_id})
    monkeypatch.setattr(g, "_present_credential_tool", fake_present)

    out = await g.present_node({
        "provider_url": "http://provider:8002", "token_id": 42, "log": [],
    })
    assert out["activation"]["status"] == "active"
    assert any("Gateway response:" in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_summary_node(monkeypatch):
    async def fake_llm(prompt, model):
        return "Done — medium tier (5 Mbps), agreementId=12345, tokenId=42."
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.summary_node({
        "chosen_tier": "medium", "chosen_mbps": 5.0,
        "agreement_id": "12345", "token_id": 42,
        "activation": {"status": "active"},
        "thinking": [], "log": [],
    })
    assert "medium" in out["final_response"]
    assert "42" in out["final_response"]


@pytest.mark.asyncio
async def test_error_node():
    out = await g.error_node({"error": "ouch", "log": []})
    assert "ouch" in out["final_response"]


@pytest.mark.asyncio
async def test_full_graph_happy_path(monkeypatch, fake_catalog):
    async def fake_browse(url):
        return json.dumps(fake_catalog)
    async def fake_quote(url, pkg):
        return json.dumps({"agreementId": "777", "priceWei": 2e16,
                          "bandwidthMbps": 5.0, "durationSeconds": 600})
    def fake_lock(aid):
        return "OK 0xdeadbeef"
    def fake_settle(aid):
        return "OK tokenId=99"
    async def fake_present(url, tid):
        return json.dumps({"status": "active", "bandwidthMbps": 5.0, "tokenId": tid})
    async def fake_llm(prompt, model):
        return "medium" if "Reply with EXACTLY ONE WORD" in prompt else \
               "OK: medium (5 Mbps), agreementId=777, tokenId=99."

    monkeypatch.setattr(g, "_browse_catalog_tool", fake_browse)
    monkeypatch.setattr(g, "_request_quote_tool", fake_quote)
    monkeypatch.setattr(g, "_lock_payment_tool", fake_lock)
    monkeypatch.setattr(g, "_await_settlement_tool", fake_settle)
    monkeypatch.setattr(g, "_present_credential_tool", fake_present)
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    graph = g.build_graph()
    result = await graph.ainvoke({
        "user_message": "I need 5 Mbps",
        "provider_url": "http://provider:8002",
        "model": "qwen3:4b",
        "log": [], "thinking": [],
    })
    assert result["chosen_tier"] == "medium"
    assert result["agreement_id"] == "777"
    assert result["token_id"] == 99
    assert result["activation"]["status"] == "active"
    assert "777" in result["final_response"]
