"""LangGraph state machine for the consumer's bandwidth acquisition workflow.

Each node corresponds to one stage of the paper's six-stage workflow.
The LLM is only consulted at pick_tier_node (which tier?) and summary_node
(one-sentence final reply). All on-chain and A2A calls are deterministic Python
that wraps the existing FastMCP tools in consumer/mcp_server.py.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

# Wrap the FastMCP tool functions as plain async callables.
# These attribute names are also monkey-patched in tests.
from consumer.mcp_server import (
    await_settlement as _await_settlement_tool,
    browse_catalog as _browse_catalog_tool,
    discover_provider as _discover_provider_tool,
    lock_payment as _lock_payment_tool,
    present_credential as _present_credential_tool,
    request_quote as _request_quote_tool,
    verify_credential as _verify_credential_tool,
)


REQUIRED_PROVIDER_SKILLS = ("get_catalog", "request_quote", "activate")


class WorkflowState(TypedDict, total=False):
    user_message: str
    provider_url: str
    provider_urls: list[str]
    offers: list[dict]
    model: str
    catalog: list[dict]
    chosen_tier: str
    chosen_mbps: float
    agreement_id: str
    tx_hash: str
    token_id: int
    settle_attempts: int
    activation: dict
    on_chain_verification: dict
    final_response: str
    log: list[dict]
    thinking: list[str]
    error: str | None


# Tools whose execution traverses HTTP to the provider (A2A wire), as opposed
# to purely local MCP tools that hit the chain or read local state. Used to
# tag log entries so the UI can distinguish A2A from local MCP.
_A2A_TOOLS = frozenset({
    "discover_provider", "browse_catalog", "request_quote", "present_credential",
})


def _log_call(state: WorkflowState, tool_name: str, args: dict) -> None:
    prefix = "[A2A]" if tool_name in _A2A_TOOLS else "[MCP]"
    state.setdefault("log", []).append({
        "from": "consumer",
        "message": f"{prefix} {tool_name}({json.dumps(args)})",
    })


def _log_result(state: WorkflowState, sender: str, result: str) -> None:
    state.setdefault("log", []).append({
        "from": sender,
        "message": str(result)[:400],
    })


DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Module-level cache so we don't reconnect for every node call.
_llm_cache: dict[str, ChatOllama] = {}

_TIER_WORD_TO_RANK = {
    "small": 0, "cheapest": 0, "basic": 0, "minimum": 0,
    "medium": 1, "standard": 1, "mid": 1,
    "large": 2, "fast": 2, "biggest": 2, "premium": 2,
}


def _get_llm(model: str) -> ChatOllama:
    if model not in _llm_cache:
        _llm_cache[model] = ChatOllama(model=model, base_url=OLLAMA_HOST, temperature=0)
    return _llm_cache[model]


async def _llm_complete(prompt: str, model: str) -> str:
    """Plain text completion. Returns the model's content string (no tool calls)."""
    llm = _get_llm(model)
    resp = await llm.ainvoke(prompt)
    return (resp.content or "").strip()


def _rank_catalog(catalog: list[dict]) -> list[dict]:
    """Sort tiers by mbps ascending so index 0=small, 1=medium, 2=large."""
    return sorted(catalog, key=lambda p: p["mbps"])


