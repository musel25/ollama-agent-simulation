"""
Provider agent FastAPI service — port 8002.
Serves catalog and quote endpoints; runs an AgreementRequested event-listener
background task that mints an NFT and calls deposit() to complete the swap.
"""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from eth_account import Account
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3

from provider.catalog import (
    CATALOG_BY_ID,
    cleanup_quotes,
    decrement_inventory,
    get_catalog_with_availability,
    make_quote,
    pending_quotes,
    rewind_inventory,
)
from provider.mcp_server import mcp
from shared.contracts import get_escrow_contract, get_nft_contract

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("provider")

RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
PROVIDER_PRIVATE_KEY = os.environ["PROVIDER_PRIVATE_KEY"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
provider_account = Account.from_key(PROVIDER_PRIVATE_KEY)
PROVIDER_ADDRESS = provider_account.address

AGENT_CARD = {
    "name": "Bandwidth Provider Agent",
    "description": "Sells bandwidth packages via atomic smart contract escrow. Issues NFT entitlements on payment.",
    "version": "1.0.0",
    "protocols": ["mcp"],
    "mcp_endpoint": "/mcp",
    "skills": [
        {
            "id": "get_catalog",
            "name": "Get Catalog",
            "description": "Returns available bandwidth tiers with pricing and slot availability.",
        },
        {
            "id": "request_quote",
            "name": "Request Quote",
            "description": "Issues a quote with agreementId for on-chain ETH escrow settlement.",
        },
    ],
}


def _send_tx(func, value: int = 0):
    tx = func.build_transaction({
        "from": PROVIDER_ADDRESS,
        "nonce": w3.eth.get_transaction_count(PROVIDER_ADDRESS, "pending"),
        "value": value,
    })
    signed = w3.eth.account.sign_transaction(tx, PROVIDER_PRIVATE_KEY)
    raw_tx = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
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
                fromBlock=last_block + 1, toBlock=current
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
    cleanup_quotes()
    quote = pending_quotes.get(agreement_id)

    if not quote or time.time() > quote["expires"]:
        log.warning(f"No valid quote for agreementId={agreement_id}, skipping.")
        return

    pkg = CATALOG_BY_ID.get(quote["packageId"])
    if not pkg:
        log.error(f"Unknown packageId in quote for agreementId={agreement_id}")
        return

    ag = escrow.functions.getAgreement(agreement_id).call()
    if ag[2] != pkg["mbps"] or ag[3] != pkg["durationSeconds"] or ag[4] != pkg["priceWei"]:
        log.error(f"Param mismatch for agreementId={agreement_id}")
        return

    if not decrement_inventory(pkg["packageId"], agreement_id, pkg["durationSeconds"]):
        log.error(f"No slots available for tier={pkg['packageId']}, agreementId={agreement_id}")
        return

    token_id = None
    try:
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

        escrow_address = escrow.address
        tx_approve, _ = _send_tx(nft.functions.approve(escrow_address, token_id))
        log.info(f"Approved escrow tx={tx_approve}")

        tx_deposit, _ = _send_tx(escrow.functions.deposit(agreement_id, token_id))
        log.info(f"Deposit complete agreementId={agreement_id} tx={tx_deposit}")

        del pending_quotes[agreement_id]

    except Exception as e:
        log.error(f"Error in deposit flow agreementId={agreement_id}: {e}")
        if token_id is None:
            rewind_inventory(pkg["packageId"], agreement_id)
            log.info(f"Inventory rewound for tier={pkg['packageId']}")
        else:
            log.error(f"NFT tokenId={token_id} is orphaned (minted but swap failed). Manual cleanup needed.")


_mcp_http_app = mcp.http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with _mcp_http_app.lifespan(app):
        asyncio.create_task(_event_listener())
        yield


app = FastAPI(title="Bandwidth Provider", lifespan=lifespan)


class QuoteRequest(BaseModel):
    packageId: str
    consumerAddress: str


@app.get("/.well-known/agent.json")
def agent_card() -> dict:
    return AGENT_CARD


@app.get("/catalog")
def get_catalog() -> list[dict]:
    return get_catalog_with_availability()


@app.post("/quote")
def request_quote(req: QuoteRequest) -> dict:
    quote = make_quote(req.packageId, req.consumerAddress)
    if quote is None:
        raise HTTPException(409, f"No slots available for '{req.packageId}' or package not found.")
    return quote


@app.get("/inventory")
def get_inventory() -> list[dict]:
    return get_catalog_with_availability()


@app.get("/address")
def provider_address() -> dict:
    return {"address": PROVIDER_ADDRESS}


# MCP mounted last so REST routes above are checked first by Starlette's router.
# http_app() registers its route at /mcp internally, so the MCP endpoint is at /mcp.
app.mount("/", _mcp_http_app)


if __name__ == "__main__":
    uvicorn.run("provider.app:app", host="0.0.0.0", port=8002, reload=False)
