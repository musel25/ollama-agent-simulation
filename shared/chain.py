"""Web3 helpers shared between consumer and provider agents.

Both agents build, sign, and send transactions the same way, decode the
``status`` field on ``getAgreement(...)`` the same way, and (for the
provider) pull the ``tokenId`` out of a ``Transfer`` log. Centralising
these here keeps the per-agent MCP servers focused on domain logic and
prevents the version-compat shim from drifting between two copies.
"""
from __future__ import annotations

from typing import Any

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract

from shared.config import Config

# Mirrors the BandwidthEscrow.Status enum. Used to render the status slot
# returned by escrow.getAgreement(...) (`ag[7]`) as a readable name.
STATUS_NAMES: dict[int, str] = {
    0: "NONE",
    1: "REQUESTED",
    2: "ACTIVE",
    3: "CLOSED",
    4: "CANCELLED",
}


def send_tx(
    w3: Web3,
    account: LocalAccount,
    private_key: str,
    func: Any,
    value: int = 0,
    timeout: int = 60,
) -> tuple[str, dict]:
    """Build, sign, broadcast, and wait for the receipt of a contract call.

    Returns ``(tx_hash_hex, receipt)``. Raises :class:`RuntimeError` if the
    private key is missing or the transaction reverted.
    """
    if account is None or not private_key:
        raise RuntimeError("private key not configured")

    tx = func.build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address, "pending"),
        "value": value,
    })
    signed = w3.eth.account.sign_transaction(tx, private_key)
    # web3.py 6.x renamed `rawTransaction` → `raw_transaction`; support both.
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    h = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(h, timeout=timeout)
    tx_hex = h.hex() if hasattr(h, "hex") else str(h)
    if receipt["status"] != 1:
        raise RuntimeError(f"tx reverted: {tx_hex}")
    return tx_hex, receipt


def extract_token_id(receipt: dict, nft_contract: Contract) -> int:
    """Return the tokenId minted in this receipt by decoding its Transfer event.

    Uses the contract's own ABI-aware decoder rather than parsing topic
    hashes by hand, so any future change to ERC-721 event encoding flows
    through automatically.
    """
    transfers = nft_contract.events.Transfer().process_receipt(receipt)
    if not transfers:
        raise RuntimeError("Transfer event not found in mint receipt")
    return int(transfers[0]["args"]["tokenId"])


def make_web3(cfg: Config) -> Web3:
    """Build a Web3 HTTP provider client pointing at `cfg.rpc_url`."""
    return Web3(Web3.HTTPProvider(cfg.rpc_url))
