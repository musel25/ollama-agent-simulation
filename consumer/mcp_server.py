"""
Consumer agent's MCP server.

Tools:
  Local (no network):
    - wallet_address()         → consumer EOA
    - sign_message(text)       → ECDSA hex signature
    - lock_payment(agreement_id)
    - await_settlement(agreement_id, max_attempts)
  A2A-bound (network to provider):
    - browse_catalog(provider_url)
    - request_quote(provider_url, package_id)
    - present_credential(provider_url, token_id)
"""
from __future__ import annotations

import json
import os
import time

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from consumer.a2a_client import send_provider_action
from shared.contracts import get_escrow_contract

mcp = FastMCP("bandwidth-consumer")

_RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
_CONSUMER_KEY = os.environ.get("CONSUMER_PRIVATE_KEY")
_w3 = Web3(Web3.HTTPProvider(_RPC_URL))
_consumer_account = Account.from_key(_CONSUMER_KEY) if _CONSUMER_KEY else None

_STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}

quote_cache: dict[str, dict] = {}


def _send_consumer_tx(func, value: int = 0) -> str:
    if _consumer_account is None:
        raise RuntimeError("CONSUMER_PRIVATE_KEY not set")
    tx = func.build_transaction({
        "from": _consumer_account.address,
        "nonce": _w3.eth.get_transaction_count(_consumer_account.address, "pending"),
        "value": value,
    })
    signed = _w3.eth.account.sign_transaction(tx, _CONSUMER_KEY)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    h = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(h, timeout=60)
    if receipt["status"] != 1:
        raise RuntimeError(f"tx reverted: {h.hex() if hasattr(h, 'hex') else h}")
    return h.hex() if hasattr(h, "hex") else str(h)


async def _fetch_provider_address(provider_url: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(f"{provider_url}/address")
        resp.raise_for_status()
        return resp.json()["address"]


@mcp.tool()
def wallet_address() -> str:
    """Return the consumer agent's Ethereum address (0x...)."""
    if _consumer_account is None:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    return _consumer_account.address


@mcp.tool()
def sign_message(text: str) -> str:
    """Sign an arbitrary text with the consumer's EOA. Returns hex signature."""
    if _consumer_account is None or not _CONSUMER_KEY:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    msg = encode_defunct(text=text)
    return Account.sign_message(msg, private_key=_CONSUMER_KEY).signature.hex()


@mcp.tool()
def lock_payment(agreement_id: str) -> str:
    """
    Send escrow.requestAgreement on chain using the cached quote.
    Returns "OK <txHash>" on success, "ERROR ..." otherwise.
    """
    quote = quote_cache.get(str(agreement_id))
    if not quote:
        return f"ERROR: no cached quote for agreementId={agreement_id}. Call request_quote first."
    try:
        provider_addr = quote.get("providerAddress")
        if not provider_addr:
            return "ERROR: cached quote has no providerAddress"
        escrow = get_escrow_contract(_w3)
        tx = _send_consumer_tx(
            escrow.functions.requestAgreement(
                int(agreement_id),
                Web3.to_checksum_address(provider_addr),
                int(quote["bandwidthMbps"]),
                int(quote["durationSeconds"]),
            ),
            value=int(quote["priceWei"]),
        )
        return f"OK {tx}"
    except Exception as e:
        return f"ERROR: {e}"


_SETTLEMENT_POLL_ATTEMPTS = 20
_SETTLEMENT_POLL_INTERVAL_S = 1.5


@mcp.tool()
def await_settlement(agreement_id: str) -> str:
    """
    Poll escrow.getAgreement until status==ACTIVE (~30s max).
    Returns "OK tokenId=N", "ERROR ...", or "PENDING".
    """
    try:
        aid = int(agreement_id)
    except (ValueError, TypeError):
        return f"ERROR: agreement_id must be a number, got {agreement_id!r}"
    escrow = get_escrow_contract(_w3)
    for _ in range(_SETTLEMENT_POLL_ATTEMPTS):
        try:
            ag = escrow.functions.getAgreement(aid).call()
            status = _STATUS_NAMES.get(ag[7], "UNKNOWN")
            if status == "ACTIVE":
                return f"OK tokenId={ag[6]}"
            if status in ("CANCELLED", "CLOSED"):
                return f"ERROR: agreement is {status}"
        except Exception as e:
            return f"ERROR reading agreement: {e}"
        time.sleep(_SETTLEMENT_POLL_INTERVAL_S)
    return "PENDING"


@mcp.tool()
async def browse_catalog(provider_url: str) -> str:
    """
    Discover provider's catalog via A2A.
    Returns JSON array of {packageId, mbps, durationSeconds, priceWei, availableSlots}.
    """
    try:
        result = await send_provider_action(provider_url, {"action": "get_catalog"})
        catalog = result.get("catalog")
        if catalog is None:
            return f"ERROR: provider response missing 'catalog' key: {result}"
        return json.dumps(catalog)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
async def request_quote(provider_url: str, package_id: str) -> str:
    """
    Request a price quote for a package via A2A. Caches the quote so
    lock_payment can find it.
    Returns {agreementId, priceWei, bandwidthMbps, durationSeconds}.
    """
    if _consumer_account is None:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    try:
        provider_addr = await _fetch_provider_address(provider_url)
        result = await send_provider_action(provider_url, {
            "action": "request_quote",
            "package_id": package_id,
            "consumer_address": _consumer_account.address,
        })
        if "error" in result:
            return f"ERROR: {result['error']}"
        quote_cache[str(result["agreementId"])] = {
            **result,
            "providerAddress": provider_addr,
        }
        return json.dumps(result)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
async def present_credential(provider_url: str, token_id: int) -> str:
    """
    Sign a fresh nonce, send 'activate' over A2A, return service metadata.
    """
    if _consumer_account is None or not _CONSUMER_KEY:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    nonce = str(int(time.time()))
    sig = Account.sign_message(encode_defunct(text=nonce),
                               private_key=_CONSUMER_KEY).signature.hex()
    try:
        result = await send_provider_action(provider_url, {
            "action": "activate",
            "token_id": int(token_id),
            "nonce": nonce,
            "signature": sig,
        })
        return json.dumps(result)
    except Exception as e:
        return f"ERROR: {e}"
