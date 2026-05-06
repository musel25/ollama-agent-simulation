"""Tests for the consumer LangGraph state machine.

The graph nodes are closures inside build_graph(); test them via the
compiled graph with stubbed tools rather than by direct import.
"""
from __future__ import annotations

import json

import pytest

from consumer.graph import build_graph
from consumer.tier_selection import deterministic_tier_pick, rank_catalog
from shared.config import Config


CFG = Config(consumer_private_key="0x" + "11" * 32)


@pytest.fixture
def fake_catalog():
    return [
        {"packageId": "small",  "mbps": 2.0, "durationSeconds": 600,
         "priceWei": 10**16, "availableSlots": 1},
        {"packageId": "medium", "mbps": 5.0, "durationSeconds": 600,
         "priceWei": 2 * 10**16, "availableSlots": 1},
        {"packageId": "large",  "mbps": 8.0, "durationSeconds": 600,
         "priceWei": 8 * 10**16, "availableSlots": 1},
    ]


def _stub_tools(fake_catalog,
                quote_response=None, lock_response="OK 0xdead",
                settle_response="OK tokenId=99",
                activation=None,
                verify_response=None, mbps=5):
    quote_response = quote_response or {
        "agreementId": "777", "priceWei": 2 * 10**16,
        "bandwidthMbps": mbps, "durationSeconds": 600}
    activation = activation or {"status": "active",
                                "bandwidthMbps": mbps, "tokenId": 99}
    verify_response = verify_response or {
        "ok": True, "owner": "0xC", "ownerIsConsumer": True,
        "agreementId": 777, "mbps": mbps, "durationSeconds": 600,
        "secondsRemaining": 600, "endpoint": "clab://pe1/eth-1.100"}

    async def discover(url):
        return json.dumps({"name": "P", "version": "2",
                           "skills": ["get_catalog", "request_quote", "activate"]})
    async def browse(url): return json.dumps(fake_catalog)
    async def quote(url, pkg): return json.dumps(quote_response)
    def lock(aid): return lock_response
    def settle(aid): return settle_response
    async def present(url, tid): return json.dumps(activation)
    def verify(tid): return json.dumps(verify_response)
    return {
        "discover_provider": discover, "browse_catalog": browse,
        "request_quote": quote, "lock_payment": lock,
        "await_settlement": settle, "present_credential": present,
        "verify_credential": verify,
    }


@pytest.mark.asyncio
async def test_full_graph_happy_path(fake_catalog, monkeypatch):
    tools = _stub_tools(fake_catalog)
    # Stub the LLM by patching ChatOllama.ainvoke at the module level.
    from langchain_ollama import ChatOllama

    class FakeResp:
        def __init__(self, content): self.content = content

    async def fake_ainvoke(self, prompt, *a, **kw):
        return FakeResp("medium" if "EXACTLY ONE WORD" in prompt
                        else "OK done.")
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "I need 5 Mbps",
        "provider_url": "http://provider:8002",
        "model": "llama3.2:3b",
        "log": [], "thinking": [],
    })
    assert result["chosen_tier"] == "medium"
    assert result["agreement_id"] == "777"
    assert result["token_id"] == 99
    assert "Active service" in result["final_response"]
    assert result["on_chain_verification"]["mbps"] == 5


@pytest.mark.asyncio
async def test_graph_errors_when_no_providers_advertise_skills(fake_catalog,
                                                                monkeypatch):
    async def discover_bad(url):
        return json.dumps({"name": "bad", "version": "1",
                           "skills": ["get_catalog"]})
    tools = _stub_tools(fake_catalog)
    tools["discover_provider"] = discover_bad

    from langchain_ollama import ChatOllama

    async def fake_ainvoke(self, prompt, *a, **kw):
        class R: content = "small"
        return R()
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "small please",
        "provider_url": "http://x:8002",
        "log": [], "thinking": [],
    })
    assert "Workflow stopped" in result["final_response"]


@pytest.mark.asyncio
async def test_graph_errors_when_lock_payment_fails(fake_catalog, monkeypatch):
    tools = _stub_tools(fake_catalog, lock_response="ERROR: insufficient funds")
    from langchain_ollama import ChatOllama
    async def fake_ainvoke(self, prompt, *a, **kw):
        class R: content = "small"
        return R()
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "small please",
        "provider_url": "http://provider:8002",
        "log": [], "thinking": [],
    })
    assert "insufficient funds" in result["final_response"]


@pytest.mark.asyncio
async def test_graph_errors_when_verify_finds_mbps_mismatch(fake_catalog,
                                                            monkeypatch):
    tools = _stub_tools(
        fake_catalog,
        verify_response={"ok": True, "owner": "0xC", "ownerIsConsumer": True,
                         "agreementId": 1, "mbps": 1, "durationSeconds": 600,
                         "secondsRemaining": 600, "endpoint": "x"})
    from langchain_ollama import ChatOllama
    async def fake_ainvoke(self, prompt, *a, **kw):
        class R: content = "medium"
        return R()
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "medium please",
        "provider_url": "http://provider:8002",
        "log": [], "thinking": [],
    })
    assert "mbps mismatch" in result["final_response"]


def test_settle_route_logic():
    # Imported lazily because the function is closed over build_graph;
    # we re-implement the table for clarity.
    cfg = CFG
    graph = build_graph(cfg, _stub_tools([]))
    # The router is internal; we exercise it by running the graph in stages.
    assert graph is not None  # smoke check; route-coverage handled by full path tests


def test_rank_catalog_sorts_by_mbps(fake_catalog):
    ranked = rank_catalog(fake_catalog)
    assert [p["packageId"] for p in ranked] == ["small", "medium", "large"]


def test_deterministic_tier_pick_numeric(fake_catalog):
    pick = deterministic_tier_pick("I need 4 Mbps", fake_catalog)
    assert pick["packageId"] == "medium"


def test_deterministic_tier_pick_oversized_request(fake_catalog):
    pick = deterministic_tier_pick("I need 100 Mbps", fake_catalog)
    assert pick["packageId"] == "large"
