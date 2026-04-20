"""
Provider agent FastAPI service — port 8002.
Serves catalog and quote endpoints; runs an AgreementRequested event-listener
background task that mints an NFT and calls deposit() to complete the swap.
"""
import asyncio
import fcntl
import json
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from eth_account import Account
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3

from shared.contracts import get_escrow_contract, get_nft_contract

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("provider")

# ── Ethereum setup ─────────────────────────────────────────────────────────────
RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
PROVIDER_PRIVATE_KEY = os.environ["PROVIDER_PRIVATE_KEY"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
provider_account = Account.from_key(PROVIDER_PRIVATE_KEY)
PROVIDER_ADDRESS = provider_account.address

# ── Catalog (hardcoded tiers, inventory tracks slots separately) ───────────────
CATALOG = [
    {"packageId": "small",  "mbps": 50,  "durationSeconds": 600, "priceWei": Web3.to_wei(0.01, "ether")},
    {"packageId": "medium", "mbps": 100, "durationSeconds": 600, "priceWei": Web3.to_wei(0.02, "ether")},
    {"packageId": "large",  "mbps": 500, "durationSeconds": 600, "priceWei": Web3.to_wei(0.08, "ether")},
]
CATALOG_BY_ID = {p["packageId"]: p for p in CATALOG}

# ── Inventory (per-tier JSON-lines with lease expiry) ─────────────────────────
INVENTORY_FILE = Path(__file__).parent / "inventory.txt"


def _read_inventory_locked(f) -> list[dict]:
    f.seek(0)
    rows = []
    now = time.time()
    for line in f.read().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        # Prune expired leases on read
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
            _write_inventory_locked(f, rows)  # persist pruned leases
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
    """Reserve one slot for the given tier. Returns True if successful."""
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
    """Remove a lease from inventory (called on mint/deposit failure)."""
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


# ── Pending quotes ─────────────────────────────────────────────────────────────
pending_quotes: dict[int, dict] = {}
QUOTE_TTL = 60  # seconds


def _cleanup_quotes() -> None:
    now = time.time()
    expired = [k for k, v in pending_quotes.items() if v["expires"] < now]
    for k in expired:
        del pending_quotes[k]


# ── Chain helpers ──────────────────────────────────────────────────────────────
def _send_tx(func, value: int = 0) -> str:
    tx = func.build_transaction({
        "from": PROVIDER_ADDRESS,
        "nonce": w3.eth.get_transaction_count(PROVIDER_ADDRESS, "pending"),
        "value": value,
    })
    signed = w3.eth.account.sign_transaction(tx, PROVIDER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex(), receipt


def _extract_token_id(receipt) -> int:
    transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)").hex()
    for entry in receipt["logs"]:
        if entry["topics"][0].hex() == transfer_topic:
            return int(entry["topics"][3].hex(), 16)
    raise RuntimeError("Transfer event not found in mint receipt")


# ── Event listener ─────────────────────────────────────────────────────────────
async def _event_listener() -> None:
    nft = get_nft_contract(w3)
    escrow = get_escrow_contract(w3)
    log.info("Event listener started, watching AgreementRequested...")
    last_block = w3.eth.block_number

    while True:
        await asyncio.sleep(2)
        try:
            current = w3.eth.block_number
            if current <= last_block:
                continue
            events = escrow.events.AgreementRequested.get_logs(
                from_block=last_block + 1, to_block=current
            )
            last_block = current
            for evt in events:
                args = evt["args"]
                asyncio.create_task(
                    _handle_agreement(nft, escrow, args["agreementId"], args)
                )
        except Exception as e:
            log.error(f"Event listener error: {e}")


async def _handle_agreement(nft, escrow, agreement_id: int, args: dict) -> None:
    _cleanup_quotes()
    quote = pending_quotes.get(agreement_id)

    if not quote or time.time() > quote["expires"]:
        log.warning(f"No valid quote for agreementId={agreement_id}, skipping.")
        return

    pkg = CATALOG_BY_ID.get(quote["packageId"])
    if not pkg:
        log.error(f"Unknown packageId in quote for agreementId={agreement_id}")
        return

    # Verify on-chain params match quote
    ag = escrow.functions.getAgreement(agreement_id).call()
    # tuple: consumer, provider, bandwidthMbps, durationSeconds, priceWei, deadline, tokenId, status
    if ag[2] != pkg["mbps"] or ag[3] != pkg["durationSeconds"] or ag[4] != pkg["priceWei"]:
        log.error(f"Param mismatch for agreementId={agreement_id}")
        return

    # Step 1: Decrement inventory (reserve slot)
    if not decrement_inventory(pkg["packageId"], agreement_id, pkg["durationSeconds"]):
        log.error(f"No slots available for tier={pkg['packageId']}, agreementId={agreement_id}")
        return

    token_id = None
    try:
        # Step 2: Mint NFT to provider address
        log.info(f"Minting NFT for agreementId={agreement_id}...")
        tx_mint, receipt_mint = _send_tx(
            nft.functions.mint(
                PROVIDER_ADDRESS,
                agreement_id,
                pkg["mbps"],
                pkg["durationSeconds"],
                "grpc://provider:8003",
            )
        )
        token_id = _extract_token_id(receipt_mint)
        log.info(f"Minted tokenId={token_id} tx={tx_mint}")

        # Step 3: Approve escrow to transfer the NFT
        escrow_address = escrow.address
        tx_approve, _ = _send_tx(nft.functions.approve(escrow_address, token_id))
        log.info(f"Approved escrow tx={tx_approve}")

        # Step 4: Call deposit — triggers atomic swap
        tx_deposit, _ = _send_tx(escrow.functions.deposit(agreement_id, token_id))
        log.info(f"Deposit complete agreementId={agreement_id} tx={tx_deposit}")

        del pending_quotes[agreement_id]

    except Exception as e:
        log.error(f"Error in deposit flow agreementId={agreement_id}: {e}")
        if token_id is None:
            # Mint failed — safe to rewind inventory
            rewind_inventory(pkg["packageId"], agreement_id)
            log.info(f"Inventory rewound for tier={pkg['packageId']}")
        else:
            log.error(
                f"NFT tokenId={token_id} is orphaned (minted but swap failed). Manual cleanup needed."
            )


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_event_listener())
    yield


