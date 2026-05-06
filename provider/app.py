"""
Provider agent FastAPI service — port 8002.

Serves catalog, quote and address endpoints; mounts the FastMCP server at /mcp;
runs an AgreementRequested event-listener that drives mint+swap through the
provider's own MCP via in-memory FastMCP Client.
"""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from eth_account import Account
from fastapi import FastAPI, HTTPException
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel
from web3 import Web3

from provider.agent_card import build_provider_agent_card
from provider.agent_executor import BandwidthProviderExecutor
from provider.expiry import expiry_sweep_loop
from provider.catalog import (
    CATALOG_BY_ID,
    cleanup_quotes,
    get_catalog_with_availability,
    make_quote,
    pending_quotes,
    slot_pool,
)
from provider.mcp_server import mcp, tool_call_log
from shared.config import Config
from shared.contracts import get_escrow_contract, get_nft_contract

# CE peer pairs across pe1 ↔ pe2 (defined by the clab topology in
# srl-gnmi-bandwidth-poc/topology). Used by /probe to pick the iperf3 peer.
CE_PEER = {"ce1": "ce2", "ce2": "ce1", "ce3": "ce4", "ce4": "ce3"}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("provider")

RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
PROVIDER_PRIVATE_KEY = os.environ["PROVIDER_PRIVATE_KEY"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
provider_account = Account.from_key(PROVIDER_PRIVATE_KEY)
PROVIDER_ADDRESS = provider_account.address

_provider_agent_card = build_provider_agent_card(Config.from_env())
_AGENT_CARD_JSON = MessageToDict(_provider_agent_card, preserving_proto_field_name=True)


_handler_tasks: set[asyncio.Task] = set()


async def _event_listener() -> None:
    escrow = get_escrow_contract(w3)
    last_block = w3.eth.block_number
    log.info("Event listener started, watching AgreementRequested at %s from block %d",
             escrow.address, last_block)

    while True:
        await asyncio.sleep(2)
        try:
            current = w3.eth.block_number
            if current <= last_block:
                continue
            events = escrow.events.AgreementRequested.get_logs(
                fromBlock=last_block + 1, toBlock=current
            )
            if events:
                log.info("Saw %d AgreementRequested event(s) in blocks %d..%d",
                         len(events), last_block + 1, current)
            last_block = current
            for evt in events:
                args = evt["args"]
                t = asyncio.create_task(
                    _handle_agreement(escrow, args["agreementId"], args)
                )
                _handler_tasks.add(t)
                t.add_done_callback(_handler_tasks.discard)
        except Exception as e:
            log.exception("Event listener error: %s", e)


async def _handle_agreement(escrow, agreement_id: int, args: dict) -> None:
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

    slot = slot_pool.reserve(pkg["packageId"], agreement_id, pkg["durationSeconds"])
    if slot is None:
        log.error(f"No slots available for tier={pkg['packageId']}, agreementId={agreement_id}")
        return

    try:
        async with MCPClient(mcp) as client:
            mint_result = await client.call_tool(
                "mint_credential",
                {
                    "agreement_id": agreement_id,
                    "consumer_address": args["consumer"],
                    "pe": slot.pe,
                    "subinterface": slot.subinterface,
                    "ce": slot.ce,
                    "mbps": pkg["mbps"],
                    "duration_seconds": pkg["durationSeconds"],
                },
            )
            mint_data = json.loads(mint_result.content[0].text)
            token_id = int(mint_data["tokenId"])
            log.info(f"Minted tokenId={token_id} on slot {slot} for agreementId={agreement_id}")

            await client.call_tool(
                "complete_swap",
                {"agreement_id": agreement_id, "token_id": token_id},
            )
            log.info(f"Swap complete agreementId={agreement_id} tokenId={token_id}")

        del pending_quotes[agreement_id]

    except Exception as e:
        log.error(f"Error in mint/swap flow agreementId={agreement_id}: {e}")
        slot_pool.release(agreement_id)


_mcp_http_app = mcp.http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with _mcp_http_app.lifespan(app):
        listener_task = asyncio.create_task(_event_listener())
        expiry_task = asyncio.create_task(expiry_sweep_loop(period_seconds=30))
        try:
            yield
        finally:
            listener_task.cancel()
            expiry_task.cancel()


app = FastAPI(title="Bandwidth Provider", lifespan=lifespan)


class QuoteRequest(BaseModel):
    packageId: str
    consumerAddress: str


@app.get("/.well-known/agent-card.json")
def agent_card_canonical() -> dict:
    return _AGENT_CARD_JSON


@app.get("/.well-known/agent.json")
def agent_card_legacy() -> dict:
    return _AGENT_CARD_JSON


# /catalog and /quote are debug-only mirrors of the A2A skills. Inter-agent
# traffic must go over A2A so the agent card / skill schema stays the contract.
@app.get("/_debug/catalog")
def get_catalog() -> list[dict]:
    return get_catalog_with_availability()


@app.post("/_debug/quote")
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


class ProbeRequest(BaseModel):
    tokenId: int


@app.post("/probe")
async def probe(req: ProbeRequest) -> dict:
    nft = get_nft_contract(w3)
    try:
        agreement_id, mbps, _duration, _start, _endpoint = (
            nft.functions.getTokenMetadata(int(req.tokenId)).call()
        )
    except Exception:
        raise HTTPException(404, f"token {req.tokenId} does not exist")

    slot = slot_pool.lookup(int(agreement_id))
    if slot is None:
        raise HTTPException(409, f"no active slot bound to agreement {agreement_id}")

    dst_ce = CE_PEER.get(slot.ce)
    if dst_ce is None:
        raise HTTPException(500, f"no peer mapping for {slot.ce}")

    async with MCPClient(mcp) as client:
        result = await client.call_tool(
            "verify_bandwidth",
            {"src_ce": slot.ce, "dst_ce": dst_ce, "expected_mbps": float(mbps)},
        )
        verify = json.loads(result.content[0].text)

    return {
        "timestamp": time.time(),
        "src_ce": slot.ce,
        "dst_ce": dst_ce,
        "expected_mbps": float(mbps),
        "measured_mbps": float(verify.get("measured_mbps", 0.0)),
        "passed": bool(verify.get("passed", False)),
        "message": verify.get("message", ""),
    }


@app.get("/tool_log")
def get_tool_log(since_ts: float | None = None) -> list[dict]:
    entries = list(tool_call_log)
    if since_ts is not None:
        entries = [e for e in entries if e["ts"] > since_ts]
    return entries


_a2a_handler = DefaultRequestHandler(
    agent_executor=BandwidthProviderExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=_provider_agent_card,
)
for route in create_agent_card_routes(_provider_agent_card):
    app.router.routes.append(route)
for route in create_jsonrpc_routes(_a2a_handler, "/a2a"):
    app.router.routes.append(route)

# MCP mounted last so all preceding routes are matched first by Starlette's router.
app.mount("/", _mcp_http_app)


if __name__ == "__main__":
    uvicorn.run("provider.app:app", host="0.0.0.0", port=8002, reload=False)