def _deterministic_tier_pick(user_message: str, catalog: list[dict]) -> dict:
    """Fallback rule used when the LLM output is not parseable to a tier word."""
    ranked = _rank_catalog(catalog)
    msg = user_message.lower()

    # Numeric "X Mbps" → smallest tier with mbps >= X; else largest tier.
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:mbps|mbit|m)\b", msg)
    if m:
        want = float(m.group(1))
        candidates = [p for p in ranked if p["mbps"] >= want]
        chosen = candidates[0] if candidates else ranked[-1]
        return chosen

    # Word match
    for word, rank in _TIER_WORD_TO_RANK.items():
        if word in msg:
            return ranked[min(rank, len(ranked) - 1)]

    return ranked[len(ranked) // 2]  # default: middle


async def discover_node(state: WorkflowState) -> dict:
    """Fetch each provider's agent card in parallel and keep only those that
    advertise the required skills. Populates state['provider_urls']."""
    urls = state.get("provider_urls") or [state["provider_url"]]
    raws = await asyncio.gather(*(_discover_provider_tool(u) for u in urls))

    surviving: list[str] = []
    for url, raw in zip(urls, raws):
        _log_call(state, "discover_provider", {"provider_url": url})
        _log_result(state, "provider", raw)
        if raw.startswith("ERROR"):
            continue
        try:
            card = json.loads(raw)
        except json.JSONDecodeError:
            continue
        skills = set(card.get("skills") or [])
        missing = set(REQUIRED_PROVIDER_SKILLS) - skills
        if missing:
            state["log"].append({
                "from": "consumer",
                "message": f"Skipping {url}: missing skills {missing}",
            })
            continue
        surviving.append(url)

    if not surviving:
        return {"log": state["log"],
                "error": "no providers advertise the required skills"}

    return {
        "log": state["log"],
        "provider_urls": surviving,
        "provider_url": surviving[0],
    }


async def browse_node(state: WorkflowState) -> dict:
    """Fan out browse_catalog across surviving providers in parallel; collect a
    flat list of offers tagged with their provider_url. The deduped `catalog`
    (cheapest offer per packageId) is what the LLM tier picker sees."""
    urls = state.get("provider_urls") or [state["provider_url"]]
    raws = await asyncio.gather(*(_browse_catalog_tool(u) for u in urls))

    offers: list[dict] = []
    for url, raw in zip(urls, raws):
        _log_call(state, "browse_catalog", {"provider_url": url})
        _log_result(state, "provider", raw)
        if raw.startswith("ERROR"):
            continue
        try:
            tiers = json.loads(raw)
        except json.JSONDecodeError:
            continue
        offers.extend({**tier, "provider_url": url} for tier in tiers)

    if not offers:
        return {"log": state["log"],
                "error": "no offers returned from any discovered provider"}

    by_pkg: dict[str, dict] = {}
    for o in offers:
        prev = by_pkg.get(o["packageId"])
        if prev is None or o["priceWei"] < prev["priceWei"]:
            by_pkg[o["packageId"]] = o

    return {"log": state["log"], "offers": offers, "catalog": list(by_pkg.values())}


async def pick_tier_node(state: WorkflowState) -> dict:
    catalog = state["catalog"]
    ranked = _rank_catalog(catalog)
    valid_words = {p["packageId"].lower() for p in ranked}

    prompt = (
        f"User says: {state['user_message']!r}\n"
        f"Catalog tiers (smallest to largest):\n"
        + "\n".join(f"- {p['packageId']}: {p['mbps']} Mbps" for p in ranked)
        + "\n\nReply with EXACTLY ONE WORD: the packageId you choose. "
          "No punctuation, no explanation, no JSON. Just the word."
    )
    raw = await _llm_complete(prompt, state.get("model") or DEFAULT_MODEL)

    state.setdefault("thinking", []).append(f"pick_tier raw: {raw!r}")

    # Try to find a tier word in the LLM output (case-insensitive, first match wins).
    chosen = None
    for token in re.findall(r"[a-zA-Z]+", raw.lower()):
        if token in valid_words:
            chosen = next(p for p in ranked if p["packageId"].lower() == token)
            break

    if chosen is None:
        chosen = _deterministic_tier_pick(state["user_message"], catalog)

    offers = state.get("offers") or [chosen]
    matching = [o for o in offers if o["packageId"] == chosen["packageId"]]
    best = min(matching, key=lambda o: o["priceWei"])
    chosen_url = best.get("provider_url") or state.get("provider_url", "")

    msg = (f"Chose {best['packageId']} ({best['mbps']} Mbps) from "
           f"{chosen_url} at {best['priceWei']} wei")
    state.setdefault("log", []).append({"from": "consumer", "message": msg})

    return {
        "chosen_tier": best["packageId"],
        "chosen_mbps": best["mbps"],
        "provider_url": chosen_url,
        "thinking": state["thinking"],
        "log": state["log"],
    }


async def quote_node(state: WorkflowState) -> dict:
    args = {"provider_url": state["provider_url"], "package_id": state["chosen_tier"]}
    _log_call(state, "request_quote", args)
    raw = await _request_quote_tool(state["provider_url"], state["chosen_tier"])
    _log_result(state, "provider", raw)
    if raw.startswith("ERROR"):
        return {"log": state["log"], "error": raw}
    try:
        quote = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"log": state["log"], "error": f"could not parse quote: {e}"}
    return {"log": state["log"], "agreement_id": str(quote["agreementId"])}


