"""
Consumer agent FastAPI service — port 8001.
Owns the consumer EOA. The LLM tool-calling loop runs here;
all chain interactions are executed by Python, not the LLM.
"""
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

from shared.contracts import get_escrow_contract, get_nft_contract

# ── Ethereum setup ─────────────────────────────────────────────────────────────
RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
CONSUMER_PRIVATE_KEY = os.environ["CONSUMER_PRIVATE_KEY"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
consumer_account = Account.from_key(CONSUMER_PRIVATE_KEY)
CONSUMER_ADDRESS = consumer_account.address

PROVIDER_BASE_URL = os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002")
GATEWAY_BASE_URL = os.environ.get("GATEWAY_BASE_URL", "http://localhost:8003")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")

inter_agent_log: list[dict] = []
_logged_interactions: set[tuple[str, str]] = set()


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

    # Handle truncated thinking: content before a bare </think> with no opening tag
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


# ── LLM tools ─────────────────────────────────────────────────────────────────

def query_provider_catalog() -> str:
    """Return available bandwidth packages from the provider as a formatted string."""
    _append_interaction("consumer", "GET /catalog")
    with httpx.Client() as client:
        resp = client.get(f"{PROVIDER_BASE_URL}/catalog")
        resp.raise_for_status()
    catalog = resp.json()
    lines = [
        f"{p['packageId']}: {p['mbps']} Mbps / {p['durationSeconds']}s / "
        f"{float(Web3.from_wei(p['priceWei'], 'ether'))} ETH "
        f"({p['availableSlots']} slots available)"
        for p in catalog
    ]
    result = "\n".join(lines)
    _append_interaction("provider", result)
    return result


def request_agreement_on_chain(package_id: str) -> str:
    """
    Get a quote from the provider for the given package, then call
    escrow.requestAgreement() on-chain locking ETH equal to the quoted price.

    Args:
        package_id: One of 'small', 'medium', 'large'.

    Returns:
        String with agreementId and tx hash, or an error message.
    """
    _append_interaction("consumer", f"POST /quote package_id={package_id}")
    try:
        provider_address = _get_provider_address()
        with httpx.Client() as client:
            resp = client.post(
                f"{PROVIDER_BASE_URL}/quote",
                json={"packageId": package_id, "consumerAddress": CONSUMER_ADDRESS},
            )
            resp.raise_for_status()
        quote = resp.json()
    except Exception as e:
        return f"ERROR getting quote: {e}"

    agreement_id = quote["agreementId"]
    price_wei = quote["priceWei"]
    mbps = quote["bandwidthMbps"]
    dur = quote["durationSeconds"]

    _append_interaction(
        "provider",
        f"Quote received: agreementId={agreement_id}, price={float(Web3.from_wei(price_wei, 'ether'))} ETH",
    )

    escrow = get_escrow_contract(w3)
    try:
        tx_hash = _send_tx(
            escrow.functions.requestAgreement(agreement_id, provider_address, mbps, dur),
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
        agreement_id: The agreementId returned by request_agreement_on_chain (as a string to preserve uint256 precision).

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


STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}

# ── LLM loop ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a bandwidth procurement agent for a blockchain-based network service.
Your goal is to get the user an ACTIVE service token — complete the full purchase workflow whenever you can determine the right tier.

Tools available:
1. query_provider_catalog — fetch available packages and prices
2. request_agreement_on_chain — get a quote and lock ETH on-chain
3. check_agreement_status — verify settlement and get the active token

Workflow — run every step when you can determine the tier:
1. Call query_provider_catalog to fetch the catalog (skip only if the user names an exact tier: small, medium, or large).
2. Pick the package whose bandwidth best matches the request. Use the smallest tier that satisfies the requirement.
3. Call request_agreement_on_chain with the chosen package_id.
4. Call check_agreement_status immediately after. If REQUESTED (not yet settled), retry up to 5 times before giving up.
5. Reply with a summary: what was purchased, agreementId, tokenId, and bandwidth granted.

Clarification — ask ONE short question only when intent is genuinely ambiguous:
- Ambiguous: "give me something", "a package please", no bandwidth or tier specified at all.
- NOT ambiguous: any Mbps value, tier name (small/medium/large), "fastest", "cheapest", "at least X Mbps".
- If ambiguous, ask exactly: "Which tier? small (50 Mbps / 0.01 ETH), medium (100 Mbps / 0.02 ETH), or large (500 Mbps / 0.08 ETH)?"
- When the user's next message names a tier or bandwidth, immediately run the full workflow — do not ask again.

Rules:
- Default to proceeding autonomously. Only ask when you genuinely cannot determine the tier.
- CRITICAL: Only report the EXACT agreementId and tokenId returned by the tools. NEVER guess or use example numbers."""

TOOL_MAP = {
    "query_provider_catalog": query_provider_catalog,
    "request_agreement_on_chain": request_agreement_on_chain,
    "check_agreement_status": check_agreement_status,
}


def run_consumer(user_message: str, model: str = DEFAULT_MODEL) -> tuple[str, list[dict], list[str]]:
    inter_agent_log.clear()
    _logged_interactions.clear()
    thinking: list[str] = []
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    tools = [query_provider_catalog, request_agreement_on_chain, check_agreement_status]

    for _ in range(12):
        try:
            response = ollama.chat(model=model, messages=messages, tools=tools, think=False)
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
            fn = TOOL_MAP.get(tool_name)
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


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        response_text, log, thinking = run_consumer(req.message, model=req.model)
        return ChatResponse(response=response_text, log=log, thinking=thinking)
    except Exception as e:
        traceback.print_exc()
        return ChatResponse(
            response=f"INTERNAL ERROR: {e}",
            log=[],
            thinking=[]
        )


@app.get("/log")
def get_log() -> list[dict]:
    return list(inter_agent_log)


@app.delete("/log")
def clear_log() -> dict:
    inter_agent_log.clear()
    return {"cleared": True}


@app.get("/catalog_proxy")
def catalog_proxy() -> list[dict]:
    with httpx.Client() as client:
        resp = client.get(f"{PROVIDER_BASE_URL}/catalog")
        resp.raise_for_status()
    return resp.json()


@app.get("/address")
def consumer_address() -> dict:
    return {"address": CONSUMER_ADDRESS}


@app.get("/check_token")
def check_token(token_id: int = Query(..., alias="tokenId")) -> dict:
    """Manual token check from UI — signs nonce and calls gateway."""
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
