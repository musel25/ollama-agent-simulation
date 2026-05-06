"""
FastMCP server for the bandwidth provider.

Tools:
  - get_catalog                   — list tiers with availability
  - request_quote                 — issue an agreementId quote
  - verify_credential_ownership   — signature/nonce + on-chain ownerOf check
  - mint_credential               — mint an NFT bound to (agreement, mbps, duration)
  - complete_swap                 — approve + escrow.deposit (atomic on-chain swap)
  - allocate_bandwidth            — push gNMI policer + tc on connected CE
  - revoke_bandwidth              — reverse of allocate_bandwidth
  - verify_bandwidth              — iperf3 UDP probe between two CEs
"""
from __future__ import annotations

import dataclasses as _dc
import inspect
import json
import time
from collections import deque
from functools import wraps

from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from provider.catalog import get_catalog_with_availability, make_quote
from shared.chain import STATUS_NAMES, extract_token_id, make_web3, send_tx
from shared.config import Config
from shared.contracts import get_escrow_contract, get_nft_contract

NONCE_WINDOW = 300


def _summarize_args(kwargs: dict) -> dict:
    """Truncate every value to ≤80 chars so log entries stay small."""
    out = {}
    for k, v in kwargs.items():
        s = str(v)
        out[k] = s if len(s) <= 80 else s[:77] + "..."
    return out


def _make_logged(tool_log: deque):
    """Return a decorator that records every invocation into `tool_log`."""
    def _logged(fn):
        tool_name = fn.__name__
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                entry = {"tool": tool_name, "ts": time.time(),
                         "args": _summarize_args(kwargs), "status": "running"}
                tool_log.append(entry)
                try:
                    result = await fn(*args, **kwargs)
                    entry["status"] = "ok"
                    return result
                except Exception:
                    entry["status"] = "error"
                    raise
            return async_wrapper

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            entry = {"tool": tool_name, "ts": time.time(),
                     "args": _summarize_args(kwargs), "status": "running"}
            tool_log.append(entry)
            try:
                result = fn(*args, **kwargs)
                entry["status"] = "ok"
                return result
            except Exception:
                entry["status"] = "error"
                raise
        return sync_wrapper
    return _logged


try:  # optional dependency — only needed when SDN_MOCK=false
    from srl_bandwidth.bandwidth import (
        allocate_bandwidth as _srl_allocate,
        revoke_bandwidth as _srl_revoke,
        verify_bandwidth as _srl_verify,
    )
    from srl_bandwidth.models import ServiceRequest as _SrlServiceRequest
    _SRL_AVAILABLE = True
except ImportError:
    _SRL_AVAILABLE = False


