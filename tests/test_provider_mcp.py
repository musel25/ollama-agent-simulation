"""In-memory MCP tests for the provider's tools."""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import Client

from provider.mcp_server import _summarize_args, build_mcp_server
from shared.config import Config

PROVIDER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
PROVIDER_ADDR = Account.from_key(PROVIDER_KEY).address
CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
CONSUMER_ADDR = Account.from_key(CONSUMER_KEY).address


@pytest.fixture
def cfg() -> Config:
    return Config(provider_private_key=PROVIDER_KEY, sdn_mock=True)


@pytest.fixture
def server(cfg):
    mcp, tool_log = build_mcp_server(cfg)
    return mcp, tool_log


@pytest.mark.asyncio
async def test_verify_credential_ownership_happy_path(server):
    mcp, _ = server
    nonce = str(int(time.time()))
    sig = Account.sign_message(encode_defunct(text=nonce),
                               private_key=CONSUMER_KEY).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = CONSUMER_ADDR
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()) - 60, "clab://pe1/ethernet-1/3.0",
    )
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        CONSUMER_ADDR, "0xprov", 5, 600, 0, 0, 7, 2,
    )

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce})
            data = json.loads(result.content[0].text)
            assert data["ok"] is True
            assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_wrong_signer(server):
    mcp, _ = server
    nonce = str(int(time.time()))
    sig = Account.sign_message(encode_defunct(text=nonce),
                               private_key=CONSUMER_KEY).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = (
        "0x000000000000000000000000000000000000dEaD")
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()), "clab://pe1/ethernet-1/3.0")
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        CONSUMER_ADDR, "0xprov", 5, 600, 0, 0, 7, 2)

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce})
            data = json.loads(result.content[0].text)
            assert data["ok"] is False


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_stale_nonce(server):
    mcp, _ = server
    stale = str(int(time.time()) - 9999)
    sig = Account.sign_message(encode_defunct(text=stale),
                               private_key=CONSUMER_KEY).signature.hex()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "verify_credential_ownership",
            {"token_id": 7, "signature": sig, "nonce": stale})
        data = json.loads(result.content[0].text)
        assert data["ok"] is False
        assert "nonce" in data["reason"].lower()


@pytest.mark.asyncio
async def test_mint_credential_returns_token_id(cfg):
    fake_receipt = {"status": 1, "logs": []}
    fake_nft = MagicMock()
    fake_nft.functions.mint.return_value.build_transaction.return_value = {
        "from": "0xprov", "nonce": 0}
    fake_nft.events.Transfer.return_value.process_receipt.return_value = [
        {"args": {"tokenId": 42, "from": "0x0", "to": "0xprov"}}]

    fake_w3 = MagicMock()
    fake_w3.eth.get_transaction_count.return_value = 0
    fake_w3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b"\x00")
    fake_w3.eth.send_raw_transaction.return_value = b"\x00"
    fake_w3.eth.wait_for_transaction_receipt.return_value = fake_receipt

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.make_web3", return_value=fake_w3):
        mcp, _ = build_mcp_server(cfg)
        async with Client(mcp) as client:
            result = await client.call_tool("mint_credential", {
                "agreement_id": 12345,
                "consumer_address": "0x000000000000000000000000000000000000dEaD",
                "pe": "pe1", "subinterface": "ethernet-1/3.0", "ce": "ce3",
                "mbps": 5, "duration_seconds": 600,
            })
            data = json.loads(result.content[0].text)
            assert data["tokenId"] == 42
            assert data["endpoint"] == "clab://pe1/ethernet-1/3.0"


@pytest.mark.asyncio
async def test_complete_swap_calls_approve_then_deposit(cfg):
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
         patch("provider.mcp_server.make_web3", return_value=fake_w3):
        mcp, _ = build_mcp_server(cfg)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "complete_swap", {"agreement_id": 12345, "token_id": 42})
            data = json.loads(result.content[0].text)
            assert data["status"] == "ok"
            fake_nft.functions.approve.assert_called_once_with("0xESCROW", 42)
            fake_escrow.functions.deposit.assert_called_once_with(12345, 42)


@pytest.mark.asyncio
async def test_tool_call_log_records_invocations(server):
    mcp, tool_log = server
    tool_log.clear()
    async with Client(mcp) as client:
        await client.call_tool("get_catalog", {})
    entries = list(tool_log)
    assert len(entries) == 1
    assert entries[0]["tool"] == "get_catalog"
    assert entries[0]["status"] == "ok"


def test_summarize_args_truncates_long_values():
    result = _summarize_args({"x": "a" * 100, "y": "short"})
    assert result["x"].endswith("...")
    assert len(result["x"]) == 80
    assert result["y"] == "short"
