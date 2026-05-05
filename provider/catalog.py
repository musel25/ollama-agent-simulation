"""
Catalog and quote logic for the provider.

State is split:
- Tier metadata (mbps, price) lives in the in-memory CATALOG dict.
- Slot availability (which subinterface, leased or free) lives in
  inventory.txt via SlotPool.
- Quotes (agreementId → quote params) live in pending_quotes (in-memory).
"""
from __future__ import annotations

import secrets
import time
from pathlib import Path

from web3 import Web3

from shared.slot_pool import SlotPool

CATALOG: list[dict] = [
    {"packageId": "small",  "mbps": 2, "durationSeconds": 600, "priceWei": Web3.to_wei(0.01, "ether")},
    {"packageId": "medium", "mbps": 5, "durationSeconds": 600, "priceWei": Web3.to_wei(0.02, "ether")},
    {"packageId": "large",  "mbps": 8, "durationSeconds": 600, "priceWei": Web3.to_wei(0.08, "ether")},
]
CATALOG_BY_ID: dict[str, dict] = {p["packageId"]: p for p in CATALOG}

INVENTORY_FILE = Path(__file__).parent / "inventory.txt"
# Quote validity window in seconds. Must comfortably cover the consumer's
# slowest credible LangGraph latency (LLM tier-pick + lock_payment mining)
# — small local models can blow past 60 s. 5 minutes leaves margin without
# letting a stale quote outlive the slot.
QUOTE_TTL = 300

pending_quotes: dict[int, dict] = {}

slot_pool = SlotPool(INVENTORY_FILE)


def get_catalog_with_availability() -> list[dict]:
    avail_by_tier = {t["tier"]: t["availableSlots"] for t in slot_pool.tiers()}
    return [
        {**pkg, "availableSlots": avail_by_tier.get(pkg["packageId"], 0)}
        for pkg in CATALOG
    ]


def cleanup_quotes() -> None:
    now = time.time()
    expired = [k for k, v in pending_quotes.items() if v["expires"] < now]
    for k in expired:
        del pending_quotes[k]


def make_quote(package_id: str, consumer_address: str) -> dict | None:
    pkg = CATALOG_BY_ID.get(package_id)
    if pkg is None:
        return None
    if slot_pool.available_count(package_id) <= 0:
        return None
    agreement_id = int.from_bytes(secrets.token_bytes(16), "big")
    pending_quotes[agreement_id] = {
        "packageId": package_id,
        "consumerAddress": consumer_address,
        "expires": time.time() + QUOTE_TTL,
        "priceWei": pkg["priceWei"],
        "bandwidthMbps": pkg["mbps"],
        "durationSeconds": pkg["durationSeconds"],
    }
    return {
        "agreementId": agreement_id,
        "priceWei": pkg["priceWei"],
        "bandwidthMbps": pkg["mbps"],
        "durationSeconds": pkg["durationSeconds"],
    }
