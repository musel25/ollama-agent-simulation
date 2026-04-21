"""
Consumer agent FastAPI service — port 8001.
Uses MCP to call provider tools (get_catalog, request_quote).
Blockchain interactions (execute_agreement, check_agreement_status) remain local.
"""
import json
import os
import time
import traceback

import httpx
import ollama
import uvicorn
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from web3 import Web3

from consumer.mcp_client import (
    call_provider_tool,
    get_provider_tools,
    mcp_tool_to_ollama,
    quote_cache,
)
from shared.contracts import get_escrow_contract, get_nft_contract

RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
CONSUMER_PRIVATE_KEY = os.environ["CONSUMER_PRIVATE_KEY"]
PROVIDER_BASE_URL = os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002")
GATEWAY_BASE_URL = os.environ.get("GATEWAY_BASE_URL", "http://localhost:8003")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
consumer_account = Account.from_key(CONSUMER_PRIVATE_KEY)
CONSUMER_ADDRESS = consumer_account.address

inter_agent_log: list[dict] = []
_logged_interactions: set[tuple[str, str]] = set()

AGENT_CARD = {
    "name": "Bandwidth Consumer Agent",
    "description": "Autonomously purchases bandwidth packages from provider agents via on-chain escrow.",
    "version": "1.0.0",
    "protocols": ["mcp", "a2a"],
    "skills": [
        {
            "id": "purchase_bandwidth",
            "name": "Purchase Bandwidth",
            "description": "Given a tier or bandwidth requirement, negotiates and settles a bandwidth lease on-chain.",
        }
    ],
}

STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}


def _append_interaction(sender: str, message: str) -> None:
    key = (sender, message)
    if key in _logged_interactions:
        return
    _logged_interactions.add(key)
    inter_agent_log.append({"from": sender, "message": message})


def _extract_thinking(content: str) -> tuple[str, list[str]]:
    thoughts: list[str] = []
    visible_parts: list[str] = []
    remainder = content
    while "<think>" in remainder and "</think>" in remainder:
        before, rest = remainder.split("<think>", 1)
        thought, remainder = rest.split("</think>", 1)
        if before.strip():
            visible_parts.append(before.strip())
        if thought.strip():
            thoughts.append(thought.strip())
    if "</think>" in remainder:
        thought, remainder = remainder.split("</think>", 1)
        if thought.strip():
            thoughts.append(thought.strip())
    if remainder.strip():
        visible_parts.append(remainder.strip())
    return "\n\n".join(visible_parts), thoughts


def _send_tx(func, value: int = 0) -> str:
    tx = func.build_transaction({
        "from": CONSUMER_ADDRESS,
        "nonce": w3.eth.get_transaction_count(CONSUMER_ADDRESS, "pending"),
        "value": value,
    })
    signed = w3.eth.account.sign_transaction(tx, CONSUMER_PRIVATE_KEY)
    raw_tx = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


def _get_provider_address() -> str:
    with httpx.Client() as client:
        resp = client.get(f"{PROVIDER_BASE_URL}/address")
        resp.raise_for_status()
    return resp.json()["address"]


def execute_agreement(agreement_id: str) -> str:
    """
    Lock ETH on-chain for a previously quoted agreement.

    Args:
        agreement_id: The agreementId string returned by request_quote.

    Returns:
        Success message with tx hash, or error string.
    """
    quote = quote_cache.get(agreement_id)
    if not quote:
        return f"ERROR: No cached quote for agreementId={agreement_id}. Call request_quote first."

    price_wei = quote["priceWei"]
    mbps = quote["bandwidthMbps"]
    duration = quote["durationSeconds"]
    aid = int(agreement_id)

    _append_interaction("consumer", f"execute_agreement(agreementId={agreement_id})")

    try:
        provider_address = _get_provider_address()
        escrow = get_escrow_contract(w3)
        tx_hash = _send_tx(
            escrow.functions.requestAgreement(aid, provider_address, mbps, duration),
            value=price_wei,
        )
    except Exception as e:
        return f"ERROR calling requestAgreement on-chain: {e}"

    _append_interaction("consumer", f"requestAgreement() sent. tx={tx_hash}, agreementId={agreement_id}")
    return (
        f"Agreement requested on-chain. agreementId={agreement_id}, tx={tx_hash}. "
        "Provider will mint NFT and complete deposit. Use check_agreement_status to confirm."
    )