app = FastAPI(title="Bandwidth Provider", lifespan=lifespan)


class QuoteRequest(BaseModel):
    packageId: str
    consumerAddress: str


@app.get("/catalog")
def get_catalog() -> list[dict]:
    return get_catalog_with_availability()


@app.post("/quote")
def request_quote(req: QuoteRequest) -> dict:
    pkg = CATALOG_BY_ID.get(req.packageId)
    if pkg is None:
        raise HTTPException(404, f"Package '{req.packageId}' not found.")

    catalog = get_catalog_with_availability()
    tier_info = next((c for c in catalog if c["packageId"] == req.packageId), None)
    if not tier_info or tier_info["availableSlots"] <= 0:
        raise HTTPException(409, f"No slots available for '{req.packageId}'.")

    agreement_id = int.from_bytes(secrets.token_bytes(16), "big")
    pending_quotes[agreement_id] = {
        "packageId": req.packageId,
        "consumerAddress": req.consumerAddress,
        "expires": time.time() + QUOTE_TTL,
    }

    return {
        "agreementId": agreement_id,
        "priceWei": pkg["priceWei"],
        "bandwidthMbps": pkg["mbps"],
        "durationSeconds": pkg["durationSeconds"],
    }


@app.get("/inventory")
def get_inventory() -> list[dict]:
    return get_catalog_with_availability()


@app.get("/address")
def provider_address() -> dict:
    return {"address": PROVIDER_ADDRESS}


if __name__ == "__main__":
    uvicorn.run("provider.app:app", host="0.0.0.0", port=8002, reload=False)
