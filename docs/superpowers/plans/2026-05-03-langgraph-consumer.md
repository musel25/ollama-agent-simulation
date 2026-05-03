# LangGraph Consumer Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the consumer's 12-iteration Ollama tool-calling loop with an explicit LangGraph state machine, so each workflow stage is a coded transition (not LLM-judged) and the small local model can no longer hallucinate completion of stages it never ran.

**Architecture:**
- A `StateGraph` with 7 nodes, one per acquisition stage (browse → pick_tier → quote → lock → settle → present → summary).
- 5 of 7 nodes are **deterministic** Python: they call existing FastMCP tool functions directly (no LLM in the loop). The model is only consulted at `pick_tier` (which tier to buy) and `summary` (one-sentence reply).
- `pick_tier` does NOT use bind_tools — small local models emit tool-call text unreliably (see `diagnosis.md §3.1`). Instead we prompt the model for a single-word tier name and parse it; if it's nonsense, we fall back to a deterministic rule. Same for `summary` (plain text generation; no tool calls).
- The 6-stage workflow from `paper/main.tex` becomes literal graph topology, closing the §3.1 paper-vs-code discrepancy.
- The dashboard's `inter_agent_log` contract is preserved verbatim — `consumer/ui.py` keeps working unchanged.

**Tech Stack:** LangGraph (`langgraph` Python pkg), `langchain-ollama` (`ChatOllama` for the two LLM nodes), existing FastMCP tools (`consumer/mcp_server.py`), FastAPI, pytest.

**Non-goals:**
- No change to `consumer/mcp_server.py` (tool functions stay as-is).
- No change to provider, contracts, A2A wire format, or dashboard UI.
- No use of `bind_tools` / structured output — the local 3B model can't be trusted with structured tool calling, so we route around it.

---

## File structure

| File | Status | Responsibility |
|---|---|---|
| `consumer/graph.py` | **new** | `WorkflowState` TypedDict, 7 node functions, `build_graph()` returning a compiled StateGraph |
| `consumer/app.py` | modify | `run_consumer` becomes a 5-line wrapper that invokes the compiled graph and returns its final state in the existing response shape |
| `tests/test_consumer_graph.py` | **new** | One test per node + one full-graph integration test with all MCP tools faked |
| `pyproject.toml` | modify | Add `langgraph` and `langchain-ollama` |
| `consumer/mcp_server.py` | unchanged | |
| `consumer/ui.py` | unchanged | |

---

## State schema (locked here, used in every task)

```python
# consumer/graph.py
from typing import TypedDict

class WorkflowState(TypedDict, total=False):
    # inputs
    user_message: str
    provider_url: str
    model: str

    # populated by nodes
    catalog: list[dict]            # browse_node
    chosen_tier: str               # pick_tier_node ("small"|"medium"|"large")
    chosen_mbps: float             # pick_tier_node
    agreement_id: str              # quote_node
    tx_hash: str                   # lock_node
    token_id: int                  # settle_node
    settle_attempts: int           # settle_node retry counter
    activation: dict               # present_node
    final_response: str            # summary_node OR error_node

    # transcript / observability — these are appended to, never overwritten
    log: list[dict]                # [{"from": "consumer"|"provider", "message": "..."}]
    thinking: list[str]            # LLM chain-of-thought from pick_tier / summary
    error: str | None              # set by any node on failure → routes to error_node
```

**Inter-agent log contract (must not change):**
- Before any A2A-bound MCP call: `log.append({"from": "consumer", "message": f"[MCP] {tool_name}({json.dumps(args)})"})`
- After A2A-bound result: `log.append({"from": "provider", "message": str(result)[:400]})`
- Local MCP tools (lock_payment, await_settlement) log with `from="consumer"` for both call and result.
- `consumer/ui.py:_parse_log_to_phases` greps for `"[MCP] request_quote"`, `"[MCP] get_catalog"`, `"requestAgreement() sent."`, `"Agreement ACTIVE."`, `"Gateway response:"`. We keep emitting those exact substrings.