def check_agreement_status(agreement_id: str) -> str:
    """
    Check the on-chain status of an agreement. If ACTIVE, call the gateway to confirm service.

    Args:
        agreement_id: The agreementId string returned by request_quote (as string to preserve uint256 precision).

    Returns:
        Status string. If ACTIVE, includes bandwidth and seconds remaining.
    """
    try:
        aid = int(agreement_id)
    except (ValueError, TypeError):
        return f"ERROR: agreement_id must be a number, got: {agreement_id!r}"

    escrow = get_escrow_contract(w3)
    try:
        agreement = escrow.functions.getAgreement(aid).call()
    except Exception as e:
        return f"ERROR reading agreement {agreement_id}: {e}"

    status_code = agreement[7]
    status = STATUS_NAMES.get(status_code, "UNKNOWN")

    if status != "ACTIVE":
        return f"Agreement {agreement_id} is {status}. Not yet settled — try again in a few seconds."

    token_id = agreement[6]
    _append_interaction("consumer", f"Agreement ACTIVE. tokenId={token_id}. Calling gateway...")

    nonce = str(int(time.time()))
    message = encode_defunct(text=nonce)
    signed = w3.eth.account.sign_message(message, private_key=CONSUMER_PRIVATE_KEY)
    sig = signed.signature.hex()

    try:
        with httpx.Client() as client:
            resp = client.get(
                f"{GATEWAY_BASE_URL}/service",
                params={"tokenId": token_id},
                headers={"X-Nonce": nonce, "X-Signature": sig},
            )
            resp.raise_for_status()
        data = resp.json()
        _append_interaction("provider", f"Gateway response: {data}")
        return (
            f"Service ACTIVE. tokenId={token_id}, "
            f"{data['bandwidth_mbps']} Mbps, "
            f"{data['seconds_remaining']}s remaining, "
            f"endpoint={data['endpoint']}."
        )
    except Exception as e:
        return f"Agreement ACTIVE (tokenId={token_id}) but gateway check failed: {e}"


LOCAL_TOOL_MAP = {
    "execute_agreement": execute_agreement,
    "check_agreement_status": check_agreement_status,
}

LOCAL_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "execute_agreement",
            "description": "Lock ETH on-chain for a previously quoted agreement. Call after request_quote.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agreement_id": {
                        "type": "string",
                        "description": "The agreementId string returned by request_quote.",
                    }
                },
                "required": ["agreement_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_agreement_status",
            "description": "Check on-chain agreement status. If ACTIVE, confirms service via gateway.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agreement_id": {
                        "type": "string",
                        "description": "The agreementId string from request_quote.",
                    }
                },
                "required": ["agreement_id"],
            },
        },
    },
]

SYSTEM_PROMPT_TEMPLATE = """You are a bandwidth procurement agent. Your goal is to get the user an ACTIVE service token.

## Tools

Provider tools (via MCP — call these to interact with the provider):
1. get_catalog — fetch available packages and prices
2. request_quote(package_id, consumer_address) — get a quote and agreementId

Local blockchain tools:
3. execute_agreement(agreement_id) — lock ETH on-chain using the agreementId from request_quote
4. check_agreement_status(agreement_id) — verify settlement and get the active token

## Workflow — run every step when you can determine the tier

1. Call get_catalog to fetch packages (skip only if user names an exact tier: small, medium, large).
2. Pick the smallest tier that satisfies the request.
3. Call request_quote with the chosen package_id and consumer_address={consumer_address}.
4. Call execute_agreement with the agreementId from the quote.
5. Call check_agreement_status immediately. If REQUESTED (not yet settled), retry up to 5 times.
6. Reply with: what was purchased, agreementId, tokenId, and bandwidth granted.

## Tier mapping

| User says | Tier |
|-----------|------|
| small / 50 Mbps / cheapest / basic | small |
| medium / 100 Mbps / mid / standard | medium |
| large / 500 Mbps / fast / biggest / premium | large |

## Rules
- Proceed autonomously whenever you can determine the tier.
- Ask ONE short question only when intent is genuinely ambiguous (no bandwidth value, no tier name).
- CRITICAL: Only report the EXACT agreementId and tokenId returned by tools. NEVER guess or invent numbers."""


