"""
Consumer agent FastAPI service — port 8001.

The workflow is driven by a LangGraph state machine (consumer/graph.py).
Cross-agent calls (browse_catalog / request_quote / present_credential) are
A2A under the hood, hidden by the MCP layer inside each graph node.
"""
import json
import os
import traceback

import uvicorn
from fastapi import FastAPI, HTTPException
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

from consumer.agent_card import build_consumer_agent_card
from consumer.graph import build_graph
from consumer.mcp_server import mcp as consumer_mcp

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
PROVIDER_A2A_URLS = [u.strip() for u in
                     os.environ.get("PROVIDER_A2A_URLS",
                                    os.environ.get("PROVIDER_BASE_URL",
                                                   "http://localhost:8002")).split(",")
                     if u.strip()]

_consumer_agent_card = build_consumer_agent_card()
_AGENT_CARD_JSON = MessageToDict(_consumer_agent_card, preserving_proto_field_name=True)

inter_agent_log: list[dict] = []
_logged: set[tuple[str, str]] = set()


def _append(sender: str, message: str) -> None:
    key = (sender, message)
    if key in _logged:
        return
    _logged.add(key)
    inter_agent_log.append({"from": sender, "message": message})


_compiled_graph = build_graph()


async def run_consumer(user_message: str, model: str = DEFAULT_MODEL) -> tuple[str, list[dict], list[str]]:
    inter_agent_log.clear()
    _logged.clear()

    initial: dict = {
        "user_message": user_message,
        "provider_url": PROVIDER_A2A_URLS[0],
        "model": model,
        "log": [],
        "thinking": [],
    }
    final = await _compiled_graph.ainvoke(initial)

    # Mirror the graph's log into the module-level list the dashboard polls.
    for entry in final.get("log", []):
        _append(entry["from"], entry["message"])

    return (
        final.get("final_response", "(no response)"),
        list(inter_agent_log),
        final.get("thinking", []),
    )


app = FastAPI(title="Consumer Agent")


class ChatRequest(BaseModel):
    message: str
    model: str = DEFAULT_MODEL


class ChatResponse(BaseModel):
    response: str
    log: list[dict]
    thinking: list[str] = Field(default_factory=list)


@app.get("/.well-known/agent-card.json")
def agent_card_canonical() -> dict:
    return _AGENT_CARD_JSON


@app.get("/.well-known/agent.json")
def agent_card_legacy() -> dict:
    return _AGENT_CARD_JSON


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        response_text, log, thinking = await run_consumer(req.message, model=req.model)
        return ChatResponse(response=response_text, log=log, thinking=thinking)
    except Exception as e:
        traceback.print_exc()
        return ChatResponse(response=f"INTERNAL ERROR: {e}", log=[], thinking=[])


@app.get("/log")
def get_log() -> list[dict]:
    return list(inter_agent_log)


@app.delete("/log")
def clear_log() -> dict:
    inter_agent_log.clear()
    return {"cleared": True}


@app.get("/catalog_proxy")
async def catalog_proxy() -> list[dict]:
    async with MCPClient(consumer_mcp) as c:
        result = await c.call_tool("browse_catalog",
                                   {"provider_url": PROVIDER_A2A_URLS[0]})
        text = result.content[0].text if result.content else ""
    if text.startswith("ERROR"):
        raise HTTPException(502, text)
    return json.loads(text)


@app.get("/address")
async def consumer_address_endpoint() -> dict:
    async with MCPClient(consumer_mcp) as c:
        result = await c.call_tool("wallet_address", {})
    return {"address": result.content[0].text}


if __name__ == "__main__":
    uvicorn.run("consumer.app:app", host="0.0.0.0", port=8001, reload=False)
