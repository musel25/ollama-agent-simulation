"""Consumer agent FastAPI service — port 8001.

Builds Config + MCP server + LangGraph in `lifespan`. Endpoints read
state from `app.state`. Cross-agent calls go through the consumer MCP
tools, which wrap A2A calls to the provider.
"""
from __future__ import annotations

import json
import traceback
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

from consumer.agent_card import build_consumer_agent_card
from consumer.graph import build_consumer_tools, build_graph
from consumer.mcp_server import build_mcp_server
from shared.chain import make_web3
from shared.config import Config
from shared.contracts import get_escrow_contract, get_nft_contract


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Config.from_env()
    mcp, _quote_cache = build_mcp_server(cfg)
    tools = build_consumer_tools(cfg)
    graph = build_graph(cfg, tools)
    card = build_consumer_agent_card(cfg)
    app.state.cfg = cfg
    app.state.mcp = mcp
    app.state.graph = graph
    app.state.agent_card_json = MessageToDict(card,
                                              preserving_proto_field_name=True)
    app.state.w3 = make_web3(cfg)
    app.state.inter_agent_log = []
    yield


app = FastAPI(title="Consumer Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    model: str | None = None


class ChatResponse(BaseModel):
    response: str
    log: list[dict]
    thinking: list[str] = Field(default_factory=list)


def _seen_keys(state) -> set:
    return getattr(state, "_seen_log_keys", set())


def _append_log(state, sender: str, message: str) -> None:
    keys = _seen_keys(state)
    key = (sender, message)
    if key in keys:
        return
    keys.add(key)
    state._seen_log_keys = keys
    state.inter_agent_log.append({"from": sender, "message": message})


@app.get("/.well-known/agent-card.json")
def agent_card_canonical(request: Request) -> dict:
    return request.app.state.agent_card_json


@app.get("/.well-known/agent.json")
def agent_card_legacy(request: Request) -> dict:
    return request.app.state.agent_card_json


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    cfg: Config = request.app.state.cfg
    request.app.state.inter_agent_log.clear()
    request.app.state._seen_log_keys = set()
    initial = {
        "user_message": req.message,
        "provider_url": cfg.provider_a2a_urls[0],
        "provider_urls": list(cfg.provider_a2a_urls),
        "model": req.model or cfg.ollama_model,
        "log": [], "thinking": [],
    }
    try:
        final = await request.app.state.graph.ainvoke(initial)
    except Exception as e:
        traceback.print_exc()
        return ChatResponse(response=f"INTERNAL ERROR: {e}", log=[], thinking=[])
    for entry in final.get("log", []):
        _append_log(request.app.state, entry["from"], entry["message"])
    return ChatResponse(
        response=final.get("final_response", "(no response)"),
        log=list(request.app.state.inter_agent_log),
        thinking=final.get("thinking", []),
    )


@app.get("/log")
def get_log(request: Request) -> list[dict]:
    return list(request.app.state.inter_agent_log)


@app.delete("/log")
def clear_log(request: Request) -> dict:
    request.app.state.inter_agent_log.clear()
    request.app.state._seen_log_keys = set()
    return {"cleared": True}


@app.get("/catalog_proxy")
async def catalog_proxy(request: Request) -> list[dict]:
    cfg: Config = request.app.state.cfg
    async with MCPClient(request.app.state.mcp) as c:
        result = await c.call_tool("browse_catalog",
                                   {"provider_url": cfg.provider_a2a_urls[0]})
        text = result.content[0].text if result.content else ""
    if text.startswith("ERROR"):
        raise HTTPException(502, text)
    return json.loads(text)


@app.get("/address")
async def consumer_address_endpoint(request: Request) -> dict:
    async with MCPClient(request.app.state.mcp) as c:
        result = await c.call_tool("wallet_address", {})
    return {"address": result.content[0].text}


@app.get("/check_token")
async def check_token(tokenId: int, request: Request) -> dict:
    async with MCPClient(request.app.state.mcp) as c:
        result = await c.call_tool("verify_credential", {"token_id": int(tokenId)})
        text = result.content[0].text if result.content else ""
    if text.startswith("ERROR"):
        raise HTTPException(404, text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(502, f"unparseable verify_credential response: {e}")
    seconds_remaining = int(data.get("secondsRemaining", 0))
    return {
        "owner": data["owner"],
        "status": "active" if seconds_remaining > 0 else "expired",
        "seconds_remaining": seconds_remaining,
        "bandwidth_mbps": float(data["mbps"]),
        "endpoint": data["endpoint"],
        "agreementId": str(data.get("agreementId", "")),
    }


class ProbeProxyRequest(BaseModel):
    tokenId: int


@app.post("/probe_proxy")
async def probe_proxy(req: ProbeProxyRequest, request: Request) -> dict:
    cfg: Config = request.app.state.cfg
    if not cfg.provider_a2a_urls:
        raise HTTPException(500, "no provider_a2a_urls configured")
    target = f"{cfg.provider_a2a_urls[0]}/probe"
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            r = await http.post(target, json={"tokenId": int(req.tokenId)})
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code,
                            f"provider /probe failed: {e.response.text}")
    except Exception as e:
        raise HTTPException(502, f"probe forward failed: {e}")


@app.get("/chain_events")
def chain_events(since_block: int = 0, request: Request = None) -> list[dict]:
    """Return escrow + NFT events emitted since `since_block`."""
    w3 = request.app.state.w3
    escrow = get_escrow_contract(w3)
    nft = get_nft_contract(w3)
    to_block = w3.eth.block_number

    def _serialize(args) -> dict:
        out = {}
        for k, v in dict(args).items():
            if isinstance(v, (bytes, bytearray)):
                out[k] = "0x" + v.hex()
            elif hasattr(v, "hex") and not isinstance(v, (int, str)):
                out[k] = v.hex()
            else:
                out[k] = (str(v) if not isinstance(v, (int, str, bool, type(None)))
                          else v)
        return out

    def _gather_named(contract, name: str) -> list[dict]:
        evt = getattr(contract.events, name, None)
        if evt is None:
            return []
        try:
            logs = evt.get_logs(fromBlock=since_block, toBlock=to_block)
        except Exception:
            return []
        out = []
        for e in logs:
            tx_hash = (e["transactionHash"].hex()
                       if hasattr(e["transactionHash"], "hex")
                       else str(e["transactionHash"]))
            try:
                gas = int(w3.eth.get_transaction_receipt(tx_hash)["gasUsed"])
            except Exception:
                gas = 0
            out.append({"event": name, "args": _serialize(e["args"]),
                        "block": int(e["blockNumber"]),
                        "txHash": tx_hash, "gas": gas})
        return out

    events: list[dict] = []
    for name in ("AgreementRequested", "AgreementActive", "AgreementCancelled"):
        events += _gather_named(escrow, name)
    events += _gather_named(nft, "Transfer")
    events.sort(key=lambda e: e["block"])
    return events


if __name__ == "__main__":
    uvicorn.run("consumer.app:app", host="0.0.0.0", port=8001, reload=False)
