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

Mounted at /mcp inside provider/app.py.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import os
import time

from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from provider.catalog import get_catalog_with_availability, make_quote
from shared.contracts import get_escrow_contract, get_nft_contract

NONCE_WINDOW = 300

_RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
_w3 = Web3(Web3.HTTPProvider(_RPC_URL))

_provider_key = os.environ.get("PROVIDER_PRIVATE_KEY")
_provider_account = Account.from_key(_provider_key) if _provider_key else None

_TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()
_STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}

SDN_MOCK = os.environ.get("SDN_MOCK", "true").lower() == "true"

try:
    from srl_bandwidth.bandwidth import (
        allocate_bandwidth as _srl_allocate,
        revoke_bandwidth as _srl_revoke,
        verify_bandwidth as _srl_verify,
    )
    from srl_bandwidth.models import ServiceRequest as _SrlServiceRequest
    _SRL_AVAILABLE = True
except ImportError:
    _SRL_AVAILABLE = False


mcp = FastMCP("bandwidth-provider")


def _send_provider_tx(func, value: int = 0):
    if _provider_account is None:
        raise RuntimeError("PROVIDER_PRIVATE_KEY not set")
    tx = func.build_transaction({
        "from": _provider_account.address,
        "nonce": _w3.eth.get_transaction_count(_provider_account.address, "pending"),
        "value": value,
    })
    signed = _w3.eth.account.sign_transaction(tx, _provider_key)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    h = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(h, timeout=60)
    if receipt["status"] != 1:
        tx_repr = h.hex() if hasattr(h, "hex") else str(h)
        raise RuntimeError(f"tx reverted: {tx_repr}")
    return h, receipt


def _extract_token_id(receipt) -> int:
    for entry in receipt["logs"]:
        topic0 = entry["topics"][0]
        topic0_hex = topic0.hex() if hasattr(topic0, "hex") else str(topic0)
        if topic0_hex.lower().lstrip("0x") == _TRANSFER_TOPIC.lower().lstrip("0x"):
            topic3 = entry["topics"][3]
            topic3_hex = topic3.hex() if hasattr(topic3, "hex") else str(topic3)
            return int(topic3_hex, 16)
    raise RuntimeError("Transfer event not found in mint receipt")


@mcp.tool()
def get_catalog() -> str:
    """Return available bandwidth packages with pricing and slot availability."""
    return json.dumps(get_catalog_with_availability())


@mcp.tool()
def request_quote(package_id: str, consumer_address: str) -> str:
    """Request a price quote for a bandwidth package. Returns an agreementId-bound quote or error."""
    quote = make_quote(package_id, consumer_address)
    if quote is None:
        return json.dumps({"error": f"Package '{package_id}' not found or no slots available."})
    return json.dumps(quote)


@mcp.tool()
def verify_credential_ownership(token_id: int, signature: str, nonce: str) -> str:
    """
    Verify ownership of a bandwidth credential NFT.

    Checks (in order):
      1. nonce is within ±300 s of now
      2. ECDSA signature recovers to the address that owns tokenId on chain
      3. agreement linked to tokenId is ACTIVE
    """
    try:
        nonce_time = int(nonce)
    except ValueError:
        return json.dumps({"ok": False, "reason": "nonce must be a unix timestamp string"})
    if abs(time.time() - nonce_time) > NONCE_WINDOW:
        return json.dumps({"ok": False, "reason": "nonce expired or too far in future"})

    try:
        signer = Account.recover_message(encode_defunct(text=nonce), signature=signature)
    except Exception as e:
        return json.dumps({"ok": False, "reason": f"invalid signature: {e}"})

    nft = get_nft_contract(_w3)
    try:
        owner = nft.functions.ownerOf(token_id).call()
    except Exception:
        return json.dumps({"ok": False, "reason": f"token {token_id} does not exist"})
    if Web3.to_checksum_address(owner) != Web3.to_checksum_address(signer):
        return json.dumps({"ok": False, "reason": "signer does not own token",
                           "signer": signer, "owner": owner})

    meta = nft.functions.getTokenMetadata(token_id).call()
    agreement_id, mbps, duration, start_time, endpoint = meta
    elapsed = int(time.time()) - int(start_time)
    seconds_remaining = max(0, int(duration) - elapsed)

    escrow = get_escrow_contract(_w3)
    agreement = escrow.functions.getAgreement(int(agreement_id)).call()
    status = _STATUS_NAMES.get(agreement[7], "UNKNOWN")

    return json.dumps({
        "ok": True,
        "signer": signer,
        "owner": owner,
        "agreement_id": int(agreement_id),
        "mbps": int(mbps),
        "duration_seconds": int(duration),
        "endpoint": endpoint,
        "seconds_remaining": seconds_remaining,
        "status": status,
    })