async def lock_node(state: WorkflowState) -> dict:
    args = {"agreement_id": state["agreement_id"]}
    _log_call(state, "lock_payment", args)
    # _lock_payment_tool is sync (does sync web3 calls); offload to a thread.
    raw = await asyncio.to_thread(_lock_payment_tool, state["agreement_id"])
    _log_result(state, "consumer", raw)
    if raw.startswith("ERROR"):
        return {"log": state["log"], "error": raw}
    # Extract the tx hash and emit the legacy log line the dashboard greps for.
    tx_hash = raw.removeprefix("OK ").strip()
    state["log"].append({
        "from": "consumer",
        "message": f"requestAgreement() sent. tx={tx_hash}",
    })
    return {"log": state["log"], "tx_hash": tx_hash}


_SETTLE_MAX_ATTEMPTS = 3


async def settle_node(state: WorkflowState) -> dict:
    args = {"agreement_id": state["agreement_id"]}
    _log_call(state, "await_settlement", args)
    raw = await asyncio.to_thread(_await_settlement_tool, state["agreement_id"])
    _log_result(state, "consumer", raw)

    attempts = state.get("settle_attempts", 0) + 1
    if raw == "PENDING":
        return {"log": state["log"], "settle_attempts": attempts}
    if raw.startswith("ERROR"):
        return {"log": state["log"], "settle_attempts": attempts, "error": raw}
    if raw.startswith("OK tokenId="):
        token_id = int(raw.removeprefix("OK tokenId=").strip())
        state["log"].append({
            "from": "consumer",
            "message": f"Agreement ACTIVE. tokenId={token_id}",
        })
        return {"log": state["log"], "settle_attempts": attempts, "token_id": token_id}
    return {"log": state["log"], "settle_attempts": attempts,
            "error": f"unexpected settlement response: {raw}"}


def _settle_route(state: WorkflowState) -> str:
    if state.get("error"):
        return "error_node"
    if "token_id" in state:
        return "present_node"
    if state.get("settle_attempts", 0) >= _SETTLE_MAX_ATTEMPTS:
        return "error_node"
    return "settle_node"


async def present_node(state: WorkflowState) -> dict:
    args = {"provider_url": state["provider_url"], "token_id": state["token_id"]}
    _log_call(state, "present_credential", args)
    raw = await _present_credential_tool(state["provider_url"], state["token_id"])
    _log_result(state, "provider", raw)
    if raw.startswith("ERROR"):
        return {"log": state["log"], "error": raw}
    try:
        activation = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"log": state["log"], "error": f"could not parse activation: {e}"}
    if not isinstance(activation, dict):
        return {"log": state["log"],
                "error": f"activation is not a JSON object: {raw[:200]}"}
    if activation.get("status") != "active":
        return {"log": state["log"],
                "error": f"activation not active: {activation}"}
    state["log"].append({
        "from": "provider",
        "message": f"Gateway response: {json.dumps(activation)}",
    })
    return {"log": state["log"], "activation": activation}


