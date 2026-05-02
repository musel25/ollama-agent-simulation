"""
Consumer agent FastAPI service — port 8001.

The LLM loop only sees the consumer's own MCP tools (in-memory FastMCP).
Cross-agent calls (browse_catalog / request_quote / present_credential) are
A2A under the hood, hidden by the MCP layer.
"""
import json
import os
import traceback

import ollama
import uvicorn
from fastapi import FastAPI, HTTPException
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

from consumer.agent_card import build_consumer_agent_card
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

A2A_BOUND_TOOLS = {"browse_catalog", "request_quote", "present_credential"}


def _append(sender: str, message: str) -> None:
    key = (sender, message)
    if key in _logged:
        return
    _logged.add(key)
    inter_agent_log.append({"from": sender, "message": message})


def _extract_thinking(content: str) -> tuple[str, list[str]]:
    thoughts: list[str] = []
    visible: list[str] = []
    rem = content
    while "<think>" in rem and "</think>" in rem:
        before, rest = rem.split("<think>", 1)
        thought, rem = rest.split("</think>", 1)
        if before.strip():
            visible.append(before.strip())
        if thought.strip():
            thoughts.append(thought.strip())
    if "</think>" in rem:
        thought, rem = rem.split("</think>", 1)
        if thought.strip():
            thoughts.append(thought.strip())
    if rem.strip():
        visible.append(rem.strip())
    return "\n\n".join(visible), thoughts


def _mcp_tool_to_ollama(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


SYSTEM_PROMPT_TEMPLATE = """You are a bandwidth procurement agent. Your goal is to get the user an ACTIVE service.

## Available providers
{provider_urls}

## Tools (all via your local MCP — do NOT make HTTP requests directly)

A2A-bound (talk to a provider, you must pass provider_url):
- browse_catalog(provider_url)
- request_quote(provider_url, package_id)
- present_credential(provider_url, token_id)

Local (operate on your own wallet / chain):
- wallet_address()
- sign_message(text)
- lock_payment(agreement_id)
- await_settlement(agreement_id)

## Workflow — execute every step in order, never stop early
1. browse_catalog on the (first) configured provider to see prices/availability.
2. Choose a tier from the catalog (see "Tier choice" below) — remember the chosen `packageId` and its `mbps`.
3. request_quote with that package_id; remember the agreementId from the result.
4. lock_payment with that agreementId — wait for "OK <txHash>".
5. await_settlement with that agreementId — call ONLY with the agreement_id, no other args. If it returns "PENDING", call await_settlement again. Move on to step 6 only after you get "OK tokenId=N".
6. present_credential with that tokenId (the integer N from step 5). This is REQUIRED — do not skip it. Wait for {{"status":"active",...}}.
7. Reply with one short sentence summarizing: which `packageId` (small/medium/large — copy verbatim from step 2), how many Mbps, the agreementId, and the tokenId. Do NOT rename the tier.

## Tier choice (apply in order)
1. If the user named a tier word (small/medium/large/cheapest/biggest/etc.), use that:
   - small / cheapest / basic / minimum  → tier with the smallest `mbps`
   - medium / standard / mid             → tier with the middle `mbps`
   - large / fast / biggest / premium    → tier with the largest `mbps`
2. Else if the user gave a number of Mbps:
   - Find every tier where `mbps >= user's requested Mbps`. Pick the one with the SMALLEST `mbps` among those.
   - If NO tier reaches the user's number (their ask exceeds the largest tier), pick the tier with the LARGEST `mbps`. Do not pick anything smaller than that just because it is cheaper.
3. Use exactly the `packageId` string from the catalog.

Worked examples (catalog: small=2, medium=5, large=8):
- user "I need 4 Mbps"   → medium (5 >= 4, smallest such)
- user "I need 5 Mbps"   → medium (5 >= 5)
- user "I need 8 Mbps"   → large
- user "I need 100 Mbps" → large (no tier reaches 100, so the LARGEST tier — never small)
- user "cheapest"        → small

## Rules
- Tier choice is YOUR reasoning — NOT a tool call. After browse_catalog, your next tool call must be request_quote with the chosen package_id.
- Pass provider_url as the FIRST argument to browse_catalog / request_quote / present_credential.
- Use wallet_address() if any tool needs the consumer address.
- Only report the EXACT agreementId and tokenId returned by tools — never invent.
- Do NOT stop after lock_payment or after a "PENDING" — settlement always finishes; keep calling await_settlement until you get "OK tokenId=N".
- Do NOT pass extra arguments like max_attempts, retry, timeout — only the parameters listed above.
"""


async def run_consumer(user_message: str, model: str = DEFAULT_MODEL) -> tuple[str, list[dict], list[str]]:
    inter_agent_log.clear()
    _logged.clear()
    thinking: list[str] = []
    visible = ""

    async with MCPClient(consumer_mcp) as mcp_client:
        tools_raw = await mcp_client.list_tools()
        tool_schemas = [_mcp_tool_to_ollama(t) for t in tools_raw]
        tool_names = {t.name for t in tools_raw}

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            provider_urls="\n".join(f"- {u}" for u in PROVIDER_A2A_URLS),
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ]

        ollama_client = ollama.AsyncClient()

        for _ in range(12):
            try:
                response = await ollama_client.chat(model=model, messages=messages,
                                                    tools=tool_schemas, think=False)
            except Exception as e:
                msg = f"Ollama Error: {e}"
                if "not found" in str(e).lower():
                    msg += f"\n\nMake sure to pull the model first: `ollama pull {model}`"
                return msg, list(inter_agent_log), thinking

            m = response.message
            visible, thought_chunks = _extract_thinking(m.content or "")
            thinking.extend(thought_chunks)
            if m.thinking:
                thinking.append(m.thinking.strip())

            if not m.tool_calls:
                break

            messages.append({"role": "assistant", "content": visible, "tool_calls": m.tool_calls})

            for tc in m.tool_calls:
                tool_name = tc.function.name
                args = tc.function.arguments or {}
                if tool_name not in tool_names:
                    result = f"ERROR: unknown tool '{tool_name}'"
                else:
                    _append("consumer", f"[MCP] {tool_name}({json.dumps(args)})")
                    try:
                        out = await mcp_client.call_tool(tool_name, args)
                        result = out.content[0].text if out.content else ""
                    except Exception as e:
                        result = f"ERROR calling {tool_name}: {e}"
                    sender = "provider" if tool_name in A2A_BOUND_TOOLS else "consumer"
                    _append(sender, str(result)[:400])
                messages.append({"role": "tool", "tool_name": tool_name, "content": str(result)})
        else:
            return ("Settlement still pending after several retries. The NFT will land "
                    "automatically once the provider processes the event — check back shortly.",
                    list(inter_agent_log), thinking)

    return visible, list(inter_agent_log), thinking


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