@mcp.tool()
def mint_credential(
    agreement_id: int,
    consumer_address: str,
    pe: str,
    subinterface: str,
    ce: str,
    mbps: int,
    duration_seconds: int,
) -> str:
    """
    Mint a BandwidthNFT credential bound to (agreement_id, mbps, duration).

    Endpoint embeds (pe, subinterface) so the credential is bound to a
    specific resource slot. Returns JSON {tokenId, txHash, endpoint}.
    """
    nft = get_nft_contract(_w3)
    endpoint = f"clab://{pe}/{subinterface}"
    h, receipt = _send_provider_tx(
        nft.functions.mint(
            _provider_account.address,
            int(agreement_id),
            int(mbps),
            int(duration_seconds),
            endpoint,
        )
    )
    token_id = _extract_token_id(receipt)
    tx_hash = h.hex() if hasattr(h, "hex") else str(h)
    return json.dumps({
        "tokenId": token_id,
        "txHash": tx_hash,
        "endpoint": endpoint,
    })


@mcp.tool()
def complete_swap(agreement_id: int, token_id: int) -> str:
    """
    Approve the escrow on the freshly minted NFT, then call escrow.deposit
    to atomically swap NFT→consumer and ETH→provider.

    Returns JSON {status, approveTx, depositTx}.
    """
    nft = get_nft_contract(_w3)
    escrow = get_escrow_contract(_w3)

    h_approve, _ = _send_provider_tx(nft.functions.approve(escrow.address, int(token_id)))
    h_deposit, _ = _send_provider_tx(escrow.functions.deposit(int(agreement_id), int(token_id)))

    return json.dumps({
        "status": "ok",
        "approveTx": h_approve.hex() if hasattr(h_approve, "hex") else str(h_approve),
        "depositTx": h_deposit.hex() if hasattr(h_deposit, "hex") else str(h_deposit),
    })


@mcp.tool()
def allocate_bandwidth(customer_id: str, pe: str, subinterface: str, mbps: float) -> str:
    """
    Push gNMI policer to PE and apply tc tbf on connected CE.

    Honors SDN_MOCK=true (default) — returns a fake-success result without
    touching ContainerLab.
    """
    if SDN_MOCK or not _SRL_AVAILABLE:
        return json.dumps({
            "success": True, "customer_id": customer_id, "pe": pe,
            "subinterface": subinterface, "mbps": mbps,
            "gnmi_pushed": False, "tc_applied": False,
            "message": "mocked",
        })
    req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                             subinterface=subinterface, mbps=mbps)
    return json.dumps(_dc.asdict(_srl_allocate(req)))


@mcp.tool()
def revoke_bandwidth(customer_id: str, pe: str, subinterface: str) -> str:
    """Reverse of allocate_bandwidth."""
    if SDN_MOCK or not _SRL_AVAILABLE:
        return json.dumps({"status": "revoked", "customer_id": customer_id,
                           "pe": pe, "subinterface": subinterface, "mocked": True})
    req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                             subinterface=subinterface, mbps=0.0)
    _srl_revoke(req)
    return json.dumps({"status": "revoked", "customer_id": customer_id,
                       "pe": pe, "subinterface": subinterface})


@mcp.tool()
def verify_bandwidth(src_ce: str, dst_ce: str,
                     expected_mbps: float | None = None,
                     tolerance: float = 0.2) -> str:
    """iperf3 UDP probe from src_ce to dst_ce."""
    if SDN_MOCK or not _SRL_AVAILABLE:
        return json.dumps({
            "passed": True, "measured_mbps": expected_mbps or 0.0,
            "expected_mbps": expected_mbps, "tolerance": tolerance,
            "message": "mocked",
        })
    return json.dumps(_dc.asdict(_srl_verify(src_ce, dst_ce, expected_mbps, tolerance)))