async def verify_node(state: WorkflowState) -> dict:
    """Independent on-chain check: confirm the NFT grants what the quote promised.
    Reads chain directly — does not trust the provider's activate response.
    """
    args = {"token_id": state["token_id"]}
    _log_call(state, "verify_credential", args)
    raw = await asyncio.to_thread(_verify_credential_tool, state["token_id"])
    _log_result(state, "consumer", raw)
    if raw.startswith("ERROR"):
        return {"log": state["log"], "error": raw}
    try:
        verified = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"log": state["log"], "error": f"could not parse verification: {e}"}

    expected_mbps = int(state["chosen_mbps"])
    if int(verified["mbps"]) != expected_mbps:
        return {"log": state["log"], "on_chain_verification": verified,
                "error": (f"on-chain mbps mismatch: NFT grants {verified['mbps']} "
                          f"but quote promised {expected_mbps}")}
    if not verified.get("ownerIsConsumer"):
        return {"log": state["log"], "on_chain_verification": verified,
                "error": f"NFT not owned by consumer (owner={verified.get('owner')})"}

    state["log"].append({
        "from": "consumer",
        "message": (f"On-chain verification OK: tokenId={state['token_id']} "
                    f"grants {verified['mbps']} Mbps for "
                    f"{verified['secondsRemaining']}s (endpoint={verified['endpoint']})"),
    })
    return {"log": state["log"], "on_chain_verification": verified}


async def summary_node(state: WorkflowState) -> dict:
    # Always return a deterministic, factually-correct sentence. We still call
    # the LLM (for observability / future prose flavor) but never use its
    # output as the user-visible response — small local models are unreliable
    # narrators and a fluently-wrong sentence would defeat the whole purpose
    # of the state-machine refactor.
    sentence = (f"Active service — {state['chosen_tier']} tier "
                f"({state['chosen_mbps']} Mbps), "
                f"agreementId={state['agreement_id']}, "
                f"tokenId={state['token_id']}.")
    prompt = (
        "Briefly acknowledge a successful bandwidth purchase:\n"
        f"- tier: {state['chosen_tier']}\n"
        f"- bandwidth: {state['chosen_mbps']} Mbps\n"
        f"- agreementId: {state['agreement_id']}\n"
        f"- tokenId: {state['token_id']}\n"
        "Reply with one short sentence."
    )
    try:
        text = await _llm_complete(prompt, state.get("model") or DEFAULT_MODEL)
    except Exception as e:
        text = f"<llm error: {e}>"
    state.setdefault("thinking", []).append(f"summary raw: {text!r}")
    return {"final_response": sentence, "thinking": state["thinking"]}


async def error_node(state: WorkflowState) -> dict:
    msg = state.get("error") or "unknown error"
    return {"final_response": f"Workflow stopped: {msg}"}


def _route_after(next_node: str):
    """Common error-routing factory: any node that set state['error'] jumps to error_node."""
    def router(state: WorkflowState) -> str:
        return "error_node" if state.get("error") else next_node
    return router


def build_graph():
    builder = StateGraph(WorkflowState)
    builder.add_node("discover_node", discover_node)
    builder.add_node("browse_node", browse_node)
    builder.add_node("pick_tier_node", pick_tier_node)
    builder.add_node("quote_node", quote_node)
    builder.add_node("lock_node", lock_node)
    builder.add_node("settle_node", settle_node)
    builder.add_node("present_node", present_node)
    builder.add_node("verify_node", verify_node)
    builder.add_node("summary_node", summary_node)
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "discover_node")
    builder.add_conditional_edges("discover_node", _route_after("browse_node"))
    builder.add_conditional_edges("browse_node", _route_after("pick_tier_node"))
    builder.add_conditional_edges("pick_tier_node", _route_after("quote_node"))
    builder.add_conditional_edges("quote_node", _route_after("lock_node"))
    builder.add_conditional_edges("lock_node", _route_after("settle_node"))
    builder.add_conditional_edges("settle_node", _settle_route)
    builder.add_conditional_edges("present_node", _route_after("verify_node"))
    builder.add_conditional_edges("verify_node", _route_after("summary_node"))
    builder.add_edge("summary_node", END)
    builder.add_edge("error_node", END)
    return builder.compile()
