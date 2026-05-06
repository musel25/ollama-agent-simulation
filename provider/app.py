"""Provider agent FastAPI service — port 8002."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI, HTTPException, Request
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel

from provider import event_listener
from provider.agent_card import build_provider_agent_card
from provider.agent_executor import BandwidthProviderExecutor
from provider.catalog import get_catalog_with_availability, slot_pool
from provider.expiry import expiry_sweep_loop
from provider.mcp_server import build_mcp_server
from shared.chain import make_web3
from shared.config import Config
from shared.contracts import get_nft_contract

# CE peer pairs — defined by the clab topology.
CE_PEER = {"ce1": "ce2", "ce2": "ce1", "ce3": "ce4", "ce4": "ce3"}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("provider")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Config.from_env()
    mcp, tool_log = build_mcp_server(cfg)
    w3 = make_web3(cfg)
    card = build_provider_agent_card(cfg)
    app.state.cfg = cfg
    app.state.mcp = mcp
    app.state.tool_log = tool_log
    app.state.w3 = w3
    app.state.agent_card_json = MessageToDict(card,
                                              preserving_proto_field_name=True)

    a2a_handler = DefaultRequestHandler(
        agent_executor=BandwidthProviderExecutor(mcp),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    for route in create_agent_card_routes(card):
        app.router.routes.append(route)
    for route in create_jsonrpc_routes(a2a_handler, "/a2a"):
        app.router.routes.append(route)

    mcp_http = mcp.http_app()
    app.mount("/", mcp_http)

    async with mcp_http.lifespan(app):
        listener_task = asyncio.create_task(event_listener.run(w3, mcp))
        expiry_task = asyncio.create_task(
            expiry_sweep_loop(mcp, period_seconds=30))
        try:
            yield
        finally:
            listener_task.cancel()
            expiry_task.cancel()


app = FastAPI(title="Bandwidth Provider", lifespan=lifespan)


class QuoteRequest(BaseModel):
    packageId: str
    consumerAddress: str


@app.get("/_debug/catalog")
def debug_catalog() -> list[dict]:
    return get_catalog_with_availability()


@app.get("/inventory")
def get_inventory() -> list[dict]:
    return get_catalog_with_availability()


@app.get("/address")
def provider_address(request: Request) -> dict:
    cfg: Config = request.app.state.cfg
    from eth_account import Account
    return {"address": Account.from_key(cfg.provider_private_key).address}


class ProbeRequest(BaseModel):
    tokenId: int


@app.post("/probe")
async def probe(req: ProbeRequest, request: Request) -> dict:
    w3 = request.app.state.w3
    nft = get_nft_contract(w3)
    try:
        agreement_id, mbps, *_ = nft.functions.getTokenMetadata(
            int(req.tokenId)).call()
    except Exception:
        raise HTTPException(404, f"token {req.tokenId} does not exist")

    slot = slot_pool.lookup(int(agreement_id))
    if slot is None:
        raise HTTPException(409, f"no active slot for agreement {agreement_id}")
    dst_ce = CE_PEER.get(slot.ce)
    if dst_ce is None:
        raise HTTPException(500, f"no peer mapping for {slot.ce}")
    async with MCPClient(request.app.state.mcp) as client:
        result = await client.call_tool("verify_bandwidth", {
            "src_ce": slot.ce, "dst_ce": dst_ce,
            "expected_mbps": float(mbps)})
        verify = json.loads(result.content[0].text)
    return {
        "timestamp": time.time(), "src_ce": slot.ce, "dst_ce": dst_ce,
        "expected_mbps": float(mbps),
        "measured_mbps": float(verify.get("measured_mbps", 0.0)),
        "passed": bool(verify.get("passed", False)),
        "message": verify.get("message", ""),
    }


@app.get("/tool_log")
def get_tool_log(request: Request, since_ts: float | None = None) -> list[dict]:
    entries = list(request.app.state.tool_log)
    if since_ts is not None:
        entries = [e for e in entries if e["ts"] > since_ts]
    return entries


if __name__ == "__main__":
    uvicorn.run("provider.app:app", host="0.0.0.0", port=8002, reload=False)
