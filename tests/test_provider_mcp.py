"""
In-memory MCP tests for the provider's tools.

These tests instantiate the provider's FastMCP server and call its tools
via Client(mcp) — no network involved. Tools that touch web3 are mocked
where the test doesn't need a live chain.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import Client


@pytest.fixture
def consumer_key() -> str:
    return "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"


@pytest.fixture
def consumer_address(consumer_key: str) -> str:
    return Account.from_key(consumer_key).address


@pytest.mark.asyncio
async def test_verify_credential_ownership_happy_path(consumer_key, consumer_address):
    nonce = str(int(time.time()))
    msg = encode_defunct(text=nonce)
    sig = Account.sign_message(msg, private_key=consumer_key).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = consumer_address
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()) - 60, "clab://pe1/ethernet-1/3.0",
    )
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        consumer_address, "0xprov", 5, 600, 0, 0, 7, 2,
    )

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce},
            )
            data = json.loads(result.content[0].text)
            assert data["ok"] is True
            assert data["signer"].lower() == consumer_address.lower()
            assert data["status"] == "ACTIVE"
            assert data["mbps"] == 5


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_wrong_signer(consumer_key, consumer_address):
    nonce = str(int(time.time()))
    msg = encode_defunct(text=nonce)
    sig = Account.sign_message(msg, private_key=consumer_key).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = (
        "0x000000000000000000000000000000000000dEaD"
    )
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()), "clab://pe1/ethernet-1/3.0")
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        consumer_address, "0xprov", 5, 600, 0, 0, 7, 2)

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce},
            )
            data = json.loads(result.content[0].text)
            assert data["ok"] is False


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_stale_nonce(consumer_key):
    stale_nonce = str(int(time.time()) - 9999)
    msg = encode_defunct(text=stale_nonce)
    sig = Account.sign_message(msg, private_key=consumer_key).signature.hex()

    from provider.mcp_server import mcp
    async with Client(mcp) as client:
        result = await client.call_tool(
            "verify_credential_ownership",
            {"token_id": 7, "signature": sig, "nonce": stale_nonce},
        )
        data = json.loads(result.content[0].text)
        assert data["ok"] is False
        assert "nonce" in data["reason"].lower()


@pytest.mark.asyncio
async def test_mint_credential_returns_token_id():
    fake_receipt = {"status": 1, "logs": []}
    fake_nft = MagicMock()
    fake_nft.functions.mint.return_value.build_transaction.return_value = {"from": "0xprov", "nonce": 0}
    # shared.chain.extract_token_id decodes via nft.events.Transfer().process_receipt(...)
    fake_nft.events.Transfer.return_value.process_receipt.return_value = [
        {"args": {"tokenId": 42, "from": "0x0", "to": "0xprov"}},
    ]

    fake_w3 = MagicMock()
    fake_w3.eth.get_transaction_count.return_value = 0
    fake_w3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b"\x00")
    fake_w3.eth.send_raw_transaction.return_value = b"\x00"
    fake_w3.eth.wait_for_transaction_receipt.return_value = fake_receipt

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server._w3", fake_w3), \
         patch("provider.mcp_server._provider_account",
               MagicMock(address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8")), \
         patch("provider.mcp_server._provider_key", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mint_credential",
                {
                    "agreement_id": 12345,
                    "consumer_address": "0x000000000000000000000000000000000000dEaD",
                    "pe": "pe1",
                    "subinterface": "ethernet-1/3.0",
                    "ce": "ce3",
                    "mbps": 5,
                    "duration_seconds": 600,
                },
            )
            data = json.loads(result.content[0].text)
            assert data["tokenId"] == 42
            assert data["endpoint"] == "clab://pe1/ethernet-1/3.0"


@pytest.mark.asyncio
async def test_complete_swap_calls_approve_then_deposit():
    fake_nft = MagicMock()
    fake_escrow = MagicMock()
    fake_escrow.address = "0xESCROW"

    fake_w3 = MagicMock()
    fake_w3.eth.get_transaction_count.return_value = 0
    fake_w3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b"\x00")
    fake_w3.eth.send_raw_transaction.return_value = b"\x00"
    fake_w3.eth.wait_for_transaction_receipt.return_value = {"status": 1, "logs": []}

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow), \
         patch("provider.mcp_server._w3", fake_w3), \
         patch("provider.mcp_server._provider_account",
               MagicMock(address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8")), \
         patch("provider.mcp_server._provider_key", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "complete_swap",
                {"agreement_id": 12345, "token_id": 42},
            )
            data = json.loads(result.content[0].text)
            assert data["status"] == "ok"
            assert "approveTx" in data
            assert "depositTx" in data
            fake_nft.functions.approve.assert_called_once_with("0xESCROW", 42)
            fake_escrow.functions.deposit.assert_called_once_with(12345, 42)


@pytest.mark.asyncio
async def test_tool_call_log_records_invocations():
    from provider import mcp_server
    mcp_server.tool_call_log.clear()

    from provider.mcp_server import mcp
    async with Client(mcp) as client:
        await client.call_tool("get_catalog", {})

    entries = list(mcp_server.tool_call_log)
    assert len(entries) == 1
    assert entries[0]["tool"] == "get_catalog"
    assert entries[0]["status"] == "ok"
    assert "ts" in entries[0]


def test_summarize_args_truncates_long_values():
    from provider.mcp_server import _summarize_args
    result = _summarize_args({"x": "a" * 100, "y": "short"})
    assert result["x"].endswith("...")
    assert len(result["x"]) == 80   # 77 chars + "..."
    assert result["y"] == "short"


@pytest.mark.asyncio
async def test_tool_call_log_records_errors():
    from provider import mcp_server
    mcp_server.tool_call_log.clear()

    # Define a sync tool inside a fresh FastMCP server, decorated with
    # _logged, that raises. Verify the entry's status flips to 'error'.
    from fastmcp import FastMCP
    test_mcp = FastMCP("test")

    @test_mcp.tool()
    @mcp_server._logged
    def buggy() -> str:
        raise RuntimeError("kaboom")

    with pytest.raises(Exception):
        async with Client(test_mcp) as client:
            await client.call_tool("buggy", {})

    entries = list(mcp_server.tool_call_log)
    assert any(e["tool"] == "buggy" and e["status"] == "error" for e in entries)
