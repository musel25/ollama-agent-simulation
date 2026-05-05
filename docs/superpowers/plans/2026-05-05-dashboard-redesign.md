# Dashboard Redesign — Two-Agent Symmetric Layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `consumer/ui.py` to a two-agent symmetric layout that surfaces Agent Cards, MCP tools (per-turn fired status), the A2A wire, on-chain events, and NFT/SDN state. Add the small backend hooks the new panels need (provider tool-call log, consumer chain-events endpoint).

**Architecture:** The provider gains an in-memory tool-call deque populated by a logging decorator wrapping every `@mcp.tool` definition, exposed via `GET /tool_log`. The consumer gains `GET /chain_events` that queries escrow + NFT events from Anvil. The Streamlit UI rewrites `consumer/ui.py` into 7 visual zones (header, 6-stage pipeline strip, triptych [consumer panel ‖ A2A wire ‖ provider panel], chat ‖ on-chain panel, NFT/SDN strip, iperf expander). All cumulative state lives in `st.session_state` to survive `inter_agent_log.clear()` on each `/chat` call.

**Tech Stack:** Python 3.13, Streamlit, FastAPI, FastMCP, LangGraph, web3.py, httpx — no new dependencies.

**Spec:** `docs/superpowers/specs/2026-05-05-dashboard-redesign-design.md`

---

## File Map

| File | Change |
|---|---|
| `provider/mcp_server.py` | Modify — add `tool_call_log` deque + `_logged` decorator; apply to every `@mcp.tool` |
| `provider/app.py` | Modify — add `GET /tool_log` endpoint |
| `consumer/app.py` | Modify — add `GET /chain_events` endpoint |
| `consumer/ui.py` | Full rewrite |
| `tests/test_provider_mcp.py` | Modify — add test that `tool_call_log` records calls |
| `tests/test_provider_app.py` | Create — test `/tool_log` route |
| `tests/test_consumer_app.py` | Create — test `/chain_events` route |

UI changes have no automated tests (consistent with the existing project — no Streamlit UI tests exist). Each UI task ends with a manual verification step against `make up` running locally.

---

## Task 1: Provider tool-call logging deque + decorator

**Files:**
- Modify: `provider/mcp_server.py`
- Modify: `tests/test_provider_mcp.py`

This adds the in-process record of every `@mcp.tool` invocation. The decorator is applied to each tool and runs the underlying function through a wrapper that appends `{tool, ts, status, args_summary}` to a module-level deque. We test that one round-trip via `Client(mcp)` produces one record.

- [ ] **Step 1: Write the failing test**

  Append to `tests/test_provider_mcp.py`:

  ```python
  @pytest.mark.asyncio
  async def test_tool_call_log_records_invocations():
      from provider import mcp_server
      mcp_server.tool_call_log.clear()

      from provider.mcp_server import mcp
      async with Client(mcp) as client:
          await client.call_tool("get_catalog", {})

      entries = list(mcp_server.tool_call_log)
      assert len(entries) == 1
      assert entries[0]["tool"] == "get_catalog"
      assert entries[0]["status"] == "ok"
      assert "ts" in entries[0]
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run pytest tests/test_provider_mcp.py::test_tool_call_log_records_invocations -v`
  Expected: FAIL with `AttributeError: module 'provider.mcp_server' has no attribute 'tool_call_log'`.

- [ ] **Step 3: Add deque + decorator and apply it**

  Open `provider/mcp_server.py`. After the existing imports, add:

  ```python
  import asyncio
  import inspect
  from collections import deque
  from functools import wraps

  tool_call_log: deque = deque(maxlen=500)


  def _summarize_args(kwargs: dict) -> dict:
      """Truncate values so log entries stay small."""
      out = {}
      for k, v in kwargs.items():
          s = str(v)
          out[k] = s if len(s) <= 80 else s[:77] + "..."
      return out


  def _logged(fn):
      """Wrap an MCP tool so each invocation appends one entry to tool_call_log.

      Records {tool, ts, args_summary, status} on entry as 'running' and
      flips status to 'ok' or 'error' once the underlying function returns.
      """
      tool_name = fn.__name__

      if inspect.iscoroutinefunction(fn):
          @wraps(fn)
          async def async_wrapper(*args, **kwargs):
              entry = {
                  "tool": tool_name,
                  "ts": time.time(),
                  "args": _summarize_args(kwargs),
                  "status": "running",
              }
              tool_call_log.append(entry)
              try:
                  result = await fn(*args, **kwargs)
                  entry["status"] = "ok"
                  return result
              except Exception:
                  entry["status"] = "error"
                  raise
          return async_wrapper

      @wraps(fn)
      def sync_wrapper(*args, **kwargs):
          entry = {
              "tool": tool_name,
              "ts": time.time(),
              "args": _summarize_args(kwargs),
              "status": "running",
          }
          tool_call_log.append(entry)
          try:
              result = fn(*args, **kwargs)
              entry["status"] = "ok"
              return result
          except Exception:
              entry["status"] = "error"
              raise
      return sync_wrapper
  ```

  Now apply `@_logged` to every existing `@mcp.tool()` definition. The decorator order is `@mcp.tool()` outer, `@_logged` inner (so logging wraps the function before FastMCP registers the wrapped version). For each existing tool, change:

  ```python
  @mcp.tool()
  def get_catalog() -> str:
      ...
  ```

  to:

  ```python
  @mcp.tool()
  @_logged
  def get_catalog() -> str:
      ...
  ```

  Apply to all 8 tools: `get_catalog`, `request_quote`, `verify_credential_ownership`, `mint_credential`, `complete_swap`, `allocate_bandwidth`, `revoke_bandwidth`, `verify_bandwidth`.

- [ ] **Step 4: Run the new test**

  Run: `uv run pytest tests/test_provider_mcp.py::test_tool_call_log_records_invocations -v`
  Expected: PASS.

