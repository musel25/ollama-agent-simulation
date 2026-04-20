import json
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

CATALOG_FILE = "catalog.txt"
AGREEMENTS_FILE = "agreements.json"

app = FastAPI(title="Bandwidth Provider")


class ConfirmRequest(BaseModel):
    tier: str
    agreed_price: float  # ETH


def _load_catalog() -> list[dict]:
    rows = []
    with open(CATALOG_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            name, mbps, duration_min, price_eth, slots = line.split(",")
            rows.append({
                "tier": name,
                "mbps": int(mbps),
                "duration_min": int(duration_min),
                "price_eth": float(price_eth),
                "slots": int(slots),
            })
    return rows


def _save_catalog(rows: list[dict]) -> None:
    with open(CATALOG_FILE, "w") as f:
        for r in rows:
            f.write(f"{r['tier']},{r['mbps']},{r['duration_min']},{r['price_eth']},{r['slots']}\n")


def _load_agreements() -> list[dict]:
    path = Path(AGREEMENTS_FILE)
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save_agreements(agreements: list[dict]) -> None:
    with open(AGREEMENTS_FILE, "w") as f:
        json.dump(agreements, f, indent=2)


@app.get("/catalog")
def get_catalog() -> list[dict]:
    return _load_catalog()


@app.post("/confirm")
def confirm_purchase(req: ConfirmRequest) -> dict:
    rows = _load_catalog()
    target = next((r for r in rows if r["tier"].lower() == req.tier.lower()), None)

    if target is None:
        raise HTTPException(404, f"Tier '{req.tier}' not found.")
    if target["slots"] <= 0:
        raise HTTPException(409, f"No slots available for tier '{req.tier}'.")
    if abs(req.agreed_price - target["price_eth"]) > 1e-9:
        raise HTTPException(402, f"Price mismatch: expected {target['price_eth']} ETH, got {req.agreed_price}.")

    target["slots"] -= 1
    _save_catalog(rows)

    now = time.time()
    token_id = str(uuid.uuid4())
    agreement = {
        "token_id": token_id,
        "tier": target["tier"],
        "mbps": target["mbps"],
        "duration_min": target["duration_min"],
        "price_eth": req.agreed_price,
        "issued_at": now,
        "expires_at": now + target["duration_min"] * 60,
    }
    agreements = _load_agreements()
    agreements.append(agreement)
    _save_agreements(agreements)

    return {
        "token_id": token_id,
        "tier": target["tier"],
        "mbps": target["mbps"],
        "duration_min": target["duration_min"],
    }


@app.get("/service")
def check_service(token: str = Query(...)) -> dict:
    agreements = _load_agreements()
    agreement = next((a for a in agreements if a["token_id"] == token), None)

    if agreement is None:
        raise HTTPException(404, "Token not found.")

    now = time.time()
    if now > agreement["expires_at"]:
        mins_ago = int((now - agreement["expires_at"]) / 60)
        raise HTTPException(410, f"Token expired {mins_ago} min ago.")

    remaining_min = int((agreement["expires_at"] - now) / 60)
    return {
        "status": "active",
        "tier": agreement["tier"],
        "mbps": agreement["mbps"],
        "remaining_min": remaining_min,
    }