---

## Graph topology (locked here)

```
START
  ↓
browse_node ─────────► (error → error_node)
  ↓
pick_tier_node ──────► (error → error_node)
  ↓
quote_node ──────────► (error → error_node)
  ↓
lock_node ───────────► (error → error_node)
  ↓
settle_node ─────────► (PENDING + attempts<3 → settle_node)
  ↓                    (error → error_node)
present_node ────────► (error → error_node)
  ↓
summary_node
  ↓
END

error_node → END
```

All happy-path edges are unconditional; error routing is a single `add_conditional_edges` per node that returns either the next node name or `"error_node"`.

---

## Task 1: Add dependencies and verify import

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the two deps**

Run from the repo root:

```bash
uv add langgraph langchain-ollama
```

Expected: `pyproject.toml` gets two new entries under `[project] dependencies`, `uv.lock` is regenerated.

- [ ] **Step 2: Sanity-import in the consumer container**

```bash
docker compose build consumer-agent
docker compose up -d consumer-agent
docker compose exec -T consumer-agent python -c "from langgraph.graph import StateGraph, START, END; from langchain_ollama import ChatOllama; print('ok')"
```

Expected: prints `ok`. If the import fails, `uv add` didn't propagate into the image — `Dockerfile.consumer` should already do `uv sync`, so a clean rebuild fixes it.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add langgraph + langchain-ollama deps"
git push
```

---

## Task 2: Create `consumer/graph.py` skeleton with state + browse_node

**Files:**
- Create: `consumer/graph.py`
- Create: `tests/test_consumer_graph.py`

- [ ] **Step 1: Write the failing test for browse_node**

Create `tests/test_consumer_graph.py`:

```python
"""Unit tests for consumer/graph.py nodes. MCP tool functions are monkey-patched."""
import json
import pytest

from consumer import graph as g


@pytest.fixture
def fake_catalog():
    return [
        {"packageId": "small",  "mbps": 2.0, "durationSeconds": 600, "priceWei": 10**16, "availableSlots": 1},
        {"packageId": "medium", "mbps": 5.0, "durationSeconds": 600, "priceWei": 2 * 10**16, "availableSlots": 1},
        {"packageId": "large",  "mbps": 8.0, "durationSeconds": 600, "priceWei": 8 * 10**16, "availableSlots": 1},
    ]


@pytest.mark.asyncio
async def test_browse_node_populates_catalog(monkeypatch, fake_catalog):
    async def fake_browse(provider_url):
        return json.dumps(fake_catalog)
    monkeypatch.setattr(g, "_browse_catalog_tool", fake_browse)

    state = {"provider_url": "http://provider:8002", "log": []}
    out = await g.browse_node(state)

    assert out["catalog"] == fake_catalog
    assert any("[MCP] browse_catalog" in e["message"] for e in out["log"])
    assert any(e["from"] == "provider" for e in out["log"])
    assert "error" not in out


@pytest.mark.asyncio
async def test_browse_node_handles_error(monkeypatch):
    async def fake_browse(provider_url):
        return "ERROR: provider unreachable"
    monkeypatch.setattr(g, "_browse_catalog_tool", fake_browse)

    out = await g.browse_node({"provider_url": "http://x", "log": []})
    assert out["error"]
    assert "provider unreachable" in out["error"]
```

- [ ] **Step 2: Run the test — it must fail because `graph.py` doesn't exist**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v
```

Expected: ImportError or `module 'consumer' has no attribute 'graph'`.

- [ ] **Step 3: Create `consumer/graph.py` with state + browse_node**

```python
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
```

