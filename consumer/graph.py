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
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

# Wrap the FastMCP tool functions as plain async callables.
# These attribute names are also monkey-patched in tests.
from consumer.mcp_server import (
    await_settlement as _await_settlement_tool,
    browse_catalog as _browse_catalog_tool,
    lock_payment as _lock_payment_tool,
    present_credential as _present_credential_tool,
    request_quote as _request_quote_tool,
)


class WorkflowState(TypedDict, total=False):
    user_message: str
    provider_url: str
    model: str
    catalog: list[dict]
    chosen_tier: str
    chosen_mbps: float
    agreement_id: str
    tx_hash: str
    token_id: int
    settle_attempts: int
    activation: dict
    final_response: str
    log: list[dict]
    thinking: list[str]
    error: str | None


def _log_call(state: WorkflowState, tool_name: str, args: dict) -> None:
    state.setdefault("log", []).append({
        "from": "consumer",
        "message": f"[MCP] {tool_name}({json.dumps(args)})",
    })


def _log_result(state: WorkflowState, sender: str, result: str) -> None:
    state.setdefault("log", []).append({
        "from": sender,
        "message": str(result)[:400],
    })


async def browse_node(state: WorkflowState) -> dict:
    args = {"provider_url": state["provider_url"]}
    _log_call(state, "browse_catalog", args)
    raw = await _browse_catalog_tool(state["provider_url"])
    _log_result(state, "provider", raw)
    if raw.startswith("ERROR"):
        return {"log": state["log"], "error": raw}
    try:
        catalog = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"log": state["log"], "error": f"could not parse catalog: {e}"}
    return {"log": state["log"], "catalog": catalog}
