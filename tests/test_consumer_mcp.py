"""
In-memory MCP tests for the consumer's tools.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import Client


CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
CONSUMER_ADDR = Account.from_key(CONSUMER_KEY).address


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("CONSUMER_PRIVATE_KEY", CONSUMER_KEY)
    monkeypatch.setenv("RPC_URL", "http://localhost:8545")


@pytest.mark.asyncio
async def test_wallet_address_returns_consumer_eoa():
    from consumer.mcp_server import mcp
    async with Client(mcp) as c:
        result = await c.call_tool("wallet_address", {})
        assert result.content[0].text.lower() == CONSUMER_ADDR.lower()


@pytest.mark.asyncio
async def test_sign_message_recoverable():
    from consumer.mcp_server import mcp
    async with Client(mcp) as c:
        result = await c.call_tool("sign_message", {"text": "hello"})
        sig = result.content[0].text
        recovered = Account.recover_message(encode_defunct(text="hello"), signature=sig)
        assert recovered.lower() == CONSUMER_ADDR.lower()


@pytest.mark.asyncio
async def test_lock_payment_rejects_uncached_quote():
    from consumer.mcp_server import mcp, quote_cache
    quote_cache.clear()
    async with Client(mcp) as c:
        result = await c.call_tool("lock_payment", {"agreement_id": "999999"})
        assert "ERROR" in result.content[0].text


@pytest.mark.asyncio
async def test_browse_catalog_calls_provider_a2a():
    expected = {"catalog": [{"packageId": "small", "mbps": 2, "durationSeconds": 600,
                             "priceWei": 10000000000000000, "availableSlots": 1}]}

    async def fake_send(provider_url, payload):
        assert payload == {"action": "get_catalog"}
        return expected

    with patch("consumer.mcp_server.send_provider_action", new=fake_send):
        from consumer.mcp_server import mcp
        async with Client(mcp) as c:
            result = await c.call_tool("browse_catalog",
                                       {"provider_url": "http://prov:8002"})
            data = json.loads(result.content[0].text)
            assert data == expected["catalog"]


@pytest.mark.asyncio
async def test_request_quote_caches_for_lock_payment():
    response = {
        "agreementId": "999",
        "priceWei": 10000000000000000,
        "bandwidthMbps": 2,
        "durationSeconds": 600,
    }

    async def fake_send(provider_url, payload):
        return response

    async def fake_fetch(url):
        return "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

    with patch("consumer.mcp_server.send_provider_action", new=fake_send), \
         patch("consumer.mcp_server._fetch_provider_address", new=fake_fetch):
        from consumer.mcp_server import mcp, quote_cache
        quote_cache.clear()
        async with Client(mcp) as c:
            result = await c.call_tool("request_quote", {
                "provider_url": "http://prov:8002",
                "package_id": "small",
            })
            data = json.loads(result.content[0].text)
            assert data["agreementId"] == "999"
            cached = quote_cache["999"]
            assert cached["providerAddress"] == "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