- [ ] **Step 4: Run the tests — they must pass**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add consumer/graph.py tests/test_consumer_graph.py
git commit -m "feat(consumer): add LangGraph state schema and browse_node"
git push
```

---

## Task 3: pick_tier_node (LLM picker, robust to small-model nonsense)

**Files:**
- Modify: `consumer/graph.py`
- Modify: `tests/test_consumer_graph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer_graph.py`:

```python
@pytest.mark.asyncio
async def test_pick_tier_explicit_word(monkeypatch, fake_catalog):
    async def fake_llm(prompt: str, model: str) -> str:
        return "medium"
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.pick_tier_node({
        "user_message": "I want medium please",
        "catalog": fake_catalog,
        "log": [],
    })
    assert out["chosen_tier"] == "medium"
    assert out["chosen_mbps"] == 5.0


@pytest.mark.asyncio
async def test_pick_tier_numeric_request_falls_back_to_rule(monkeypatch, fake_catalog):
    # Even if the LLM returns garbage, the deterministic fallback picks the
    # smallest tier whose mbps >= user's requested number.
    async def fake_llm(prompt, model):
        return "I think probably the great one"  # not parseable
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.pick_tier_node({
        "user_message": "I need 4 Mbps",
        "catalog": fake_catalog,
        "log": [],
    })
    assert out["chosen_tier"] == "medium"


@pytest.mark.asyncio
async def test_pick_tier_request_exceeds_largest(monkeypatch, fake_catalog):
    async def fake_llm(prompt, model):
        return "???"
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.pick_tier_node({
        "user_message": "I need 100 Mbps",
        "catalog": fake_catalog,
        "log": [],
    })
    assert out["chosen_tier"] == "large"
```

- [ ] **Step 2: Run tests — they fail because `pick_tier_node` and `_llm_complete` don't exist**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v -k pick_tier
```

Expected: `AttributeError: module 'consumer.graph' has no attribute 'pick_tier_node'`.

- [ ] **Step 3: Implement `pick_tier_node` and `_llm_complete`**

Add to `consumer/graph.py`:

```python
import re

from langchain_ollama import ChatOllama

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Module-level cache so we don't reconnect for every node call.
_llm_cache: dict[str, ChatOllama] = {}


def _get_llm(model: str) -> ChatOllama:
    if model not in _llm_cache:
        _llm_cache[model] = ChatOllama(model=model, base_url=OLLAMA_HOST, temperature=0)
    return _llm_cache[model]


async def _llm_complete(prompt: str, model: str) -> str:
    """Plain text completion. Returns the model's content string (no tool calls)."""
    llm = _get_llm(model)
    resp = await llm.ainvoke(prompt)
    return (resp.content or "").strip()


_TIER_WORD_TO_RANK = {
    "small": 0, "cheapest": 0, "basic": 0, "minimum": 0,
    "medium": 1, "standard": 1, "mid": 1,
    "large": 2, "fast": 2, "biggest": 2, "premium": 2,
}


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

    return {
        "chosen_tier": chosen["packageId"],
        "chosen_mbps": chosen["mbps"],
        "thinking": state["thinking"],
    }
```

