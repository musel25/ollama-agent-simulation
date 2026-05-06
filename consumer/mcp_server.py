"""
Consumer agent's MCP server.

Tools:
  Local (no network):
    - wallet_address()         → consumer EOA
    - lock_payment(agreement_id)
    - await_settlement(agreement_id)
    - verify_credential(token_id) — independent on-chain check
  A2A-bound (network to provider):
    - discover_provider(provider_url)
    - browse_catalog(provider_url)
    - request_quote(provider_url, package_id)
    - present_credential(provider_url, token_id)
"""
from __future__ import annotations

import json
import time

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from consumer.a2a_client import fetch_agent_card, send_provider_action
from shared.chain import STATUS_NAMES, make_web3, send_tx
from shared.config import Config
from shared.contracts import get_escrow_contract, get_nft_contract


# Settlement polling: 20 attempts × 1.5s ≈ 30s upper bound.
_SETTLEMENT_POLL_ATTEMPTS = 20
_SETTLEMENT_POLL_INTERVAL_S = 1.5


async def _fetch_provider_address(provider_url: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(f"{provider_url}/address")
        resp.raise_for_status()
        return resp.json()["address"]


def build_mcp_server(cfg: Config) -> tuple[FastMCP, dict]:
    """Build the consumer FastMCP server bound to `cfg`.

    Returns ``(mcp, quote_cache)``. The quote_cache is exposed so tests
    can inspect cached quotes after `request_quote` calls.
    """
    if not cfg.consumer_private_key:
        raise RuntimeError("Config.consumer_private_key is required")

    mcp = FastMCP("bandwidth-consumer")
    quote_cache: dict[str, dict] = {}
    w3 = make_web3(cfg)
    consumer_account = Account.from_key(cfg.consumer_private_key)
    consumer_key = cfg.consumer_private_key

    @mcp.tool()
    def wallet_address() -> str:
        """Return the consumer agent's Ethereum address (0x...)."""
        return consumer_account.address

    @mcp.tool()
    def lock_payment(agreement_id: str) -> str:
        """Send escrow.requestAgreement using the cached quote.
        Returns "OK <txHash>" on success, "ERROR ..." otherwise."""
        quote = quote_cache.get(str(agreement_id))
        if not quote:
            return (f"ERROR: no cached quote for agreementId={agreement_id}. "
                    "Call request_quote first.")
        provider_addr = quote.get("providerAddress")
        if not provider_addr:
            return "ERROR: cached quote has no providerAddress"
        try:
            escrow = get_escrow_contract(w3)
            tx_hex, _ = send_tx(
                w3, consumer_account, consumer_key,
                escrow.functions.requestAgreement(
                    int(agreement_id),
                    Web3.to_checksum_address(provider_addr),
                    int(quote["bandwidthMbps"]),
                    int(quote["durationSeconds"])),
                value=int(quote["priceWei"]))
            return f"OK {tx_hex}"
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def await_settlement(agreement_id: str) -> str:
        """Poll escrow.getAgreement until status==ACTIVE (~30s max)."""
        try:
            aid = int(agreement_id)
        except (ValueError, TypeError):
            return f"ERROR: agreement_id must be a number, got {agreement_id!r}"
        escrow = get_escrow_contract(w3)
        for _ in range(_SETTLEMENT_POLL_ATTEMPTS):
            try:
                ag = escrow.functions.getAgreement(aid).call()
                status = STATUS_NAMES.get(ag[7], "UNKNOWN")
                if status == "ACTIVE":
                    return f"OK tokenId={ag[6]}"
                if status in ("CANCELLED", "CLOSED"):
                    return f"ERROR: agreement is {status}"
            except Exception as e:
                return f"ERROR reading agreement: {e}"
            time.sleep(_SETTLEMENT_POLL_INTERVAL_S)
        return "PENDING"

    @mcp.tool()
    def verify_credential(token_id: int) -> str:
        """Independently verify a credential on-chain (does NOT call provider)."""
        try:
            nft = get_nft_contract(w3)
            tid = int(token_id)
            owner = Web3.to_checksum_address(nft.functions.ownerOf(tid).call())
            agreement_id, mbps, duration, start_time, endpoint = (
                nft.functions.getTokenMetadata(tid).call())
            seconds_remaining = max(
                0, duration - max(0, int(time.time()) - start_time))
            return json.dumps({
                "ok": True, "owner": owner,
                "ownerIsConsumer": owner == consumer_account.address,
                "agreementId": agreement_id, "mbps": mbps,
                "durationSeconds": duration,
                "secondsRemaining": seconds_remaining, "endpoint": endpoint,
            })
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def discover_provider(provider_url: str) -> str:
        """Fetch agent card; return JSON {name, version, skills: [skill_id, ...]}."""
        try:
            card = await fetch_agent_card(provider_url)
            skills = [s.get("id") for s in card.get("skills", []) if s.get("id")]
            return json.dumps({"name": card.get("name"),
                               "version": card.get("version"), "skills": skills})
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def browse_catalog(provider_url: str) -> str:
        """Discover provider's catalog via A2A. Returns JSON array."""
        try:
            result = await send_provider_action(provider_url,
                                                {"action": "get_catalog"})
            catalog = result.get("catalog")
            if catalog is None:
                return f"ERROR: provider response missing 'catalog' key: {result}"
            return json.dumps(catalog)
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def request_quote(provider_url: str, package_id: str) -> str:
        """Request a quote via A2A and cache it for lock_payment."""
        try:
            provider_addr = await _fetch_provider_address(provider_url)
            result = await send_provider_action(provider_url, {
                "action": "request_quote", "package_id": package_id,
                "consumer_address": consumer_account.address,
            })
            if "error" in result:
                return f"ERROR: {result['error']}"
            quote_cache[str(result["agreementId"])] = {
                **result, "providerAddress": provider_addr,
            }
            return json.dumps(result)
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def present_credential(provider_url: str, token_id: int) -> str:
        """Sign a fresh nonce and send 'activate' over A2A."""
        nonce = str(int(time.time()))
        sig = Account.sign_message(
            encode_defunct(text=nonce),
            private_key=consumer_key).signature.hex()
        try:
            result = await send_provider_action(provider_url, {
                "action": "activate", "token_id": int(token_id),
                "nonce": nonce, "signature": sig,
            })
            return json.dumps(result)
        except Exception as e:
            return f"ERROR: {e}"

    return mcp, quote_cache


# Backwards-compat shim — removed when consumer/app.py and consumer/graph.py
# land on the new factory shape (Tasks 11 and 14).
def _build_default():
    import os as _os
    cfg = Config(
        consumer_private_key=_os.environ.get("CONSUMER_PRIVATE_KEY"),
    )
    if not cfg.consumer_private_key:
        return None, {}
    return build_mcp_server(cfg)


mcp, quote_cache = _build_default()

# Expose the closure-bound tool callables so consumer/graph.py can keep
# importing them by name until Task 11 swaps to the tools-dict shape.
if mcp is not None:
    # FastMCP stores tools under keys like "tool:<name>@" in _local_provider._components.
    # The plan flagged this as fragile — see Task 11 for the migration that drops it.
    _components = mcp._local_provider._components  # type: ignore[attr-defined]
    _tools = {
        v.name: v for k, v in _components.items() if k.startswith("tool:")
    }
    wallet_address      = _tools["wallet_address"].fn
    lock_payment        = _tools["lock_payment"].fn
    await_settlement    = _tools["await_settlement"].fn
    verify_credential   = _tools["verify_credential"].fn
    discover_provider   = _tools["discover_provider"].fn
    browse_catalog      = _tools["browse_catalog"].fn
    request_quote       = _tools["request_quote"].fn
    present_credential  = _tools["present_credential"].fn
