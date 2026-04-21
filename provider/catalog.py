import fcntl
import json
import secrets
import time
from pathlib import Path

from web3 import Web3

CATALOG: list[dict] = [
    {"packageId": "small",  "mbps": 50,  "durationSeconds": 600, "priceWei": Web3.to_wei(0.01, "ether")},
    {"packageId": "medium", "mbps": 100, "durationSeconds": 600, "priceWei": Web3.to_wei(0.02, "ether")},
    {"packageId": "large",  "mbps": 500, "durationSeconds": 600, "priceWei": Web3.to_wei(0.08, "ether")},
]
CATALOG_BY_ID: dict[str, dict] = {p["packageId"]: p for p in CATALOG}

INVENTORY_FILE = Path(__file__).parent / "inventory.txt"
QUOTE_TTL = 60

pending_quotes: dict[int, dict] = {}


def _read_inventory_locked(f) -> list[dict]:
    f.seek(0)
    now = time.time()
    rows = []
    for line in f.read().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        row["activeLeases"] = [l for l in row["activeLeases"] if l["expiresAt"] > now]
        rows.append(row)
    return rows


def _write_inventory_locked(f, rows: list[dict]) -> None:
    f.seek(0)
    f.truncate()
    for row in rows:
        f.write(json.dumps(row) + "\n")


def _available_slots(row: dict) -> int:
    now = time.time()
    active = sum(1 for l in row["activeLeases"] if l["expiresAt"] > now)
    return row["totalSlots"] - active


def get_catalog_with_availability() -> list[dict]:
    with open(INVENTORY_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            rows = _read_inventory_locked(f)
            _write_inventory_locked(f, rows)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    row_by_tier = {r["tier"]: r for r in rows}
    result = []
    for pkg in CATALOG:
        row = row_by_tier.get(pkg["packageId"], {})
        available = _available_slots(row) if row else 0
        result.append({**pkg, "availableSlots": available})
    return result


def decrement_inventory(tier: str, agreement_id: int, duration_seconds: int) -> bool:
    with open(INVENTORY_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            rows = _read_inventory_locked(f)
            for row in rows:
                if row["tier"] == tier:
                    if _available_slots(row) <= 0:
                        return False
                    row["activeLeases"].append({
                        "agreementId": agreement_id,
                        "expiresAt": time.time() + duration_seconds,
                    })
                    _write_inventory_locked(f, rows)
                    return True
            return False
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def rewind_inventory(tier: str, agreement_id: int) -> None:
    with open(INVENTORY_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            rows = _read_inventory_locked(f)
            for row in rows:
                if row["tier"] == tier:
                    row["activeLeases"] = [
                        l for l in row["activeLeases"] if l["agreementId"] != agreement_id
                    ]
            _write_inventory_locked(f, rows)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def cleanup_quotes() -> None:
    now = time.time()
    expired = [k for k, v in pending_quotes.items() if v["expires"] < now]
    for k in expired:
        del pending_quotes[k]


def make_quote(package_id: str, consumer_address: str) -> dict | None:
    """Generate and store a quote. Returns quote dict or None if package unavailable."""
    pkg = CATALOG_BY_ID.get(package_id)
    if pkg is None:
        return None
    catalog = get_catalog_with_availability()
    tier_info = next((c for c in catalog if c["packageId"] == package_id), None)
    if not tier_info or tier_info["availableSlots"] <= 0:
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