- [ ] **Step 4: Run tests — must pass**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v -k pick_tier
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add consumer/graph.py tests/test_consumer_graph.py
git commit -m "feat(consumer): add pick_tier_node with deterministic fallback"
git push
```

---

## Task 4: quote_node and lock_node (deterministic)

**Files:**
- Modify: `consumer/graph.py`
- Modify: `tests/test_consumer_graph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer_graph.py`:

```python
@pytest.mark.asyncio
async def test_quote_node(monkeypatch):
    async def fake_quote(provider_url, package_id):
        return json.dumps({
            "agreementId": "12345",
            "priceWei": 2 * 10**16,
            "bandwidthMbps": 5.0,
            "durationSeconds": 600,
        })
    monkeypatch.setattr(g, "_request_quote_tool", fake_quote)

    out = await g.quote_node({
        "provider_url": "http://provider:8002",
        "chosen_tier": "medium",
        "log": [],
    })
    assert out["agreement_id"] == "12345"
    assert any("[MCP] request_quote" in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_quote_node_propagates_error(monkeypatch):
    async def fake_quote(provider_url, package_id):
        return "ERROR: tier sold out"
    monkeypatch.setattr(g, "_request_quote_tool", fake_quote)

    out = await g.quote_node({
        "provider_url": "http://x", "chosen_tier": "medium", "log": [],
    })
    assert "tier sold out" in out["error"]


@pytest.mark.asyncio
async def test_lock_node(monkeypatch):
    def fake_lock(agreement_id):
        return "OK 0xabc123"
    monkeypatch.setattr(g, "_lock_payment_tool", fake_lock)

    out = await g.lock_node({"agreement_id": "12345", "log": []})
    assert out["tx_hash"] == "0xabc123"
    assert any("requestAgreement() sent." in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_lock_node_propagates_error(monkeypatch):
    def fake_lock(agreement_id):
        return "ERROR: insufficient funds"
    monkeypatch.setattr(g, "_lock_payment_tool", fake_lock)

    out = await g.lock_node({"agreement_id": "12345", "log": []})
    assert "insufficient funds" in out["error"]
```

- [ ] **Step 2: Run tests — must fail**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v -k "quote_node or lock_node"
```

Expected: AttributeErrors for `quote_node` and `lock_node`.

- [ ] **Step 3: Implement both nodes**

Add to `consumer/graph.py`:

```python
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
```

- [ ] **Step 4: Run tests — must pass**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v -k "quote_node or lock_node"
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add consumer/graph.py tests/test_consumer_graph.py
git commit -m "feat(consumer): add quote_node and lock_node"
git push
```

---

## Task 5: settle_node with PENDING retry

**Files:**
- Modify: `consumer/graph.py`
- Modify: `tests/test_consumer_graph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer_graph.py`:

```python
@pytest.mark.asyncio
async def test_settle_node_active(monkeypatch):
    def fake_settle(agreement_id):
        return "OK tokenId=42"
    monkeypatch.setattr(g, "_await_settlement_tool", fake_settle)

    out = await g.settle_node({"agreement_id": "12345", "log": [], "settle_attempts": 0})
    assert out["token_id"] == 42
    assert any("Agreement ACTIVE." in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_settle_node_pending_increments_counter(monkeypatch):
    def fake_settle(agreement_id):
        return "PENDING"
    monkeypatch.setattr(g, "_await_settlement_tool", fake_settle)

    out = await g.settle_node({"agreement_id": "12345", "log": [], "settle_attempts": 0})
    assert "token_id" not in out
    assert out["settle_attempts"] == 1
    assert "error" not in out


@pytest.mark.asyncio
async def test_settle_should_retry_routing():
    assert g._settle_route({"settle_attempts": 0}) == "settle_node"
    assert g._settle_route({"settle_attempts": 2}) == "settle_node"
    assert g._settle_route({"settle_attempts": 3}) == "error_node"
    assert g._settle_route({"token_id": 7, "settle_attempts": 1}) == "present_node"
    assert g._settle_route({"error": "boom"}) == "error_node"
```

- [ ] **Step 2: Run — must fail**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v -k settle
```

Expected: AttributeError for `settle_node` and `_settle_route`.

- [ ] **Step 3: Implement**

Add to `consumer/graph.py`:

```python
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
```

- [ ] **Step 4: Run — must pass**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v -k settle
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add consumer/graph.py tests/test_consumer_graph.py
git commit -m "feat(consumer): add settle_node with PENDING retry routing"
git push
```

---

## Task 6: present_node, summary_node, error_node, and graph wiring

**Files:**
- Modify: `consumer/graph.py`
- Modify: `tests/test_consumer_graph.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_consumer_graph.py`:

```python
@pytest.mark.asyncio
async def test_present_node(monkeypatch):
    async def fake_present(provider_url, token_id):
        return json.dumps({"status": "active", "bandwidthMbps": 5.0, "tokenId": token_id})
    monkeypatch.setattr(g, "_present_credential_tool", fake_present)

    out = await g.present_node({
        "provider_url": "http://provider:8002", "token_id": 42, "log": [],
    })
    assert out["activation"]["status"] == "active"
    assert any("Gateway response:" in e["message"] for e in out["log"])


@pytest.mark.asyncio
async def test_summary_node(monkeypatch):
    async def fake_llm(prompt, model):
        return "Done — medium tier (5 Mbps), agreementId=12345, tokenId=42."
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    out = await g.summary_node({
        "chosen_tier": "medium", "chosen_mbps": 5.0,
        "agreement_id": "12345", "token_id": 42,
        "activation": {"status": "active"},
        "thinking": [], "log": [],
    })
    assert "medium" in out["final_response"]
    assert "42" in out["final_response"]


@pytest.mark.asyncio
async def test_error_node():
    out = await g.error_node({"error": "ouch", "log": []})
    assert "ouch" in out["final_response"]


@pytest.mark.asyncio
async def test_full_graph_happy_path(monkeypatch, fake_catalog):
    async def fake_browse(url):
        return json.dumps(fake_catalog)
    async def fake_quote(url, pkg):
        return json.dumps({"agreementId": "777", "priceWei": 2e16,
                          "bandwidthMbps": 5.0, "durationSeconds": 600})
    def fake_lock(aid):
        return "OK 0xdeadbeef"
    def fake_settle(aid):
        return "OK tokenId=99"
    async def fake_present(url, tid):
        return json.dumps({"status": "active", "bandwidthMbps": 5.0, "tokenId": tid})
    async def fake_llm(prompt, model):
        return "medium" if "Reply with EXACTLY ONE WORD" in prompt else \
               "OK: medium (5 Mbps), agreementId=777, tokenId=99."

    monkeypatch.setattr(g, "_browse_catalog_tool", fake_browse)
    monkeypatch.setattr(g, "_request_quote_tool", fake_quote)
    monkeypatch.setattr(g, "_lock_payment_tool", fake_lock)
    monkeypatch.setattr(g, "_await_settlement_tool", fake_settle)
    monkeypatch.setattr(g, "_present_credential_tool", fake_present)
    monkeypatch.setattr(g, "_llm_complete", fake_llm)

    graph = g.build_graph()
    result = await graph.ainvoke({
        "user_message": "I need 5 Mbps",
        "provider_url": "http://provider:8002",
        "model": "qwen3:4b",
        "log": [], "thinking": [],
    })
    assert result["chosen_tier"] == "medium"
    assert result["agreement_id"] == "777"
    assert result["token_id"] == 99
    assert result["activation"]["status"] == "active"
    assert "777" in result["final_response"]
```

- [ ] **Step 2: Run — must fail**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v
```

Expected: 4 new tests fail with AttributeError on `present_node`, `summary_node`, `error_node`, `build_graph`.

- [ ] **Step 3: Implement the remaining three nodes + the graph builder**

Add to `consumer/graph.py`:

```python
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
    state["log"].append({
        "from": "provider",
        "message": f"Gateway response: {json.dumps(activation)}",
    })
    return {"log": state["log"], "activation": activation}


async def summary_node(state: WorkflowState) -> dict:
    prompt = (
        "Summarize this completed bandwidth purchase in ONE sentence. "
        "Use exactly these values verbatim — do NOT change any number:\n"
        f"- tier: {state['chosen_tier']}\n"
        f"- bandwidth: {state['chosen_mbps']} Mbps\n"
        f"- agreementId: {state['agreement_id']}\n"
        f"- tokenId: {state['token_id']}\n"
        f"- activation status: {state['activation'].get('status', 'unknown')}\n"
        "Reply with the sentence only — no preamble, no JSON, no tool calls."
    )
    text = await _llm_complete(prompt, state.get("model") or DEFAULT_MODEL)
    state.setdefault("thinking", []).append(f"summary raw: {text!r}")
    # Belt-and-braces: if the LLM didn't include the key facts, build a deterministic
    # sentence so the user always sees the truth.
    fallback = (f"Active service — {state['chosen_tier']} tier "
                f"({state['chosen_mbps']} Mbps), agreementId={state['agreement_id']}, "
                f"tokenId={state['token_id']}.")
    final = text if (str(state["agreement_id"]) in text and str(state["token_id"]) in text) else fallback
    return {"final_response": final, "thinking": state["thinking"]}


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
    builder.add_node("browse_node", browse_node)
    builder.add_node("pick_tier_node", pick_tier_node)
    builder.add_node("quote_node", quote_node)
    builder.add_node("lock_node", lock_node)
    builder.add_node("settle_node", settle_node)
    builder.add_node("present_node", present_node)
    builder.add_node("summary_node", summary_node)
    builder.add_node("error_node", error_node)

    builder.add_edge(START, "browse_node")
    builder.add_conditional_edges("browse_node", _route_after("pick_tier_node"))
    builder.add_conditional_edges("pick_tier_node", _route_after("quote_node"))
    builder.add_conditional_edges("quote_node", _route_after("lock_node"))
    builder.add_conditional_edges("lock_node", _route_after("settle_node"))
    builder.add_conditional_edges("settle_node", _settle_route)
    builder.add_conditional_edges("present_node", _route_after("summary_node"))
    builder.add_edge("summary_node", END)
    builder.add_edge("error_node", END)
    return builder.compile()
```

- [ ] **Step 4: Run all tests — must pass**

```bash
docker compose exec -T consumer-agent uv run pytest tests/test_consumer_graph.py -v
```

Expected: all tests pass (~12 total).

- [ ] **Step 5: Commit**

```bash
git add consumer/graph.py tests/test_consumer_graph.py
git commit -m "feat(consumer): wire LangGraph state machine end-to-end"
git push
```

---

## Task 7: Replace `run_consumer` with the compiled graph; manual e2e

**Files:**
- Modify: `consumer/app.py`

- [ ] **Step 1: Read current `run_consumer` to confirm response shape**

```bash
grep -n "run_consumer\|inter_agent_log\|ChatResponse" consumer/app.py
```

The contract that must be preserved:
- Returns `(visible_text, log_list, thinking_list)`.
- `inter_agent_log` is a module-level list cleared at the start of each call (the dashboard reads it via `GET /log`).

- [ ] **Step 2: Rewrite `run_consumer`**

Replace the `run_consumer` function (and remove the now-dead `_extract_thinking`, `_iter_json_objects`, `_parse_text_tool_calls`, `_mcp_tool_to_ollama`, `SYSTEM_PROMPT_TEMPLATE`, `A2A_BOUND_TOOLS`, the entire `MCPClient`/`ollama.AsyncClient` loop, and the `Message`/`re`/`fastmcp` imports if they become unused) with:

```python
from consumer.graph import build_graph

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
```

Also delete now-unused imports at the top of `consumer/app.py` — at minimum `re`, `from ollama._types import Message`, `from fastmcp import Client as MCPClient`, and the helper functions `_extract_thinking`, `_iter_json_objects`, `_parse_text_tool_calls`, `_mcp_tool_to_ollama`. Keep `_append`, `_logged`, `inter_agent_log`, the FastAPI app, `/chat`, `/log`, `/catalog_proxy`, `/address` routes — all unchanged.

- [ ] **Step 3: Restart the consumer and verify it boots**

```bash
docker compose restart consumer-agent
sleep 3
docker compose logs consumer-agent --tail=10
```

Expected: `Uvicorn running on http://0.0.0.0:8001`. No traceback.

- [ ] **Step 4: End-to-end smoke test from the command line**

```bash
curl -s -X POST http://localhost:8001/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"I need medium 5 Mbps"}' | python3 -m json.tool
```

Expected response (values will differ but shape must match):
```json
{
  "response": "Active service — medium tier (5.0 Mbps), agreementId=...,  tokenId=...",
  "log": [
    {"from": "consumer", "message": "[MCP] browse_catalog(...)"},
    {"from": "provider", "message": "[{\"packageId\": \"small\", ...}]"},
    {"from": "consumer", "message": "[MCP] request_quote(...)"},
    {"from": "provider", "message": "{\"agreementId\": ..., ...}"},
    {"from": "consumer", "message": "[MCP] lock_payment(...)"},
    {"from": "consumer", "message": "OK 0x..."},
    {"from": "consumer", "message": "requestAgreement() sent. tx=0x..."},
    {"from": "consumer", "message": "[MCP] await_settlement(...)"},
    {"from": "consumer", "message": "OK tokenId=..."},
    {"from": "consumer", "message": "Agreement ACTIVE. tokenId=..."},
    {"from": "consumer", "message": "[MCP] present_credential(...)"},
    {"from": "provider", "message": "{\"status\": \"active\", ...}"},
    {"from": "provider", "message": "Gateway response: {...}"}
  ],
  "thinking": ["pick_tier raw: ...", "summary raw: ..."]
}
```

The `response` field must contain a real `agreementId` (a long integer) and a real `tokenId` (a small integer like 1, 2, 3 — not a fabricated value). The `log` array must contain all 13 entries above; if any are missing, the corresponding stage didn't run.

- [ ] **Step 5: Verify the dashboard shows all four stages green**

Open http://localhost:8501, ask "I need medium 5 Mbps". Check the right column — Catalog, Quote, On-chain TX, Gateway must ALL show ✓ DONE (not "pending").

- [ ] **Step 6: Run the full test suite — must still pass**

```bash
docker compose exec -T consumer-agent uv run pytest -v
```

Expected: all green, including pre-existing tests.

- [ ] **Step 7: Commit**

```bash
git add consumer/app.py
git commit -m "refactor(consumer): replace tool-loop with LangGraph state machine"
git push
```

---

## Self-review

**Spec coverage:** Each requirement maps to a task —
- "LangGraph state machine" → Tasks 2–6.
- "Each node exposes only the relevant tool" → enforced by graph topology in Task 6 (no `bind_tools` at all; even more constrained than the original idea).
- "Hallucination of completion impossible" → `summary_node` runs only after `present_node` succeeds (Task 6 routing); fallback in `summary_node` rebuilds the sentence from real state if the LLM omits the values (Task 6).
- "Dashboard keeps working" → log-line strings preserved in Tasks 2/4/5/6 (`[MCP] ...`, `requestAgreement() sent.`, `Agreement ACTIVE.`, `Gateway response:`); manually verified in Task 7 Step 5.
- "Paper §3.1 alignment" → graph topology = paper's six stages; resolves the §3.1 LangGraph claim.
- "Tests" → unit per node + integration in Tasks 2–6; e2e curl + dashboard in Task 7.

**Placeholder scan:** No "TBD" / "TODO" / "similar to Task N" — every step has the actual code or command.

**Type / name consistency:** State keys (`chosen_tier`, `agreement_id`, `tx_hash`, `token_id`, `activation`, `settle_attempts`) match between schema (Task 2), every node body (Tasks 2–6), and the e2e response check (Task 7). Node names match between `add_node` calls and the routers (`_route_after`, `_settle_route`).

**Risk:** the only network dep is `langchain-ollama` reaching the Ollama HTTP API at `OLLAMA_HOST`. The compose stack already exposes `http://ollama:11434` to the consumer container — no infra change needed. If the small model emits weird text in `summary_node`, the fallback in Task 6 Step 3 reconstructs a correct sentence from state.
