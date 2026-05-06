"""LangGraph state machine for the consumer's bandwidth acquisition workflow.

Each node corresponds to one stage of the paper's six-stage workflow.
The LLM is consulted only at pick_tier_node and summary_node. Every
on-chain or A2A call goes through one of the consumer MCP tools, passed
in as a `tools` dict so the graph is testable without a real MCP server.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable, TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from consumer.tier_selection import deterministic_tier_pick, rank_catalog
from shared.config import Config


REQUIRED_PROVIDER_SKILLS = ("get_catalog", "request_quote", "activate")
_SETTLE_MAX_ATTEMPTS = 3
_A2A_TOOLS = frozenset({
    "discover_provider", "browse_catalog", "request_quote", "present_credential",
})


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


# Tool dict shape: name → async or sync callable. Built by build_consumer_tools().
ToolMap = dict[str, Callable[..., Awaitable[str] | str]]


async def _call_tool(tools: ToolMap, name: str, *args, **kwargs) -> str:
    """Invoke a tool that may be sync or async, returning its string result."""
    fn = tools[name]
    out = fn(*args, **kwargs)
    if asyncio.iscoroutine(out):
        return await out
    return await asyncio.to_thread(lambda: out) if False else out


def _log_call(state: WorkflowState, tool_name: str, args: dict) -> None:
    prefix = "[A2A]" if tool_name in _A2A_TOOLS else "[MCP]"
    state.setdefault("log", []).append({
        "from": "consumer",
        "message": f"{prefix} {tool_name}({json.dumps(args)})",
    })


def _log_result(state: WorkflowState, sender: str, result: str) -> None:
    state.setdefault("log", []).append({
        "from": sender, "message": str(result)[:400],
    })


def build_graph(cfg: Config, tools: ToolMap):
    """Compile the LangGraph state machine for the consumer agent.

    `tools` must provide the seven keys: discover_provider, browse_catalog,
    request_quote, lock_payment, await_settlement, present_credential,
    verify_credential. See `build_consumer_tools(cfg)` for the default
    factory that wires them to the consumer MCP server.
    """
    llm_cache: dict[str, ChatOllama] = {}

    def _llm(model: str) -> ChatOllama:
        if model not in llm_cache:
            llm_cache[model] = ChatOllama(
                model=model, base_url=cfg.ollama_host, temperature=0)
        return llm_cache[model]

    async def _llm_complete(prompt: str, model: str) -> str:
        resp = await _llm(model).ainvoke(prompt)
        return (resp.content or "").strip()

    async def discover_node(state: WorkflowState) -> dict:
        urls = state.get("provider_urls") or [state["provider_url"]]
        raws = await asyncio.gather(*(
            _call_tool(tools, "discover_provider", u) for u in urls))
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
                state["log"].append({"from": "consumer",
                                     "message": f"Skipping {url}: missing skills {missing}"})
                continue
            surviving.append(url)
        if not surviving:
            return {"log": state["log"],
                    "error": "no providers advertise the required skills"}
        return {"log": state["log"], "provider_urls": surviving,
                "provider_url": surviving[0]}

    async def browse_node(state: WorkflowState) -> dict:
        urls = state.get("provider_urls") or [state["provider_url"]]
        raws = await asyncio.gather(*(
            _call_tool(tools, "browse_catalog", u) for u in urls))
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
            offers.extend({**t, "provider_url": url} for t in tiers)
        if not offers:
            return {"log": state["log"],
                    "error": "no offers returned from any discovered provider"}
        by_pkg: dict[str, dict] = {}
        for o in offers:
            prev = by_pkg.get(o["packageId"])
            if prev is None or o["priceWei"] < prev["priceWei"]:
                by_pkg[o["packageId"]] = o
        return {"log": state["log"], "offers": offers,
                "catalog": list(by_pkg.values())}

    async def pick_tier_node(state: WorkflowState) -> dict:
        catalog = state["catalog"]
        ranked = rank_catalog(catalog)
        valid = {p["packageId"].lower() for p in ranked}
        prompt = (
            f"User says: {state['user_message']!r}\n"
            f"Catalog tiers (smallest to largest):\n"
            + "\n".join(f"- {p['packageId']}: {p['mbps']} Mbps" for p in ranked)
            + "\n\nReply with EXACTLY ONE WORD: the packageId you choose. "
              "No punctuation, no explanation, no JSON. Just the word."
        )
        raw = await _llm_complete(prompt,
                                  state.get("model") or cfg.ollama_model)
        state.setdefault("thinking", []).append(f"pick_tier raw: {raw!r}")
        chosen = None
        for token in re.findall(r"[a-zA-Z]+", raw.lower()):
            if token in valid:
                chosen = next(
                    p for p in ranked if p["packageId"].lower() == token)
                break
        if chosen is None:
            chosen = deterministic_tier_pick(state["user_message"], catalog)
        offers = state.get("offers") or [chosen]
        matching = [o for o in offers if o["packageId"] == chosen["packageId"]]
        best = min(matching, key=lambda o: o["priceWei"])
        chosen_url = best.get("provider_url") or state.get("provider_url", "")
        state.setdefault("log", []).append({"from": "consumer",
            "message": (f"Chose {best['packageId']} ({best['mbps']} Mbps) "
                        f"from {chosen_url} at {best['priceWei']} wei")})
        return {"chosen_tier": best["packageId"], "chosen_mbps": best["mbps"],
                "provider_url": chosen_url,
                "thinking": state["thinking"], "log": state["log"]}

    async def quote_node(state: WorkflowState) -> dict:
        args = {"provider_url": state["provider_url"],
                "package_id": state["chosen_tier"]}
        _log_call(state, "request_quote", args)
        raw = await _call_tool(tools, "request_quote",
                               state["provider_url"], state["chosen_tier"])
        _log_result(state, "provider", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        try:
            quote = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"log": state["log"],
                    "error": f"could not parse quote: {e}"}
        return {"log": state["log"], "agreement_id": str(quote["agreementId"])}

    async def lock_node(state: WorkflowState) -> dict:
        args = {"agreement_id": state["agreement_id"]}
        _log_call(state, "lock_payment", args)
        raw = await asyncio.to_thread(tools["lock_payment"],
                                      state["agreement_id"])
        _log_result(state, "consumer", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        tx_hash = raw.removeprefix("OK ").strip()
        state["log"].append({"from": "consumer",
                             "message": f"requestAgreement() sent. tx={tx_hash}"})
        return {"log": state["log"], "tx_hash": tx_hash}

    async def settle_node(state: WorkflowState) -> dict:
        args = {"agreement_id": state["agreement_id"]}
        _log_call(state, "await_settlement", args)
        raw = await asyncio.to_thread(tools["await_settlement"],
                                      state["agreement_id"])
        _log_result(state, "consumer", raw)
        attempts = state.get("settle_attempts", 0) + 1
        if raw == "PENDING":
            return {"log": state["log"], "settle_attempts": attempts}
        if raw.startswith("ERROR"):
            return {"log": state["log"], "settle_attempts": attempts,
                    "error": raw}
        if raw.startswith("OK tokenId="):
            token_id = int(raw.removeprefix("OK tokenId=").strip())
            state["log"].append({"from": "consumer",
                "message": f"Agreement ACTIVE. tokenId={token_id}"})
            return {"log": state["log"], "settle_attempts": attempts,
                    "token_id": token_id}
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
        args = {"provider_url": state["provider_url"],
                "token_id": state["token_id"]}
        _log_call(state, "present_credential", args)
        raw = await _call_tool(tools, "present_credential",
                               state["provider_url"], state["token_id"])
        _log_result(state, "provider", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        try:
            activation = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"log": state["log"],
                    "error": f"could not parse activation: {e}"}
        if not isinstance(activation, dict):
            return {"log": state["log"],
                    "error": f"activation is not a JSON object: {raw[:200]}"}
        if activation.get("status") != "active":
            return {"log": state["log"],
                    "error": f"activation not active: {activation}"}
        state["log"].append({"from": "provider",
            "message": f"Gateway response: {json.dumps(activation)}"})
        return {"log": state["log"], "activation": activation}

    async def verify_node(state: WorkflowState) -> dict:
        args = {"token_id": state["token_id"]}
        _log_call(state, "verify_credential", args)
        raw = await asyncio.to_thread(tools["verify_credential"],
                                      state["token_id"])
        _log_result(state, "consumer", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        try:
            verified = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"log": state["log"],
                    "error": f"could not parse verification: {e}"}
        expected_mbps = int(state["chosen_mbps"])
        if int(verified["mbps"]) != expected_mbps:
            return {"log": state["log"],
                    "on_chain_verification": verified,
                    "error": (f"on-chain mbps mismatch: NFT grants "
                              f"{verified['mbps']} but quote promised "
                              f"{expected_mbps}")}
        if not verified.get("ownerIsConsumer"):
            return {"log": state["log"],
                    "on_chain_verification": verified,
                    "error": (f"NFT not owned by consumer "
                              f"(owner={verified.get('owner')})")}
        state["log"].append({"from": "consumer",
            "message": (f"On-chain verification OK: tokenId={state['token_id']} "
                        f"grants {verified['mbps']} Mbps for "
                        f"{verified['secondsRemaining']}s "
                        f"(endpoint={verified['endpoint']})")})
        return {"log": state["log"], "on_chain_verification": verified}

    async def summary_node(state: WorkflowState) -> dict:
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
            text = await _llm_complete(prompt,
                                       state.get("model") or cfg.ollama_model)
        except Exception as e:
            text = f"<llm error: {e}>"
        state.setdefault("thinking", []).append(f"summary raw: {text!r}")
        return {"final_response": sentence, "thinking": state["thinking"]}

    async def error_node(state: WorkflowState) -> dict:
        msg = state.get("error") or "unknown error"
        return {"final_response": f"Workflow stopped: {msg}"}

    def _route_after(next_node: str):
        def router(state: WorkflowState) -> str:
            return "error_node" if state.get("error") else next_node
        return router

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


def build_consumer_tools(cfg: Config) -> ToolMap:
    """Build the default tool dict by spinning up the consumer MCP server.

    Returns a dict that maps tool names to plain callables (sync or async).
    Notebooks can pass a hand-rolled dict instead to swap in stubs.
    """
    from consumer.mcp_server import build_mcp_server  # local import to avoid cycle
    mcp, _ = build_mcp_server(cfg)
    # FastMCP stores tools under keys like "tool:<name>@" in
    # _local_provider._components. The earlier shim used the same path.
    _components = mcp._local_provider._components  # type: ignore[attr-defined]
    _tools = {v.name: v for k, v in _components.items() if k.startswith("tool:")}
    return {name: tool.fn for name, tool in _tools.items()}