- [ ] **Step 5: Run the full provider mcp test suite to confirm no regression**

  Run: `uv run pytest tests/test_provider_mcp.py -v`
  Expected: all tests pass (the decorator must preserve signatures via `functools.wraps` so FastMCP's schema introspection still works).

- [ ] **Step 6: Commit**

  ```bash
  git add provider/mcp_server.py tests/test_provider_mcp.py
  git commit -m "feat(provider): add in-process MCP tool-call log via @_logged decorator"
  ```

---

## Task 2: Provider `/tool_log` endpoint

**Files:**
- Modify: `provider/app.py`
- Create: `tests/test_provider_app.py`

Expose the deque from Task 1 over HTTP so the dashboard can poll it.

- [ ] **Step 1: Write the failing test**

  Create `tests/test_provider_app.py`:

  ```python
  """HTTP-level tests for provider/app.py routes that don't need anvil."""
  from __future__ import annotations

  import os

  import pytest
  from fastapi.testclient import TestClient


  @pytest.fixture
  def client(monkeypatch):
      # Provider app needs PROVIDER_PRIVATE_KEY at import time.
      monkeypatch.setenv(
          "PROVIDER_PRIVATE_KEY",
          "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
      )
      monkeypatch.setenv("SDN_MOCK", "true")
      from provider.app import app
      with TestClient(app) as c:
          yield c


  def test_tool_log_returns_recorded_entries(client):
      from provider import mcp_server
      mcp_server.tool_call_log.clear()
      mcp_server.tool_call_log.append({
          "tool": "get_catalog", "ts": 1.0, "args": {}, "status": "ok",
      })

      resp = client.get("/tool_log")
      assert resp.status_code == 200
      data = resp.json()
      assert isinstance(data, list)
      assert data[-1]["tool"] == "get_catalog"
      assert data[-1]["status"] == "ok"


  def test_tool_log_since_ts_filters(client):
      from provider import mcp_server
      mcp_server.tool_call_log.clear()
      mcp_server.tool_call_log.append({"tool": "a", "ts": 1.0, "args": {}, "status": "ok"})
      mcp_server.tool_call_log.append({"tool": "b", "ts": 5.0, "args": {}, "status": "ok"})

      resp = client.get("/tool_log", params={"since_ts": 2.0})
      assert resp.status_code == 200
      data = resp.json()
      assert [e["tool"] for e in data] == ["b"]
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run pytest tests/test_provider_app.py -v`
  Expected: FAIL with `404` because `/tool_log` doesn't exist yet.

- [ ] **Step 3: Add the endpoint**

  Open `provider/app.py`. Just before the A2A handler block (the `_a2a_handler = DefaultRequestHandler(...)` line near the bottom), insert:

  ```python
  @app.get("/tool_log")
  def get_tool_log(since_ts: float | None = None) -> list[dict]:
      from provider.mcp_server import tool_call_log
      entries = list(tool_call_log)
      if since_ts is not None:
          entries = [e for e in entries if e["ts"] > since_ts]
      return entries
  ```

- [ ] **Step 4: Run the new tests**

  Run: `uv run pytest tests/test_provider_app.py -v`
  Expected: both tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add provider/app.py tests/test_provider_app.py
  git commit -m "feat(provider): expose tool_call_log via GET /tool_log"
  ```

---

## Task 3: Consumer `/chain_events` endpoint

**Files:**
- Modify: `consumer/app.py`
- Create: `tests/test_consumer_app.py`

Returns escrow `AgreementRequested` + `Deposit` and NFT `Transfer` events for the on-chain panel. The dashboard polls this once per turn.

- [ ] **Step 1: Write the failing test**

  Create `tests/test_consumer_app.py`:

  ```python
  """HTTP-level tests for consumer/app.py routes that mock web3."""
  from __future__ import annotations

  from unittest.mock import MagicMock

  import pytest
  from fastapi.testclient import TestClient


  def _fake_event(name: str, args: dict, gas: int, block: int, tx_hash: str):
      """Build a w3-style event dict that matches what get_logs returns."""
      m = MagicMock()
      m.__getitem__.side_effect = lambda k: {
          "args": args,
          "blockNumber": block,
          "transactionHash": MagicMock(hex=lambda: tx_hash),
      }[k]
      return m


  @pytest.fixture
  def client(monkeypatch):
      monkeypatch.setenv("CONSUMER_PRIVATE_KEY",
                         "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a")
      from consumer.app import app
      with TestClient(app) as c:
          yield c


  def test_chain_events_returns_combined_events(client, monkeypatch):
      from consumer import app as consumer_app

      fake_escrow = MagicMock()
      fake_escrow.events.AgreementRequested.get_logs.return_value = []
      fake_escrow.events.Deposit.get_logs.return_value = []
      fake_nft = MagicMock()
      fake_nft.events.Transfer.get_logs.return_value = []

      fake_w3 = MagicMock()
      fake_w3.eth.block_number = 100
      fake_w3.eth.get_transaction_receipt.return_value = {"gasUsed": 50_000}

      monkeypatch.setattr(consumer_app, "_w3", fake_w3)
      monkeypatch.setattr(consumer_app, "get_escrow_contract", lambda w3: fake_escrow)
      monkeypatch.setattr(consumer_app, "get_nft_contract", lambda w3: fake_nft)

      resp = client.get("/chain_events", params={"since_block": 0})
      assert resp.status_code == 200
      data = resp.json()
      assert isinstance(data, list)
      assert data == []  # no events in this synthetic chain
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `uv run pytest tests/test_consumer_app.py -v`
  Expected: FAIL with `404` because `/chain_events` doesn't exist.

- [ ] **Step 3: Add the endpoint**

  Open `consumer/app.py`. After the existing `/probe_proxy` route, add:

  ```python
  @app.get("/chain_events")
  def chain_events(since_block: int = 0) -> list[dict]:
      """Return escrow + NFT events emitted since `since_block`.

      Used by the dashboard to populate the on-chain panel. Each event:
        {event, args, block, txHash, gas}
      where args is a JSON-safe dict of the event's indexed/non-indexed args.
      """
      escrow = get_escrow_contract(_w3)
      nft = get_nft_contract(_w3)
      to_block = _w3.eth.block_number

      def _serialize(args) -> dict:
          out = {}
          for k, v in dict(args).items():
              if isinstance(v, (bytes, bytearray)):
                  out[k] = "0x" + v.hex()
              elif hasattr(v, "hex") and not isinstance(v, (int, str)):
                  out[k] = v.hex()
              else:
                  out[k] = str(v) if not isinstance(v, (int, str, bool, type(None))) else v
          return out

      def _gather(get_logs_fn, name: str) -> list[dict]:
          try:
              logs = get_logs_fn(fromBlock=since_block, toBlock=to_block)
          except Exception:
              return []
          out = []
          for evt in logs:
              tx_hash = evt["transactionHash"].hex() if hasattr(evt["transactionHash"], "hex") else str(evt["transactionHash"])
              try:
                  gas = int(_w3.eth.get_transaction_receipt(tx_hash)["gasUsed"])
              except Exception:
                  gas = 0
              out.append({
                  "event": name,
                  "args": _serialize(evt["args"]),
                  "block": int(evt["blockNumber"]),
                  "txHash": tx_hash,
                  "gas": gas,
              })
          return out

      events: list[dict] = []
      events += _gather(escrow.events.AgreementRequested.get_logs, "AgreementRequested")
      events += _gather(escrow.events.Deposit.get_logs, "Deposit")
      events += _gather(nft.events.Transfer.get_logs, "Transfer")
      events.sort(key=lambda e: e["block"])
      return events
  ```

- [ ] **Step 4: Run the new test**

  Run: `uv run pytest tests/test_consumer_app.py -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add consumer/app.py tests/test_consumer_app.py
  git commit -m "feat(consumer): add GET /chain_events for dashboard on-chain panel"
  ```

---

## Task 4: UI scaffold — wipe, palette, sidebar, session_state

**Files:**
- Modify: `consumer/ui.py` (full rewrite begins here)

Replace the file with a clean shell: page config, single CSS block (palette + panel base styles), trimmed sidebar, `st.session_state` initialization. No body content yet — just the chrome. After this task, running the UI shows an empty dark page with the sidebar.

- [ ] **Step 1: Replace `consumer/ui.py` with the scaffold**

  Overwrite `consumer/ui.py` with:

  ```python
  """
  Streamlit dashboard — port 8501.

  Two-agent symmetric layout: consumer panel | A2A wire | provider panel.
  Pulls cumulative state from /chat, /tool_log, /chain_events into
  st.session_state so it survives inter_agent_log.clear() on each turn.
  """
  from __future__ import annotations

  import html as html_lib
  import json
  import os
  import re
  import time

  import httpx
  import streamlit as st
  from web3 import Web3

  CONSUMER_BASE_URL = os.environ.get("CONSUMER_BASE_URL", "http://localhost:8001")
  PROVIDER_BASE_URL = os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002")
  DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
  MODELS = list(dict.fromkeys([DEFAULT_MODEL, "qwen3:4b", "qwen3:1.7b"]))
  SDN_MOCK = os.environ.get("SDN_MOCK", "true").lower() == "true"

  # ── Streamlit page setup ───────────────────────────────────────────────────
  st.set_page_config(page_title="A2A Bandwidth Provisioning", layout="wide")

  st.markdown("""
  <style>
    :root {
      --bg-page: #0d0d12;
      --bg-panel: #13131c;
      --bg-deep: #0e0e16;
      --border: #2a2a3e;
      --border-soft: #1f1f2a;
      --text: #d8d8e0;
      --text-dim: #8a8a9a;
      --text-faint: #555;
      --accent-consumer: #818cf8;
      --accent-provider: #60a5fa;
      --accent-wire: #34d399;
      --accent-chain: #f59e0b;
      --accent-success: #22c55e;
      --accent-active: #3b82f6;
    }
    section[data-testid="stSidebar"] { width: 240px !important; min-width: 240px !important; }
    .block-container { padding-top: 1.6rem !important; padding-bottom: 1rem !important; max-width: 1600px; }
    .stApp { background: var(--bg-page); }

    .panel { background: var(--bg-panel); border: 1px solid var(--border);
             border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; }
    .panel-title { font-size: 11px; font-weight: 600; letter-spacing: 0.6px;
                   text-transform: uppercase; color: #cfd6ff;
                   display:flex; justify-content:space-between; align-items:center;
                   margin-bottom: 8px; }
    .panel-title .meta { font-size: 9px; color: var(--text-faint); font-weight: 400;
                         letter-spacing: 0.2px; text-transform: none; }

    .agent-panel { border-left: 3px solid var(--accent-consumer); }
    .provider-panel { border-left: 3px solid var(--accent-provider); }
    .wire-panel { border-left: 3px solid var(--accent-wire); }
    .chain-panel { border-left: 3px solid var(--accent-chain); }

    .label { font-size: 9px; color: var(--text-faint); letter-spacing: 0.6px;
             text-transform: uppercase; margin: 10px 0 4px; }
  </style>
  """, unsafe_allow_html=True)

  # ── session_state init ─────────────────────────────────────────────────────
  UI_STATE_VERSION = 4
  if st.session_state.get("ui_state_version") != UI_STATE_VERSION:
      st.session_state.ui_state_version = UI_STATE_VERSION
      st.session_state.chat_history = []
      st.session_state.timeline = []           # phases for the A2A wire
      st.session_state.consumer_tool_log = []  # parsed [MCP] markers from /chat log, dedup'd
      st.session_state.provider_tool_log = []  # entries from provider /tool_log
      st.session_state.chain_events = []       # entries from consumer /chain_events
      st.session_state.probe_samples = []
      st.session_state.turn = 0
      st.session_state.running = False
      st.session_state.last_block_seen = 0
      st.session_state.last_provider_ts_seen = 0.0

  # ── sidebar ────────────────────────────────────────────────────────────────
  with st.sidebar:
      st.header("⚙️ Settings")
      selected_model = st.selectbox("Ollama model", MODELS, index=MODELS.index(DEFAULT_MODEL))
      st.caption(f"Pull with: `ollama pull {selected_model}`")
      st.divider()
      if st.button("🗑 Clear session"):
          try:
              with httpx.Client() as c:
                  c.delete(f"{CONSUMER_BASE_URL}/log")
          except Exception:
              pass
          for k in ("chat_history", "timeline", "consumer_tool_log",
                    "provider_tool_log", "chain_events", "probe_samples"):
              st.session_state[k] = []
          st.session_state.turn = 0
          st.session_state.last_block_seen = 0
          st.session_state.last_provider_ts_seen = time.time()
          st.rerun()

  # Body sections wired up in subsequent tasks.
  ```

- [ ] **Step 2: Manual verification**

  In one terminal: `make up` (starts the docker stack including the UI on `:8501`). Wait ~30 s.

  Open http://localhost:8501. Expected: blank dark page; sidebar shows model selector + "Clear session" button. No errors in `docker compose logs ui` or in the browser console.

- [ ] **Step 3: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "refactor(ui): scaffold for dashboard redesign — palette, sidebar, session_state"
  ```

---

## Task 5: Header + 6-stage pipeline strip

**Files:**
- Modify: `consumer/ui.py`

Add the title/subtitle/status pill at the top, and the 6-stage pipeline strip directly under it. Pipeline stage status comes from a helper that scans `st.session_state.consumer_tool_log` (which Task 6 starts populating; for this task the strip will all be `not yet fired`).

- [ ] **Step 1: Add the helpers and renderers**

  Append to `consumer/ui.py` (above the body sections marker):

  ```python
  STAGES = [
      ("01", "Discovery",     "🔍", "browse_catalog"),
      ("02", "Quote",         "💬", "request_quote"),
      ("03", "Payment Lock",  "🔒", "lock_payment"),
      ("04", "Atomic Swap",   "⚡", "await_settlement"),
      ("05", "Activation",    "🪪", "present_credential"),
      ("06", "Consumption",   "📡", "verify_bandwidth"),
  ]


  def _consumer_tool_fired(name: str) -> bool:
      return any(e["tool"] == name for e in st.session_state.consumer_tool_log)


  def _provider_tool_fired(name: str) -> bool:
      return any(e["tool"] == name for e in st.session_state.provider_tool_log)


  def _stage_status(trigger: str) -> str:
      # Stage 06 fires only if iperf was run; treat probe_samples as the trigger.
      if trigger == "verify_bandwidth":
          return "done" if st.session_state.probe_samples else "pending"
      if _consumer_tool_fired(trigger) or _provider_tool_fired(trigger):
          return "done"
      return "pending"


  def render_header() -> None:
      turn = st.session_state.turn
      if st.session_state.running:
          status = f"BUSY · turn {turn}"
          color = "#3b82f6"
          bg = "#1a2f4a"
      elif turn > 0:
          status = f"READY · turn {turn}"
          color = "#22c55e"
          bg = "#14291a"
      else:
          status = "IDLE"
          color = "#666"
          bg = "#15151f"

      st.markdown(
          f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
          f'padding-bottom:14px;border-bottom:1px solid var(--border);margin-bottom:14px;">'
          f'<div><div style="font-size:18px;font-weight:600;color:#f0f0f8;">'
          f'A2A Bandwidth Provisioning — autonomous agent demo</div>'
          f'<div style="font-size:11px;color:var(--text-dim);margin-top:3px;">'
          f'Orange Labs · MCP-driven consumer & provider · atomic on-chain swap · '
          f'SDN ({"mock" if SDN_MOCK else "real"})</div></div>'
          f'<div style="background:{bg};border:1px solid {color}55;color:{color};'
          f'font-size:10px;padding:4px 10px;border-radius:99px;font-weight:600;'
          f'letter-spacing:0.4px;">● {status}</div></div>',
          unsafe_allow_html=True,
      )


  def render_pipeline() -> None:
      tiles = []
      for num, label, icon, trigger in STAGES:
          status = _stage_status(trigger)
          if status == "done":
              border = "#22c55e88"; bg = "#14291a44"; lcolor = "#22c55e"
          else:
              border = "var(--border)"; bg = "#15151f"; lcolor = "#bbb"
          tiles.append(
              f'<div style="background:{bg};border:1px solid {border};border-radius:8px;'
              f'padding:10px 8px;text-align:center;">'
              f'<div style="font-size:9px;color:#555;letter-spacing:1px;">{num}</div>'
              f'<div style="font-size:18px;margin:4px 0;">{icon}</div>'
              f'<div style="font-size:10px;font-weight:500;color:{lcolor};">{label}</div></div>'
          )
      st.markdown(
          '<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px;'
          'margin-bottom:16px;">' + "".join(tiles) + "</div>",
          unsafe_allow_html=True,
      )


  # ── body ───────────────────────────────────────────────────────────────────
  render_header()
  render_pipeline()
  ```

- [ ] **Step 2: Manual verification**

  Reload the UI. Expected: Header with title + subtitle + grey `IDLE` pill; 6-stage strip with all stages grey/pending. No layout shift, no console errors.

- [ ] **Step 3: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "feat(ui): header with status pill + 6-stage pipeline strip"
  ```

---

## Task 6: Triptych — Consumer Agent panel (left)

**Files:**
- Modify: `consumer/ui.py`

The left column of the triptych. Renders Agent Card metadata (name, version, wallet, A2A endpoint, model) + skills chip + MCP-tools list with `not yet fired` / `fired this turn` / `fired previously` status.

This task also introduces the `_parse_tool_log_from_chat` helper that converts the consumer-side `/chat` response log into `consumer_tool_log` entries on each turn (this is needed before the panel can show any state).

- [ ] **Step 1: Add helpers**

  Add to `consumer/ui.py` above `render_header`:

  ```python
  CONSUMER_TOOLS = [
      ("browse_catalog",     "a2a",      False),
      ("request_quote",      "a2a",      False),
      ("lock_payment",       "on-chain", False),
      ("await_settlement",   "on-chain", False),
      ("present_credential", "a2a",      False),
      ("wallet_address",     "local",    True),   # ambient
      ("sign_message",       "local",    True),   # ambient
  ]

  PROVIDER_TOOLS = [
      ("get_catalog",                "read",     False),
      ("request_quote",              "read",     False),
      ("verify_credential_ownership","read",     False),
      ("mint_credential",            "on-chain", False),
      ("complete_swap",              "on-chain", False),
      ("allocate_bandwidth",         "sdn",      False),
      ("verify_bandwidth",           "sdn",      False),
      ("revoke_bandwidth",           "expiry",   True),  # ambient
  ]


  _MCP_RE = re.compile(r"\[MCP\]\s+(\w+)\(")


  def _parse_consumer_tools_from_log(log: list[dict], turn: int) -> list[dict]:
      """Extract [MCP] tool_name(...) markers from a /chat log and tag each
      with the turn it fired in. Used by ingest_chat_response."""
      out = []
      for entry in log:
          if entry.get("from") != "consumer":
              continue
          m = _MCP_RE.search(entry.get("message", ""))
          if m:
              out.append({"tool": m.group(1), "turn": turn})
      return out


  def _merge_tool_log(existing: list[dict], new_entries: list[dict]) -> list[dict]:
      """De-duplicate by (tool, turn). Older turns kept; newer turns append."""
      seen = {(e["tool"], e["turn"]) for e in existing}
      out = list(existing)
      for e in new_entries:
          key = (e["tool"], e["turn"])
          if key not in seen:
              out.append(e)
              seen.add(key)
      return out


  def _tool_status(tool_log: list[dict], tool_name: str, current_turn: int) -> str:
      """Return 'fired_this_turn' / 'fired_previously' / 'not_yet_fired'."""
      turns = [e["turn"] for e in tool_log if e["tool"] == tool_name]
      if not turns:
          return "not_yet_fired"
      if max(turns) >= current_turn:
          return "fired_this_turn"
      return "fired_previously"


  @st.cache_data(ttl=10)
  def _fetch_address(base_url: str) -> str | None:
      try:
          with httpx.Client(timeout=3.0) as c:
              r = c.get(f"{base_url}/address")
              r.raise_for_status()
              return r.json()["address"]
      except Exception:
          return None


  def _render_tool_row(name: str, tag: str, ambient: bool, status: str) -> str:
      if ambient:
          border = "1px dashed #2a2a3e"; nm_color = "#666"; tag_color = "#444"; mark = ""
      elif status == "fired_this_turn":
          border = "1px solid #3b82f6"; nm_color = "#93c5fd"; tag_color = "#3b82f6"; mark = " ✓"
      elif status == "fired_previously":
          border = "1px solid #22c55e44"; nm_color = "#7fc99a"; tag_color = "#22c55e88"; mark = " ✓"
      else:
          border = "1px solid #232333"; nm_color = "#bbb"; tag_color = "#666"; mark = ""
      return (
          f'<div style="display:flex;justify-content:space-between;align-items:center;'
          f'font-family:ui-monospace,monospace;font-size:10px;padding:4px 8px;'
          f'border-radius:5px;background:#15151f;border:{border};margin-bottom:3px;">'
          f'<span style="color:{nm_color};">{html_lib.escape(name)}{mark}</span>'
          f'<span style="font-size:8px;color:{tag_color};">{html_lib.escape(tag)}</span></div>'
      )


  def render_consumer_panel() -> None:
      addr = _fetch_address(CONSUMER_BASE_URL) or "—"
      addr_short = (addr[:6] + "…" + addr[-4:]) if addr != "—" else "—"
      turn = st.session_state.turn

      tool_rows = "".join(
          _render_tool_row(name, tag, ambient,
                           _tool_status(st.session_state.consumer_tool_log, name, turn))
          for name, tag, ambient in CONSUMER_TOOLS
      )

      st.markdown(f'''
        <div class="panel agent-panel">
          <div class="panel-title">
            <span>🛒 Consumer Agent</span>
            <span class="meta">v2.0.0</span>
          </div>
          <div style="font-size:13px;font-weight:600;color:#f0f0f8;">Bandwidth Consumer Agent</div>
          <div style="font-size:10px;color:var(--text-dim);line-height:1.4;margin:2px 0 10px;">
            Autonomously procures time-bound bandwidth from provider agents via atomic
            on-chain escrow + ERC-721 credential.
          </div>
          <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                      padding:3px 0;border-top:1px dashed var(--border);">
            <span style="color:#666;text-transform:uppercase;font-size:9px;">wallet</span>
            <span style="font-family:ui-monospace,monospace;">{addr_short}</span></div>
          <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                      padding:3px 0;border-top:1px dashed var(--border);">
            <span style="color:#666;text-transform:uppercase;font-size:9px;">A2A endpoint</span>
            <span>:8001/chat</span></div>
          <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                      padding:3px 0;border-top:1px dashed var(--border);">
            <span style="color:#666;text-transform:uppercase;font-size:9px;">model</span>
            <span>{html_lib.escape(selected_model)}</span></div>

          <div class="label">A2A Skills</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;">
            <span style="background:#1a1a2e;border:1px solid #818cf855;color:#cfd6ff;
                         font-size:10px;padding:2px 8px;border-radius:99px;">purchase_bandwidth</span>
          </div>

          <div class="label">MCP Tools</div>
          {tool_rows}
        </div>
      ''', unsafe_allow_html=True)
  ```

- [ ] **Step 2: Wire the panel into the page (placeholder triptych)**

  Append to the body section, after `render_pipeline()`:

  ```python
  col_l, col_c, col_r = st.columns([1, 1.2, 1])
  with col_l:
      render_consumer_panel()
  with col_c:
      st.markdown('<div class="panel wire-panel"><div class="panel-title">A2A Wire</div>'
                  '<div style="color:var(--text-faint);font-size:11px;">— wired in next task —</div></div>',
                  unsafe_allow_html=True)
  with col_r:
      st.markdown('<div class="panel provider-panel"><div class="panel-title">Provider Agent</div>'
                  '<div style="color:var(--text-faint);font-size:11px;">— wired in next task —</div></div>',
                  unsafe_allow_html=True)
  ```

- [ ] **Step 3: Manual verification**

  Reload the UI. Expected: triptych with the consumer panel populated (Bandwidth Consumer Agent, wallet `0x…`, the skill chip, all 7 MCP tools listed — 5 grey "not yet fired" + 2 with dotted border for ambient). The middle and right columns show placeholder text. Wallet should resolve to a real address (consumer is up).

- [ ] **Step 4: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "feat(ui): consumer agent panel — card, skills, MCP tools with turn-status"
  ```

---

## Task 7: Triptych — A2A wire (center)

**Files:**
- Modify: `consumer/ui.py`

Replace the center placeholder with the A2A wire view: consumer-aligned-left bubbles, provider-aligned-right bubbles, on-chain markers as full-width arrow rows, all derived from `st.session_state.timeline` (already populated by the existing parser, kept from Task 8 ingest).

This task also introduces the `ingest_chat_response` helper that runs once per turn after `/chat` returns to populate `timeline`, `consumer_tool_log`, and (in the next task) `chain_events` + `provider_tool_log`. We wire chat input here too because without it, `timeline` stays empty.

- [ ] **Step 1: Add timeline parser + ingest + chat helpers**

  Add to `consumer/ui.py` (above `render_header`):

  ```python
  def _parse_timeline(log: list[dict], turn: int) -> list[dict]:
      """Convert /chat log entries into A2A wire bubbles + on-chain markers.

      Returns a list of {kind, sender, text, turn} where:
        kind = 'bubble' or 'chain'
        sender = 'consumer' or 'provider' (only meaningful for bubbles)
      """
      out: list[dict] = []
      for e in log:
          sender = e.get("from", "")
          msg = e.get("message", "")
          if not sender or not msg:
              continue
          if msg.startswith("requestAgreement()"):
              out.append({"kind": "chain", "text": "⛓ requestAgreement on chain", "turn": turn})
          elif "Agreement ACTIVE" in msg:
              out.append({"kind": "chain", "text": f"⛓ {msg}", "turn": turn})
          elif sender in ("consumer", "provider"):
              out.append({"kind": "bubble", "sender": sender, "text": msg, "turn": turn})
      return out


  def _merge_timeline(existing: list[dict], new_items: list[dict]) -> list[dict]:
      seen = {(i["kind"], i.get("sender", ""), i["text"], i["turn"]) for i in existing}
      out = list(existing)
      for i in new_items:
          key = (i["kind"], i.get("sender", ""), i["text"], i["turn"])
          if key not in seen:
              out.append(i)
              seen.add(key)
      return out


  def render_wire_panel() -> None:
      bubbles_html = []
      for item in st.session_state.timeline:
          if item["kind"] == "chain":
              bubbles_html.append(
                  f'<div style="text-align:center;color:#f59e0b;font-size:10px;'
                  f'padding:6px 0;letter-spacing:0.3px;">{html_lib.escape(item["text"])}</div>'
              )
              continue
          sender = item["sender"]
          text = html_lib.escape(item["text"])
          if sender == "consumer":
              bubbles_html.append(
                  f'<div style="align-self:flex-start;background:#1a1a2e;'
                  f'border:1px solid #2a2a4e;border-left:3px solid #818cf8;'
                  f'border-radius:8px;padding:6px 9px;font-size:10px;color:#d4d8ff;'
                  f'max-width:88%;font-family:ui-monospace,monospace;line-height:1.4;'
                  f'word-break:break-word;">'
                  f'<div style="font-size:8px;letter-spacing:0.4px;text-transform:uppercase;'
                  f'opacity:0.7;margin-bottom:2px;">consumer →</div>{text}</div>'
              )
          else:
              bubbles_html.append(
                  f'<div style="align-self:flex-end;background:#1a2535;'
                  f'border:1px solid #2a3545;border-right:3px solid #60a5fa;'
                  f'border-radius:8px;padding:6px 9px;font-size:10px;color:#d4e4ff;'
                  f'max-width:88%;font-family:ui-monospace,monospace;line-height:1.4;'
                  f'text-align:right;word-break:break-word;">'
                  f'<div style="font-size:8px;letter-spacing:0.4px;text-transform:uppercase;'
                  f'opacity:0.7;margin-bottom:2px;">← provider</div>{text}</div>'
              )

      bubbles_count = sum(1 for i in st.session_state.timeline if i["kind"] == "bubble")
      body = ("".join(bubbles_html)
              if st.session_state.timeline
              else '<div style="color:var(--text-faint);font-size:11px;">No agent-to-agent traffic yet — type intent into the chat below.</div>')

      st.markdown(f'''
        <div class="panel wire-panel">
          <div class="panel-title">
            <span>↔ Agent-to-Agent Wire</span>
            <span class="meta">JSON-RPC over HTTP · {bubbles_count} msgs</span>
          </div>
          <div style="display:flex;flex-direction:column;gap:6px;max-height:520px;overflow-y:auto;">
            {body}
          </div>
        </div>
      ''', unsafe_allow_html=True)


  def ingest_chat_response(turn: int, log: list[dict]) -> None:
      """Merge a /chat response log into all cumulative session_state buckets."""
      st.session_state.timeline = _merge_timeline(
          st.session_state.timeline, _parse_timeline(log, turn)
      )
      st.session_state.consumer_tool_log = _merge_tool_log(
          st.session_state.consumer_tool_log,
          _parse_consumer_tools_from_log(log, turn),
      )
  ```

- [ ] **Step 2: Replace center placeholder + add chat-input handling at the bottom**

  Find the triptych block from Task 6 (`with col_c: st.markdown('<div class="panel wire-panel">...`) and replace it with `render_wire_panel()`. Then append at the bottom of the file:

  ```python
  user_input = st.chat_input("Ask the consumer agent…")
  if user_input:
      st.session_state.turn += 1
      st.session_state.running = True
      st.session_state.chat_history.append({"role": "user", "content": user_input})
      try:
          with httpx.Client(timeout=300.0) as c:
              r = c.post(f"{CONSUMER_BASE_URL}/chat",
                         json={"message": user_input, "model": selected_model})
              r.raise_for_status()
              data = r.json()
      except Exception as e:
          data = {"response": f"Error: {e}", "log": [], "thinking": []}

      ingest_chat_response(st.session_state.turn, data.get("log", []))
      st.session_state.chat_history.append({
          "role": "assistant",
          "content": data.get("response", ""),
          "thinking": data.get("thinking", []),
      })
      st.session_state.running = False
      st.rerun()
  ```

- [ ] **Step 3: Manual verification**

  Reload the UI. Type "I need 5 Mbps for 10 minutes" into the chat input. Wait ~30-60 s for the LLM + chain. Expected: A2A wire fills with consumer bubbles on the left + provider bubbles on the right, with on-chain marker rows interleaved. Pipeline stages 01–05 turn green. Consumer panel shows the 5 non-ambient MCP tools with blue "fired this turn" border.

- [ ] **Step 4: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "feat(ui): A2A wire panel + chat input + cumulative ingest"
  ```

---

## Task 8: Triptych — Provider Agent panel (right)

**Files:**
- Modify: `consumer/ui.py`

Mirror of the consumer panel. Pulls live wallet from `provider:8002/address` (already exists). Pulls live MCP-tool fired status from `provider:8002/tool_log` (Task 2). Polled once per turn from inside `ingest_chat_response`.

- [ ] **Step 1: Extend `ingest_chat_response` with provider tool-log fetch**

  Replace the existing `ingest_chat_response` with:

  ```python
  def ingest_chat_response(turn: int, log: list[dict]) -> None:
      """Merge a /chat response log into all cumulative session_state buckets,
      and poll provider /tool_log for the same turn (uses last_provider_ts_seen
      as a watermark so we don't re-count entries from prior turns or runs)."""
      st.session_state.timeline = _merge_timeline(
          st.session_state.timeline, _parse_timeline(log, turn)
      )
      st.session_state.consumer_tool_log = _merge_tool_log(
          st.session_state.consumer_tool_log,
          _parse_consumer_tools_from_log(log, turn),
      )

      since = st.session_state.last_provider_ts_seen
      try:
          with httpx.Client(timeout=5.0) as c:
              r = c.get(f"{PROVIDER_BASE_URL}/tool_log",
                        params={"since_ts": since})
              r.raise_for_status()
              entries = [e for e in r.json() if e.get("status") == "ok"]
      except Exception:
          entries = []
      st.session_state.provider_tool_log = _merge_tool_log(
          st.session_state.provider_tool_log,
          [{"tool": e["tool"], "turn": turn} for e in entries],
      )
      if entries:
          st.session_state.last_provider_ts_seen = max(e["ts"] for e in entries)
  ```

- [ ] **Step 2: Add `render_provider_panel`**

  Add (next to `render_consumer_panel`):

  ```python
  def render_provider_panel() -> None:
      addr = _fetch_address(PROVIDER_BASE_URL) or "—"
      addr_short = (addr[:6] + "…" + addr[-4:]) if addr != "—" else "—"
      turn = st.session_state.turn

      tool_rows = "".join(
          _render_tool_row(name, tag, ambient,
                           _tool_status(st.session_state.provider_tool_log, name, turn))
          for name, tag, ambient in PROVIDER_TOOLS
      )

      skills_html = "".join(
          f'<span style="background:#1a2535;border:1px solid #60a5fa55;color:#d4e4ff;'
          f'font-size:10px;padding:2px 8px;border-radius:99px;">{s}</span>'
          for s in ("get_catalog", "request_quote", "activate")
      )

      st.markdown(f'''
        <div class="panel provider-panel">
          <div class="panel-title">
            <span>🏪 Provider Agent</span>
            <span class="meta">v2.0.0</span>
          </div>
          <div style="font-size:13px;font-weight:600;color:#f0f0f8;">Bandwidth Provider Agent</div>
          <div style="font-size:10px;color:var(--text-dim);line-height:1.4;margin:2px 0 10px;">
            Sells time-bound bandwidth via atomic on-chain escrow + ERC-721 credential.
            Activates SDN policy on credential presentation.
          </div>
          <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                      padding:3px 0;border-top:1px dashed var(--border);">
            <span style="color:#666;text-transform:uppercase;font-size:9px;">wallet</span>
            <span style="font-family:ui-monospace,monospace;">{addr_short}</span></div>
          <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                      padding:3px 0;border-top:1px dashed var(--border);">
            <span style="color:#666;text-transform:uppercase;font-size:9px;">A2A endpoint</span>
            <span>:8002/a2a</span></div>
          <div style="font-size:10px;color:#aaa;display:flex;justify-content:space-between;
                      padding:3px 0;border-top:1px dashed var(--border);">
            <span style="color:#666;text-transform:uppercase;font-size:9px;">SDN</span>
            <span>{"mock" if SDN_MOCK else "real"}</span></div>

          <div class="label">A2A Skills</div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;">{skills_html}</div>

          <div class="label">MCP Tools</div>
          {tool_rows}
        </div>
      ''', unsafe_allow_html=True)
  ```

- [ ] **Step 3: Wire the right column**

  Find the triptych `with col_r:` block and replace its body with `render_provider_panel()`.

- [ ] **Step 4: Manual verification**

  Reload UI, run chat "I need 5 Mbps for 10 minutes", wait. Expected: provider panel shows real wallet address, three skill chips, and the 8 MCP tools — 6 with blue "fired this turn" border (`get_catalog`, `request_quote`, `verify_credential_ownership`, `mint_credential`, `complete_swap`, `allocate_bandwidth`), `verify_bandwidth` grey, `revoke_bandwidth` dotted (ambient).

- [ ] **Step 5: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "feat(ui): provider agent panel — card, skills, MCP tools polled from /tool_log"
  ```

---

## Task 9: Bottom row — Chat panel (left)

**Files:**
- Modify: `consumer/ui.py`

The chat panel that re-uses the chat input we already added in Task 7. It also displays the running chat history and an expander for the agent's "thinking" trace per turn.

- [ ] **Step 1: Add `render_chat_panel`**

  Add next to other render functions:

  ```python
  def render_chat_panel() -> None:
      st.markdown('<div class="panel agent-panel"><div class="panel-title">'
                  '<span>👤 Human → Consumer</span>'
                  '<span class="meta">intent · reasoning trace</span></div>',
                  unsafe_allow_html=True)
      for msg in st.session_state.chat_history:
          with st.chat_message(msg["role"]):
              st.write(msg["content"])
              if msg.get("thinking"):
                  with st.expander("Thinking", expanded=False):
                      for t in msg["thinking"]:
                          st.write(t)
      st.markdown('</div>', unsafe_allow_html=True)
  ```

- [ ] **Step 2: Wire it under the triptych**

  After the triptych block (and before the chat-input handling at the bottom), insert:

  ```python
  bottom_l, bottom_r = st.columns([1, 1])
  with bottom_l:
      render_chat_panel()
  with bottom_r:
      st.markdown('<div class="panel chain-panel"><div class="panel-title">'
                  '<span>⛓ On-chain Events</span>'
                  '<span class="meta">— wired in next task —</span></div>'
                  '</div>', unsafe_allow_html=True)
  ```

  Note: the `st.chat_input(...)` at the very bottom of the file stays where it is — Streamlit's chat_input always docks at the page bottom regardless of where in the script it's called.

- [ ] **Step 3: Manual verification**

  Reload UI. Expected: chat panel under the consumer column shows the running history (user message + agent reply, with a "Thinking" expander). Sending a new message still works.

- [ ] **Step 4: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "feat(ui): chat panel with running history + thinking expander"
  ```

---

## Task 10: Bottom row — On-chain Events panel (right)

**Files:**
- Modify: `consumer/ui.py`

Replaces the right-side placeholder with the on-chain panel. Polls `consumer:8001/chain_events` (Task 3) once per turn, merges into `st.session_state.chain_events`.

- [ ] **Step 1: Extend `ingest_chat_response` to poll chain events**

  Replace the existing `ingest_chat_response` with:

  ```python
  def ingest_chat_response(turn: int, log: list[dict]) -> None:
      """Merge /chat log + poll provider /tool_log + poll consumer
      /chain_events. Uses last_provider_ts_seen and last_block_seen as
      watermarks so prior-turn entries aren't re-counted."""
      st.session_state.timeline = _merge_timeline(
          st.session_state.timeline, _parse_timeline(log, turn)
      )
      st.session_state.consumer_tool_log = _merge_tool_log(
          st.session_state.consumer_tool_log,
          _parse_consumer_tools_from_log(log, turn),
      )

      since_ts = st.session_state.last_provider_ts_seen
      try:
          with httpx.Client(timeout=5.0) as c:
              r = c.get(f"{PROVIDER_BASE_URL}/tool_log",
                        params={"since_ts": since_ts})
              r.raise_for_status()
              entries = [e for e in r.json() if e.get("status") == "ok"]
      except Exception:
          entries = []
      st.session_state.provider_tool_log = _merge_tool_log(
          st.session_state.provider_tool_log,
          [{"tool": e["tool"], "turn": turn} for e in entries],
      )
      if entries:
          st.session_state.last_provider_ts_seen = max(e["ts"] for e in entries)

      since_block = st.session_state.last_block_seen
      try:
          with httpx.Client(timeout=5.0) as c:
              r = c.get(f"{CONSUMER_BASE_URL}/chain_events",
                        params={"since_block": since_block})
              r.raise_for_status()
              new_events = r.json()
      except Exception:
          new_events = []
      if new_events:
          st.session_state.chain_events.extend(new_events)
          st.session_state.last_block_seen = max(e["block"] for e in new_events)
  ```

- [ ] **Step 2: Add `render_chain_panel`**

  ```python
  def render_chain_panel() -> None:
      events = st.session_state.chain_events
      if not events:
          rows_html = ('<div style="color:var(--text-faint);font-size:11px;'
                       'padding:6px 0;">No on-chain events yet.</div>')
      else:
          rows = []
          for e in events:
              args_str = ", ".join(f"{k}={v}" for k, v in (e.get("args") or {}).items())
              if len(args_str) > 60:
                  args_str = args_str[:57] + "..."
              rows.append(
                  f'<div style="font-family:ui-monospace,monospace;font-size:10px;'
                  f'color:#bbb;padding:5px 8px;border-bottom:1px solid var(--border-soft);">'
                  f'<span style="color:#f59e0b;">{html_lib.escape(e["event"])}</span> '
                  f'<span style="color:#888;">{html_lib.escape(args_str)}</span>'
                  f'<span style="color:#666;float:right;">block {e["block"]} · gas {e["gas"]:,}</span>'
                  f'</div>'
              )
          rows_html = "".join(rows)

      st.markdown(f'''
        <div class="panel chain-panel">
          <div class="panel-title">
            <span>⛓ On-chain Events</span>
            <span class="meta">Anvil · {len(events)} events</span>
          </div>
          {rows_html}
        </div>
      ''', unsafe_allow_html=True)
  ```

- [ ] **Step 3: Wire it into the right bottom column**

  Find the `with bottom_r:` block from Task 9 and replace its body with `render_chain_panel()`.

- [ ] **Step 4: Manual verification**

  Clear the session, run chat once. Expected: at least three rows appear: `AgreementRequested`, `Transfer`, `Deposit`, each with block number and gas. Run a second turn — events from the first turn should still be there (cumulative).

- [ ] **Step 5: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "feat(ui): on-chain events panel polled from /chain_events"
  ```

---

## Task 11: NFT/SDN credential strip + iperf expander + sidebar cleanup

**Files:**
- Modify: `consumer/ui.py`

Final task. Adds the full-width NFT/SDN strip below the bottom row (auto-fetches `/check_token` once a token id is known from the timeline) and the iperf expander at the very bottom. Also removes the "Gateway Check" block from the sidebar (its functions move into this strip).

- [ ] **Step 1: Add `_active_token_id` + `render_nft_strip` + `render_iperf_expander`**

  Add:

  ```python
  def _active_token_id() -> int | None:
      """Find the most recent tokenId mentioned in the timeline."""
      for item in reversed(st.session_state.timeline):
          if item["kind"] == "chain" and "tokenId=" in item["text"]:
              m = re.search(r"tokenId=(\d+)", item["text"])
              if m:
                  return int(m.group(1))
      return None


  def render_nft_strip() -> None:
      tid = _active_token_id()
      if tid is None:
          st.markdown(
              '<div style="background:#0f1410;border:1px solid #22c55e22;border-radius:8px;'
              'padding:10px 14px;font-size:11px;color:var(--text-faint);margin-bottom:12px;">'
              '🪪 NFT credential — no active credential yet</div>',
              unsafe_allow_html=True,
          )
          return

      try:
          with httpx.Client(timeout=5.0) as c:
              r = c.get(f"{CONSUMER_BASE_URL}/check_token", params={"tokenId": tid})
              r.raise_for_status()
              data = r.json()
      except Exception as e:
          st.markdown(
              f'<div style="color:#f87171;font-size:11px;">NFT lookup failed: {html_lib.escape(str(e))}</div>',
              unsafe_allow_html=True,
          )
          return

      owner_short = data["owner"][:6] + "…" + data["owner"][-4:]
      sdn_rule = f"policer {data['bandwidth_mbps']} Mbps · {data['endpoint'].replace('clab://', '')}"
      st.markdown(f'''
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;
                    padding:10px 14px;background:#0f1410;border:1px solid #22c55e55;
                    border-radius:8px;font-size:10px;margin-bottom:12px;">
          <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                          margin-bottom:3px;">Token ID</div>
               <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{tid}</div></div>
          <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                          margin-bottom:3px;">Owner</div>
               <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{owner_short}</div></div>
          <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                          margin-bottom:3px;">Status</div>
               <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{html_lib.escape(data["status"])} · {data["seconds_remaining"]}s</div></div>
          <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                          margin-bottom:3px;">SDN Rule</div>
               <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">{html_lib.escape(sdn_rule)}</div></div>
          <div><div style="font-size:9px;color:#666;text-transform:uppercase;letter-spacing:0.4px;
                          margin-bottom:3px;">QoS</div>
               <div style="color:#a7e8c4;font-family:ui-monospace,monospace;">guaranteed</div></div>
        </div>
      ''', unsafe_allow_html=True)


  def render_iperf_expander() -> None:
      tid = _active_token_id()
      with st.expander("📡 Bandwidth probe (iperf3)", expanded=False):
          if tid is None:
              st.caption("No active credential.")
              return
          if st.button("Run iperf3 probe"):
              try:
                  with httpx.Client(timeout=30.0) as c:
                      r = c.post(f"{CONSUMER_BASE_URL}/probe_proxy", json={"tokenId": tid})
                      r.raise_for_status()
                      st.session_state.probe_samples.append(r.json())
                      st.rerun()
              except Exception as e:
                  st.error(f"Probe failed: {e}")
          if st.session_state.probe_samples:
              chart_data = {
                  "measured_mbps": [s["measured_mbps"] for s in st.session_state.probe_samples],
                  "expected_mbps": [s["expected_mbps"] for s in st.session_state.probe_samples],
              }
              st.line_chart(chart_data, height=200)
              last = st.session_state.probe_samples[-1]
              st.caption(
                  f"last: {last['src_ce']} → {last['dst_ce']} "
                  f"{last['measured_mbps']:.2f} / {last['expected_mbps']:.1f} Mbps"
              )
  ```

- [ ] **Step 2: Wire them under the bottom row**

  After the `bottom_l, bottom_r = st.columns([1,1])` block, append:

  ```python
  render_nft_strip()
  render_iperf_expander()
  ```

- [ ] **Step 3: Final cleanup pass**

  Open the file. Remove any leftover stub markup or stale comments from earlier tasks. Confirm the final body section reads, in order:

  1. `render_header()`
  2. `render_pipeline()`
  3. triptych — `render_consumer_panel()` ‖ `render_wire_panel()` ‖ `render_provider_panel()`
  4. bottom row — `render_chat_panel()` ‖ `render_chain_panel()`
  5. `render_nft_strip()`
  6. `render_iperf_expander()`
  7. `st.chat_input(...)` block at the very bottom

- [ ] **Step 4: End-to-end manual verification (acceptance criteria)**

  `make down-clean && make up`. Wait ~30 s. Open http://localhost:8501. Type "I need 5 Mbps for 10 minutes". Wait for the spinner to finish. Take a screenshot and confirm:

  1. Both agent cards (name, version, wallet, A2A endpoint) populated.
  2. Consumer-side MCP tools `browse_catalog`, `request_quote`, `lock_payment`, `await_settlement`, `present_credential` show the blue "fired this turn" border. `wallet_address` and `sign_message` are dotted/ambient.
  3. Provider-side MCP tools `get_catalog`, `request_quote`, `verify_credential_ownership`, `mint_credential`, `complete_swap`, `allocate_bandwidth` show blue "fired this turn". `verify_bandwidth` grey; `revoke_bandwidth` dotted.
  4. A2A wire shows ≥ 6 bubbles alternating left/right + on-chain marker rows.
  5. On-chain panel shows `AgreementRequested`, `Transfer`, `Deposit` with block + gas.
  6. NFT/SDN strip populated: token id, owner, status `ACTIVE`, SDN rule, QoS.
  7. Pipeline strip: stages 01–05 green; stage 06 only goes green after expanding the iperf section and clicking "Run iperf3 probe".

- [ ] **Step 5: Commit**

  ```bash
  git add consumer/ui.py
  git commit -m "feat(ui): NFT/SDN credential strip + iperf expander; finalize redesign"
  ```

---

## Self-review: spec coverage

- §1 Header → Task 5 ✓
- §2 Pipeline strip (6 stages) → Task 5 ✓
- §3a Consumer Agent panel → Task 6 ✓
- §3b A2A wire → Task 7 ✓
- §3c Provider Agent panel → Task 8 ✓
- §4 Human → Consumer chat panel → Task 9 (chat input added in Task 7) ✓
- §5 On-chain Events panel → Task 10 + endpoint Task 3 ✓
- §6 NFT/SDN strip → Task 11 ✓
- §7 iperf probe expander → Task 11 ✓
- Provider tool-call log infra → Tasks 1, 2 ✓
- Cumulative client-side state → Tasks 4, 7, 8, 10 (all session_state buckets initialized in Task 4 scaffold; populated incrementally) ✓
- Sidebar shrink (model selector + Clear session only) → Task 4 ✓
- Color palette → Task 4 ✓

Spec requirement "ambient" tools rendered with dotted border → covered in `_render_tool_row` (Task 6). Spec requirement that consumer tool log accumulates from the existing `[MCP] tool_name(...)` markers → `_parse_consumer_tools_from_log` (Task 6). All spec requirements have a task.