async def run_consumer(user_message: str, model: str = DEFAULT_MODEL) -> tuple[str, list[dict], list[str]]:
    inter_agent_log.clear()
    _logged_interactions.clear()
    thinking: list[str] = []

    mcp_tools_raw = await get_provider_tools()
    mcp_tool_names = {t.name for t in mcp_tools_raw}
    mcp_tool_schemas = [mcp_tool_to_ollama(t) for t in mcp_tools_raw]

    all_tools = mcp_tool_schemas + LOCAL_TOOL_SCHEMAS

    system_content = SYSTEM_PROMPT_TEMPLATE.replace("{consumer_address}", CONSUMER_ADDRESS)
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_message},
    ]

    ollama_client = ollama.AsyncClient()

    for _ in range(12):
        try:
            response = await ollama_client.chat(model=model, messages=messages, tools=all_tools, think=False)
        except Exception as e:
            error_msg = f"Ollama Error: {e}"
            if "not found" in str(e).lower():
                error_msg += f"\n\nMake sure to pull the model first: `ollama pull {model}`"
            return error_msg, list(inter_agent_log), thinking

        msg = response.message
        visible_content, thought_chunks = _extract_thinking(msg.content or "")
        thinking.extend(thought_chunks)
        if msg.thinking:
            thinking.append(msg.thinking.strip())

        if not msg.tool_calls:
            break

        messages.append({
            "role": "assistant",
            "content": visible_content,
            "tool_calls": msg.tool_calls,
        })

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = tc.function.arguments or {}

            if tool_name in mcp_tool_names:
                _append_interaction("consumer", f"[MCP] {tool_name}({json.dumps(args)})")
                try:
                    result = await call_provider_tool(tool_name, args)
                except Exception as e:
                    result = f"ERROR calling MCP tool {tool_name}: {e}"
                _append_interaction("provider", result[:400])
            else:
                fn = LOCAL_TOOL_MAP.get(tool_name)
                if fn is None:
                    result = f"ERROR: unknown tool '{tool_name}'"
                else:
                    try:
                        result = fn(**args)
                    except Exception as e:
                        result = f"ERROR in {tool_name}: {e}"

            messages.append({"role": "tool", "tool_name": tool_name, "content": str(result)})
    else:
        return (
            "The agreement was submitted on-chain but the provider has not settled it yet after several retries. "
            "The NFT will be delivered automatically once the provider processes the event — check back shortly.",
            list(inter_agent_log),
            thinking,
        )

    return visible_content, list(inter_agent_log), thinking


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="Consumer Agent")


class ChatRequest(BaseModel):
    message: str
    model: str = DEFAULT_MODEL


class ChatResponse(BaseModel):
    response: str
    log: list[dict]
    thinking: list[str] = Field(default_factory=list)


@app.get("/.well-known/agent.json")
def agent_card() -> dict:
    return AGENT_CARD


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
    result = await call_provider_tool("get_catalog", {})
    return json.loads(result)


@app.get("/address")
def consumer_address() -> dict:
    return {"address": CONSUMER_ADDRESS}


@app.get("/check_token")
def check_token(token_id: int = Query(..., alias="tokenId")) -> dict:
    nonce = str(int(time.time()))
    message = encode_defunct(text=nonce)
    signed = w3.eth.account.sign_message(message, private_key=CONSUMER_PRIVATE_KEY)
    sig = signed.signature.hex()
    with httpx.Client() as client:
        resp = client.get(
            f"{GATEWAY_BASE_URL}/service",
            params={"tokenId": token_id},
            headers={"X-Nonce": nonce, "X-Signature": sig},
        )
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.json().get("detail", resp.text))
    return resp.json()


if __name__ == "__main__":
    uvicorn.run("consumer.app:app", host="0.0.0.0", port=8001, reload=False)