def build_mcp_server(cfg: Config) -> tuple[FastMCP, deque]:
    """Build a fresh provider FastMCP server bound to `cfg`.

    Returns ``(mcp, tool_log)``. The tool_log deque is exposed so the
    FastAPI app can serve `/tool_log`.
    """
    if not cfg.provider_private_key:
        raise RuntimeError("Config.provider_private_key is required")

    mcp = FastMCP("bandwidth-provider")
    tool_log: deque = deque(maxlen=500)
    logged = _make_logged(tool_log)

    w3 = make_web3(cfg)
    provider_account = Account.from_key(cfg.provider_private_key)
    provider_key = cfg.provider_private_key
    sdn_mock = cfg.sdn_mock

    def _provider_send_tx(func, value: int = 0):
        return send_tx(w3, provider_account, provider_key, func, value=value)

    @mcp.tool()
    @logged
    def get_catalog() -> str:
        """Return available bandwidth packages with pricing and slot availability."""
        return json.dumps(get_catalog_with_availability())

    @mcp.tool()
    @logged
    def request_quote(package_id: str, consumer_address: str) -> str:
        """Issue an agreementId-bound price quote, or ``{"error": ...}``."""
        quote = make_quote(package_id, consumer_address)
        if quote is None:
            return json.dumps({"error":
                               f"Package '{package_id}' not found or no slots available."})
        return json.dumps(quote)

    @mcp.tool()
    @logged
    def verify_credential_ownership(token_id: int, signature: str, nonce: str) -> str:
        """Verify nonce freshness, signature recovery, and on-chain agreement status."""
        try:
            nonce_time = int(nonce)
        except ValueError:
            return json.dumps({"ok": False,
                               "reason": "nonce must be a unix timestamp string"})
        if abs(time.time() - nonce_time) > NONCE_WINDOW:
            return json.dumps({"ok": False,
                               "reason": "nonce expired or too far in future"})
        try:
            signer = Account.recover_message(encode_defunct(text=nonce),
                                             signature=signature)
        except Exception as e:
            return json.dumps({"ok": False, "reason": f"invalid signature: {e}"})

        nft = get_nft_contract(w3)
        try:
            owner = nft.functions.ownerOf(token_id).call()
        except Exception:
            return json.dumps({"ok": False,
                               "reason": f"token {token_id} does not exist"})
        if Web3.to_checksum_address(owner) != Web3.to_checksum_address(signer):
            return json.dumps({"ok": False, "reason": "signer does not own token",
                               "signer": signer, "owner": owner})

        meta = nft.functions.getTokenMetadata(token_id).call()
        agreement_id, mbps, duration, start_time, endpoint = meta
        elapsed = int(time.time()) - int(start_time)
        seconds_remaining = max(0, int(duration) - elapsed)

        escrow = get_escrow_contract(w3)
        agreement = escrow.functions.getAgreement(int(agreement_id)).call()
        status = STATUS_NAMES.get(agreement[7], "UNKNOWN")

        return json.dumps({
            "ok": True, "signer": signer, "owner": owner,
            "agreement_id": int(agreement_id), "mbps": int(mbps),
            "duration_seconds": int(duration), "endpoint": endpoint,
            "seconds_remaining": seconds_remaining, "status": status,
        })

    @mcp.tool()
    @logged
    def mint_credential(agreement_id: int, consumer_address: str, pe: str,
                        subinterface: str, ce: str, mbps: int,
                        duration_seconds: int) -> str:
        """Mint a BandwidthNFT bound to (agreement, mbps, duration). Returns JSON."""
        nft = get_nft_contract(w3)
        endpoint = f"clab://{pe}/{subinterface}"
        tx_hex, receipt = _provider_send_tx(
            nft.functions.mint(provider_account.address, int(agreement_id),
                               int(mbps), int(duration_seconds), endpoint))
        return json.dumps({
            "tokenId": extract_token_id(receipt, nft),
            "txHash": tx_hex, "endpoint": endpoint,
        })

    @mcp.tool()
    @logged
    def complete_swap(agreement_id: int, token_id: int) -> str:
        """Approve escrow on the NFT, then call escrow.deposit (atomic swap)."""
        nft = get_nft_contract(w3)
        escrow = get_escrow_contract(w3)
        approve_tx, _ = _provider_send_tx(
            nft.functions.approve(escrow.address, int(token_id)))
        deposit_tx, _ = _provider_send_tx(
            escrow.functions.deposit(int(agreement_id), int(token_id)))
        return json.dumps({"status": "ok", "approveTx": approve_tx,
                           "depositTx": deposit_tx})

    @mcp.tool()
    @logged
    def allocate_bandwidth(customer_id: str, pe: str, subinterface: str,
                           mbps: float) -> str:
        """Push gNMI policer + tc tbf for a slot. Mocked under SDN_MOCK."""
        if sdn_mock or not _SRL_AVAILABLE:
            return json.dumps({
                "success": True, "customer_id": customer_id, "pe": pe,
                "subinterface": subinterface, "mbps": mbps,
                "gnmi_pushed": False, "tc_applied": False, "message": "mocked",
            })
        req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                                 subinterface=subinterface, mbps=mbps)
        return json.dumps(_dc.asdict(_srl_allocate(req)))

    @mcp.tool()
    @logged
    def revoke_bandwidth(customer_id: str, pe: str, subinterface: str) -> str:
        """Reverse of allocate_bandwidth. Mocked under SDN_MOCK."""
        if sdn_mock or not _SRL_AVAILABLE:
            return json.dumps({"status": "revoked", "customer_id": customer_id,
                               "pe": pe, "subinterface": subinterface,
                               "mocked": True})
        req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                                 subinterface=subinterface, mbps=0.0)
        _srl_revoke(req)
        return json.dumps({"status": "revoked", "customer_id": customer_id,
                           "pe": pe, "subinterface": subinterface})

    @mcp.tool()
    @logged
    def verify_bandwidth(src_ce: str, dst_ce: str,
                         expected_mbps: float | None = None,
                         tolerance: float = 0.2) -> str:
        """iperf3 UDP probe from src_ce to dst_ce. Mocked under SDN_MOCK."""
        if sdn_mock or not _SRL_AVAILABLE:
            return json.dumps({"passed": True,
                               "measured_mbps": expected_mbps or 0.0,
                               "expected_mbps": expected_mbps,
                               "tolerance": tolerance, "message": "mocked"})
        return json.dumps(_dc.asdict(
            _srl_verify(src_ce, dst_ce, expected_mbps, tolerance)))

    return mcp, tool_log


# Backwards-compat shim — removed in Task 15.
# Allows provider/app.py and provider/expiry.py to keep importing `mcp` and
# `tool_call_log` until the lifespan refactor lands.
def _build_default():
    cfg = Config(
        provider_private_key=__import__("os").environ.get("PROVIDER_PRIVATE_KEY"),
        sdn_mock=__import__("os").environ.get("SDN_MOCK", "true").lower() == "true",
    )
    if cfg.provider_private_key:
        return build_mcp_server(cfg)
    return None, None


mcp, tool_call_log = _build_default()
