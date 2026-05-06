# Pedagogical Notebooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 5 terse notebooks with a 21-notebook concept-first pedagogical series backed by a shared rendering helper module.

**Architecture:** A single `notebooks/_viz.py` module owns every visual (mermaid via mermaid.ink, MCP tool inspector, agent-card cards, state diffs, chat bubbles, chain status pills, event timeline, network topology, before/after toggle). Each notebook imports the helpers and stays short. Concept notebooks are mostly markdown; walkthrough notebooks drive the helpers with live data. The chain layer earns 4 notebooks; LangGraph and network earn 4; MCP and A2A earn 3; overview, inventory, and end-to-end are 1 each.

**Tech Stack:** Python 3.13, `uv`, `jupyterlab`, `ipywidgets>=8`, `langgraph`, `fastmcp`, `a2a-sdk`, `web3`, `eth-account`. Mermaid rendered via HTTP to `mermaid.ink` (matches LangGraph's own approach) with offline fallback to fenced markdown.

**Working branch:** `feat/pedagogical-notebooks` (already exists, contains the spec).

**Spec:** `docs/superpowers/specs/2026-05-06-pedagogical-notebooks-design.md`.

---

## File Structure

**Created:**
```
notebooks/_viz.py                  Shared renderers (single source of truth)
notebooks/__init__.py              Empty marker so _viz can be imported
tests/test_viz.py                  Smoke test: every renderer runs on a fixture
notebooks/00_overview.ipynb
notebooks/01a_chain_contract_model.ipynb
notebooks/01b_chain_escrow_lifecycle.ipynb
notebooks/01c_chain_nft_minting.ipynb
notebooks/01d_chain_walkthrough.ipynb
notebooks/02a_mcp_concepts.ipynb
notebooks/02b_mcp_tool_catalog.ipynb
notebooks/02c_mcp_walkthrough.ipynb
notebooks/03a_a2a_concepts.ipynb
notebooks/03b_a2a_agent_cards.ipynb
notebooks/03c_a2a_walkthrough.ipynb
notebooks/04a_graph_state_schema.ipynb
notebooks/04b_graph_topology.ipynb
notebooks/04c_graph_llm_prompts.ipynb
notebooks/04d_graph_walkthrough.ipynb
notebooks/05a_inventory_and_expiry.ipynb
notebooks/06_end_to_end.ipynb
notebooks/07a_network_concepts.ipynb
notebooks/07b_network_topology.ipynb
notebooks/07c_network_before_after.ipynb
notebooks/07d_network_router_config.ipynb
```

**Deleted:**
```
notebooks/01_chain.ipynb
notebooks/02_mcp.ipynb
notebooks/03_a2a.ipynb
notebooks/04_consumer_graph.ipynb
notebooks/05_end_to_end.ipynb
```

**Modified:**
```
notebooks/README.md                Rewrite to point at the new 21-notebook series
pyproject.toml                     Add ipywidgets>=8 to [dependency-groups] dev
```

---

## Conventions

Every notebook starts with the same boilerplate cell:

```python
import sys, pathlib
_ROOT = pathlib.Path.cwd().resolve()
if (_ROOT / 'shared').is_dir():
    sys.path.insert(0, str(_ROOT))
elif (_ROOT.parent / 'shared').is_dir():
    sys.path.insert(0, str(_ROOT.parent))

from notebooks._viz import (
    render_mermaid, render_agent_card, render_mcp_tools,
    render_state, render_chat_log, render_chain_status,
    render_event_timeline, render_topology, toggle_before_after,
)
```

Three reusable account constants (already in `tests/conftest.py`, copy verbatim):

```python
DEPLOYER = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'
```

Cell type convention: `# %% [markdown]` and `# %%` style isn't used — these are real `.ipynb` files. Tasks below give the cell sequence; build via `nbformat.v4.new_notebook()` + `new_markdown_cell` / `new_code_cell`.

Test the notebook builds compile by running:
```bash
uv run python -c "import nbformat; nbformat.read('notebooks/<file>.ipynb', as_version=4); print('ok')"
```

Test full notebook execution (where applicable) via `nbclient`:
```bash
uv run jupyter execute notebooks/<file>.ipynb --kernel_name=python3
```

---

## Phase 1: Helper module foundation

This phase ships nothing user-visible but unblocks every notebook. Strict TDD.

### Task 1: Create the notebooks package

**Files:**
- Create: `notebooks/__init__.py`

- [ ] **Step 1: Create empty package marker**

```bash
touch notebooks/__init__.py
```

- [ ] **Step 2: Verify Python sees it**

Run: `uv run python -c "import notebooks; print(notebooks.__file__)"`
Expected: prints the path; no ImportError.

- [ ] **Step 3: Commit**

```bash
git add notebooks/__init__.py
git commit -m "chore(notebooks): make notebooks/ a package for shared helpers"
git push
```

### Task 2: Add ipywidgets dev dep

**Files:**
- Modify: `pyproject.toml` (the `[dependency-groups] dev` block)

- [ ] **Step 1: Add ipywidgets via uv**

Run: `uv add --dev "ipywidgets>=8"`
Expected: `pyproject.toml` and `uv.lock` updated; `ipywidgets` installed in `.venv/`.

- [ ] **Step 2: Verify import**

Run: `uv run python -c "import ipywidgets; print(ipywidgets.__version__)"`
Expected: prints 8.x.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add ipywidgets>=8 for notebook before/after toggle"
git push
```

### Task 3: Smoke test scaffold for _viz (failing)

**Files:**
- Create: `tests/test_viz.py`

- [ ] **Step 1: Write the failing test**

```python
"""Smoke test for notebooks/_viz.py renderers.

We do not assert on rendered HTML/PNG content — just that every helper
returns the expected IPython.display type without raising.
"""
from __future__ import annotations

import pytest
from IPython.display import HTML, Image


def test_viz_module_imports():
    from notebooks import _viz
    expected = {
        "render_mermaid", "render_agent_card", "render_mcp_tools",
        "render_state", "render_chat_log", "render_chain_status",
        "render_event_timeline", "render_topology", "toggle_before_after",
    }
    missing = expected - set(dir(_viz))
    assert not missing, f"missing helpers: {missing}"


def test_render_mermaid_returns_image_or_html():
    from notebooks._viz import render_mermaid
    out = render_mermaid("graph LR; A-->B")
    assert isinstance(out, (Image, HTML))


def test_render_agent_card_returns_html():
    from notebooks._viz import render_agent_card
    card = {
        "name": "X", "version": "1.0", "description": "d",
        "capabilities": {"streaming": False},
        "supported_interfaces": [{"protocol_binding": "JSONRPC", "url": "/a2a"}],
        "skills": [{"id": "s", "name": "S", "description": "ds", "tags": []}],
    }
    out = render_agent_card(card)
    assert isinstance(out, HTML)
    assert "X" in out.data


def test_render_state_returns_html_with_diff():
    from notebooks._viz import render_state
    prev = {"a": 1, "b": 2}
    cur = {"a": 1, "b": 3, "c": 4}
    out = render_state(cur, prev)
    assert isinstance(out, HTML)
    # added + changed keys are surfaced
    assert "c" in out.data
    assert "b" in out.data


def test_render_chat_log_returns_html():
    from notebooks._viz import render_chat_log
    log = [{"from": "consumer", "message": "hi"},
           {"from": "provider", "message": "hello"}]
    out = render_chat_log(log)
    assert isinstance(out, HTML)
    assert "hi" in out.data and "hello" in out.data


def test_render_chain_status_handles_status_dict():
    from notebooks._viz import render_chain_status_from_dict
    ag = {"consumer": "0xC", "provider": "0xP", "bandwidthMbps": 5,
          "durationSeconds": 600, "priceWei": 10**16, "tokenId": 0,
          "status": "REQUESTED"}
    out = render_chain_status_from_dict(123, ag)
    assert isinstance(out, HTML)
    assert "REQUESTED" in out.data


def test_render_event_timeline_returns_html():
    from notebooks._viz import render_event_timeline
    events = [{"event": "AgreementRequested", "block": 1, "args": {"id": 1},
               "txHash": "0xabc", "gas": 90000}]
    out = render_event_timeline(events)
    assert isinstance(out, HTML)
    assert "AgreementRequested" in out.data


def test_render_topology_returns_image_or_html():
    from notebooks._viz import render_topology_from_rows
    rows = [
        {"tier": "small", "mbps": 2, "slots": [
            {"pe": "pe1", "subinterface": "ethernet-1/2.0",
             "ce": "ce1", "agreementId": None}]},
    ]
    out = render_topology_from_rows(rows, active_agreement_ids=set(),
                                    ce_peer={"ce1": "ce2"})
    assert isinstance(out, (Image, HTML))


def test_toggle_before_after_returns_widget_or_html():
    from notebooks._viz import toggle_before_after
    a = HTML("<div>A</div>")
    b = HTML("<div>B</div>")
    out = toggle_before_after(a, b)
    # ipywidgets.VBox or HTML fallback
    assert out is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_viz.py -v`
Expected: collection or import errors — `notebooks._viz` does not exist yet.

- [ ] **Step 3: Commit**

```bash
git add tests/test_viz.py
git commit -m "test(viz): smoke test for the notebook renderer helpers"
git push
```

### Task 4: Implement render_mermaid

**Files:**
- Create: `notebooks/_viz.py`

- [ ] **Step 1: Implement render_mermaid + a stub for the rest**

```python
"""Notebook rendering helpers.

Single source of truth for mermaid diagrams, MCP-tool inspectors,
A2A agent-card views, JSON state diffs, chat-bubble logs, on-chain
state pills, event timelines, network-topology graphs, and the
before/after ipywidgets toggle. Imported by every notebook in the
pedagogical series.

Mermaid rendering uses the mermaid.ink HTTP service (the same approach
LangGraph uses internally for draw_mermaid_png). Offline behavior:
fall back to a fenced markdown block so notebooks remain readable.
"""
from __future__ import annotations

import base64
import html as _html
import io
import json
from typing import Any, Iterable

import httpx
from IPython.display import HTML, Image


def render_mermaid(source: str) -> HTML | Image:
    """Render mermaid source as a PNG via mermaid.ink, or fenced text on failure."""
    try:
        encoded = base64.urlsafe_b64encode(source.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/img/{encoded}"
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        return Image(data=resp.content, format="png")
    except Exception:
        # offline or rate-limited fallback
        escaped = _html.escape(source)
        return HTML(f"<pre style='background:#f6f8fa;padding:8px;"
                    f"border-radius:6px'><code>{escaped}</code></pre>")
```

(The other helpers are added in Tasks 5–12. For now `render_mermaid` is the only real one. Keep imports tight — add `httpx`, `base64`, `html as _html` here.)

- [ ] **Step 2: Run mermaid test only**

Run: `uv run pytest tests/test_viz.py::test_render_mermaid_returns_image_or_html -v`
Expected: PASS (network-permitting; the fallback path is also acceptable since the test only checks the return type).

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_mermaid via mermaid.ink with offline fallback"
git push
```

### Task 5: Implement render_agent_card

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append render_agent_card**

```python
def render_agent_card(card: dict) -> HTML:
    """Render an a2a-sdk AgentCard (as dict) as a styled HTML card.

    `card` is the result of MessageToDict(agent_card, preserving_proto_field_name=True)
    or the JSON returned by /.well-known/agent-card.json.
    """
    name = _html.escape(str(card.get("name", "?")))
    version = _html.escape(str(card.get("version", "?")))
    desc = _html.escape(str(card.get("description", "")))
    caps = card.get("capabilities", {}) or {}
    caps_html = " ".join(
        f"<span style='background:#eef;padding:2px 8px;border-radius:10px;"
        f"margin-right:4px;font-size:12px'>{_html.escape(k)}: "
        f"{_html.escape(str(v))}</span>"
        for k, v in caps.items()
    )
    interfaces_rows = "".join(
        f"<tr><td>{_html.escape(str(i.get('protocol_binding', '?')))}</td>"
        f"<td><code>{_html.escape(str(i.get('url', '?')))}</code></td></tr>"
        for i in (card.get("supported_interfaces") or [])
    )
    skills = card.get("skills") or []
    skills_html = "".join(
        f"<li><b>{_html.escape(s.get('id', ''))}</b> — "
        f"{_html.escape(s.get('name', ''))}: "
        f"{_html.escape(s.get('description', ''))} "
        f"<span style='color:#888;font-size:12px'>"
        f"[{', '.join(_html.escape(t) for t in s.get('tags') or [])}]</span></li>"
        for s in skills
    )
    body = (
        f"<div style='border:1px solid #ddd;border-radius:8px;padding:16px;"
        f"max-width:760px;font-family:system-ui'>"
        f"<div style='font-size:18px;font-weight:600'>{name} "
        f"<span style='color:#888;font-size:13px'>v{version}</span></div>"
        f"<div style='color:#444;margin:6px 0'>{desc}</div>"
        f"<div style='margin:8px 0'>{caps_html}</div>"
        f"<table style='border-collapse:collapse;font-size:13px'>"
        f"<thead><tr><th align='left'>binding</th><th align='left'>url</th></tr></thead>"
        f"<tbody>{interfaces_rows}</tbody></table>"
        f"<div style='margin-top:10px;font-weight:600'>Skills</div>"
        f"<ul style='font-size:13px'>{skills_html}</ul>"
        f"</div>"
    )
    return HTML(body)
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_viz.py::test_render_agent_card_returns_html -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_agent_card for A2A agent cards"
git push
```

### Task 6: Implement render_mcp_tools

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append render_mcp_tools**

```python
def render_mcp_tools(mcp) -> HTML:
    """Render every tool registered on a FastMCP server as an HTML card grid.

    Reads `mcp._local_provider._components` (FastMCP internals) and renders
    name + description + JSON Schema (input/output) for each tool.
    """
    components = getattr(getattr(mcp, "_local_provider", None),
                         "_components", {}) or {}
    tools = [v for k, v in components.items() if k.startswith("tool:")]

    cards: list[str] = []
    for t in tools:
        name = _html.escape(getattr(t, "name", "?"))
        desc = _html.escape(getattr(t, "description", "") or "")
        schema = getattr(t, "input_schema", None) or getattr(t, "schema", None)
        try:
            schema_json = json.dumps(schema, indent=2, default=str) if schema else "{}"
        except Exception:
            schema_json = str(schema)
        cards.append(
            f"<div style='border:1px solid #ddd;border-radius:8px;padding:12px;"
            f"margin:6px;flex:1 1 320px;max-width:380px'>"
            f"<div style='font-weight:600;font-family:monospace'>{name}</div>"
            f"<div style='color:#555;font-size:13px;margin:4px 0'>{desc}</div>"
            f"<details><summary style='cursor:pointer;font-size:12px;color:#06c'>"
            f"input schema</summary>"
            f"<pre style='background:#f6f8fa;padding:8px;border-radius:4px;"
            f"font-size:12px;overflow-x:auto'>"
            f"{_html.escape(schema_json)}</pre></details>"
            f"</div>"
        )
    grid = (
        f"<div style='display:flex;flex-wrap:wrap'>"
        f"{''.join(cards)}"
        f"</div>"
    )
    header = (
        f"<div style='font-family:system-ui'>"
        f"<div style='font-weight:600;margin-bottom:6px'>"
        f"FastMCP server: {_html.escape(getattr(mcp, 'name', '?'))} "
        f"<span style='color:#888;font-size:12px'>"
        f"({len(tools)} tools)</span></div>"
        f"{grid}</div>"
    )
    return HTML(header)
```

- [ ] **Step 2: Quick manual sanity (no assertion needed; covered by import test)**

Run: `uv run python -c "from notebooks._viz import render_mcp_tools; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_mcp_tools as an HTML card grid with schemas"
git push
```

### Task 7: Implement render_state with diff

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append render_state**

```python
def render_state(state: dict, prev: dict | None = None) -> HTML:
    """Pretty-print state as JSON; if prev given, highlight added/changed keys."""
    keys = sorted(set(state) | set(prev or {}))
    rows: list[str] = []
    for k in keys:
        new_val = state.get(k, "<missing>")
        old_val = (prev or {}).get(k, "<absent>")
        try:
            new_json = json.dumps(new_val, default=str)
        except Exception:
            new_json = str(new_val)
        if prev is None:
            color, label = "#000", ""
        elif k not in prev:
            color, label = "#0a0", " ＋"
        elif k not in state:
            color, label = "#a00", " −"
        elif new_val != old_val:
            color, label = "#a60", " Δ"
        else:
            color, label = "#666", ""
        rows.append(
            f"<tr><td style='color:{color};font-family:monospace;"
            f"vertical-align:top'>{_html.escape(k)}{label}</td>"
            f"<td style='font-family:monospace;font-size:12px'>"
            f"{_html.escape(new_json[:300])}"
            f"{'…' if len(new_json) > 300 else ''}</td></tr>"
        )
    return HTML(
        f"<table style='border-collapse:collapse;font-size:13px'>"
        f"<thead><tr><th align='left'>key</th><th align='left'>value</th></tr>"
        f"</thead><tbody>{''.join(rows)}</tbody></table>"
    )
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_viz.py::test_render_state_returns_html_with_diff -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_state with JSON diff highlighting"
git push
```

### Task 8: Implement render_chat_log

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append render_chat_log**

```python
_BUBBLE_COLORS = {
    "consumer": ("#e3f2fd", "#0d47a1"),  # blue
    "provider": ("#e8f5e9", "#1b5e20"),  # green
    "system":   ("#fff3e0", "#e65100"),  # orange
}


def render_chat_log(log: Iterable[dict]) -> HTML:
    """Render an inter-agent log as chat bubbles, color-coded by sender."""
    bubbles: list[str] = []
    for entry in log:
        sender = (entry.get("from") or "").lower()
        bg, fg = _BUBBLE_COLORS.get(sender, ("#f0f0f0", "#222"))
        align = "flex-start" if sender == "consumer" else "flex-end"
        text = _html.escape(str(entry.get("message", "")))
        bubbles.append(
            f"<div style='display:flex;justify-content:{align};margin:4px 0'>"
            f"<div style='background:{bg};color:{fg};padding:6px 10px;"
            f"border-radius:12px;max-width:70%;font-family:system-ui;font-size:13px'>"
            f"<div style='font-size:10px;opacity:0.7;text-transform:uppercase'>"
            f"{_html.escape(sender)}</div>{text}</div></div>"
        )
    return HTML(
        f"<div style='font-family:system-ui;max-width:760px'>"
        f"{''.join(bubbles)}</div>"
    )
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_viz.py::test_render_chat_log_returns_html -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_chat_log as chat bubbles"
git push
```

### Task 9: Implement render_chain_status (+ from_dict variant)

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append both helpers**

```python
_STATUS_PILL = {
    "NONE":      ("#eee", "#555"),
    "REQUESTED": ("#fff3cd", "#856404"),
    "ACTIVE":    ("#d4edda", "#155724"),
    "CLOSED":    ("#cce5ff", "#004085"),
    "CANCELLED": ("#f8d7da", "#721c24"),
}


def _agreement_table(agreement_id: int, ag: dict) -> str:
    rows: list[str] = []
    for k in ("consumer", "provider", "bandwidthMbps", "durationSeconds",
              "priceWei", "requestDeadline", "tokenId", "status"):
        if k not in ag:
            continue
        v = ag[k]
        rows.append(
            f"<tr><td style='font-family:monospace;color:#555'>{k}</td>"
            f"<td style='font-family:monospace'>{_html.escape(str(v))}</td></tr>"
        )
    status = str(ag.get("status", "NONE"))
    bg, fg = _STATUS_PILL.get(status, ("#eee", "#555"))
    pill = (
        f"<span style='background:{bg};color:{fg};padding:3px 10px;"
        f"border-radius:12px;font-weight:600;font-size:12px'>{status}</span>"
    )
    return (
        f"<div style='font-family:system-ui;max-width:560px'>"
        f"<div style='font-weight:600;margin-bottom:4px'>"
        f"Agreement #{agreement_id} {pill}</div>"
        f"<table style='border-collapse:collapse;font-size:13px'>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def render_chain_status_from_dict(agreement_id: int, ag: dict) -> HTML:
    """Render an Agreement struct (already a dict) with its colored status pill."""
    return HTML(_agreement_table(agreement_id, ag))


def render_chain_status(escrow, agreement_id: int) -> HTML:
    """Render an Agreement looked up live from a web3 contract handle."""
    raw = escrow.functions.getAgreement(int(agreement_id)).call()
    # tuple order matches BandwidthEscrow.Agreement struct
    ag = {
        "consumer": raw[0], "provider": raw[1],
        "bandwidthMbps": int(raw[2]), "durationSeconds": int(raw[3]),
        "priceWei": int(raw[4]), "requestDeadline": int(raw[5]),
        "tokenId": int(raw[6]),
        "status": ("NONE", "REQUESTED", "ACTIVE", "CLOSED", "CANCELLED")[int(raw[7])],
    }
    return render_chain_status_from_dict(agreement_id, ag)
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_viz.py::test_render_chain_status_handles_status_dict -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_chain_status with status pill + struct table"
git push
```

### Task 10: Implement render_event_timeline

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append render_event_timeline**

```python
def render_event_timeline(events: Iterable[dict]) -> HTML:
    """Render a list of decoded chain events as a sortable HTML table."""
    rows: list[str] = []
    for e in events:
        args = e.get("args") or {}
        try:
            args_json = json.dumps(args, default=str)
        except Exception:
            args_json = str(args)
        rows.append(
            f"<tr>"
            f"<td>{int(e.get('block', 0))}</td>"
            f"<td><code>{_html.escape(str(e.get('event', '?')))}</code></td>"
            f"<td style='font-family:monospace;font-size:12px'>"
            f"{_html.escape(args_json[:240])}"
            f"{'…' if len(args_json) > 240 else ''}</td>"
            f"<td>{int(e.get('gas', 0)):,}</td>"
            f"<td><code style='font-size:11px'>"
            f"{_html.escape(str(e.get('txHash', ''))[:16])}…</code></td>"
            f"</tr>"
        )
    return HTML(
        f"<table style='border-collapse:collapse;font-size:13px;font-family:system-ui'>"
        f"<thead style='background:#f6f8fa'>"
        f"<tr><th>block</th><th>event</th><th>args</th>"
        f"<th>gas</th><th>tx</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_viz.py::test_render_event_timeline_returns_html -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_event_timeline as a sortable HTML table"
git push
```

### Task 11: Implement render_topology

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append topology helpers**

```python
def _topology_mermaid(rows: list[dict],
                      active_agreement_ids: set[int],
                      ce_peer: dict) -> str:
    """Build a mermaid graph LR from a list of slot-pool rows."""
    pes: set[str] = set()
    ces: set[str] = set()
    edges: list[str] = []
    active_edges: list[str] = []
    for row in rows:
        for s in row.get("slots", []):
            pe, ce, sif = s["pe"], s["ce"], s["subinterface"]
            pes.add(pe); ces.add(ce)
            label = f"{row['mbps']} Mbps<br/>{sif}"
            edge = f"  {ce} ---|{label}| {pe}"
            if s.get("agreementId") in active_agreement_ids:
                active_edges.append(f"  linkStyle {len(edges)} stroke:#1b5e20,stroke-width:3px")
            edges.append(edge)
    nodes = "\n".join(
        [f"  {p}([PE: {p}])" for p in sorted(pes)]
        + [f"  {c}((CE: {c}))" for c in sorted(ces)]
    )
    pairs = "\n".join(
        f"  {a} -.peer.- {b}" for a, b in sorted(set(
            tuple(sorted([k, v])) for k, v in ce_peer.items() if k in ces and v in ces
        ))
    )
    return (
        "graph LR\n"
        f"{nodes}\n"
        f"{chr(10).join(edges)}\n"
        f"{pairs}\n"
        f"{chr(10).join(active_edges)}"
    )


def render_topology_from_rows(rows: list[dict],
                              active_agreement_ids: set[int],
                              ce_peer: dict) -> HTML | Image:
    """Render the network topology described by raw inventory rows."""
    return render_mermaid(_topology_mermaid(rows, active_agreement_ids, ce_peer))


def render_topology(slot_pool, active_agreement_ids: set[int],
                    ce_peer: dict) -> HTML | Image:
    """Render topology by reading rows directly off a SlotPool instance."""
    rows = slot_pool._read_and_reclaim()  # noqa: SLF001 — public read access
    return render_topology_from_rows(rows, active_agreement_ids, ce_peer)
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_viz.py::test_render_topology_returns_image_or_html -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): render_topology from slot-pool rows + CE peer map"
git push
```

### Task 12: Implement toggle_before_after

**Files:**
- Modify: `notebooks/_viz.py`

- [ ] **Step 1: Append the toggle**

```python
def toggle_before_after(before, after):
    """Return an ipywidgets.VBox toggle, or stack both in HTML if widgets missing."""
    try:
        import ipywidgets as widgets
    except Exception:
        # Fallback: just stack
        return HTML(
            "<div><h4>Before</h4>" + getattr(before, "data", str(before))
            + "<h4>After</h4>" + getattr(after, "data", str(after))
            + "</div>"
        )

    radio = widgets.ToggleButtons(options=["before", "after"], value="before")
    out = widgets.Output()

    def _redraw(_change=None):
        out.clear_output(wait=True)
        with out:
            from IPython.display import display
            display(before if radio.value == "before" else after)

    radio.observe(_redraw, names="value")
    _redraw()
    return widgets.VBox([radio, out])
```

- [ ] **Step 2: Run all viz tests**

Run: `uv run pytest tests/test_viz.py -v`
Expected: 9 PASS.

- [ ] **Step 3: Commit**

```bash
git add notebooks/_viz.py
git commit -m "feat(viz): toggle_before_after via ipywidgets with stacked fallback"
git push
```

---

## Phase 2: Cleanup + README

### Task 13: Delete the old notebooks and rewrite the README

**Files:**
- Delete: `notebooks/01_chain.ipynb`, `notebooks/02_mcp.ipynb`, `notebooks/03_a2a.ipynb`, `notebooks/04_consumer_graph.ipynb`, `notebooks/05_end_to_end.ipynb`
- Modify: `notebooks/README.md`

- [ ] **Step 1: Delete old notebooks**

```bash
git rm notebooks/01_chain.ipynb notebooks/02_mcp.ipynb \
       notebooks/03_a2a.ipynb notebooks/04_consumer_graph.ipynb \
       notebooks/05_end_to_end.ipynb
```

- [ ] **Step 2: Rewrite the README**

Replace `notebooks/README.md` with:

```markdown
# Notebooks

A 21-notebook pedagogical series. Concept-first; each layer has at least
one concept notebook (mostly prose + diagrams) and one walkthrough
notebook (hands-on). The chain, LangGraph, and network layers each get
four; MCP and A2A each get three.

## Prerequisites

- Python 3.13 + `uv`
- `anvil` + `forge` on PATH (install from [Foundry](https://book.getfoundry.sh/getting-started/installation))
- For `06_end_to_end.ipynb` only: `ollama` running locally with `llama3.2:3b` pulled

## Setup

```bash
uv sync
uv run jupyter lab .
```

## Run order

| # | Notebook | What it teaches |
|---|---|---|
| 0 | `00_overview.ipynb` | The 6-stage flow; who talks to whom. |
| 1a | `01a_chain_contract_model.ipynb` | Solidity structs, Status enum, ERC-721 credential. |
| 1b | `01b_chain_escrow_lifecycle.ipynb` | State machine; CEI ordering inside `deposit()`. |
| 1c | `01c_chain_nft_minting.ipynb` | TokenMetadata; on-chain endpoint binding. |
| 1d | `01d_chain_walkthrough.ipynb` | Deploy + walk one trade; events, gas, balances. |
| 2a | `02a_mcp_concepts.ipynb` | MCP, FastMCP, tools/resources, transports. |
| 2b | `02b_mcp_tool_catalog.ipynb` | Inspect every provider + consumer tool's schema. |
| 2c | `02c_mcp_walkthrough.ipynb` | Call tools through `fastmcp.Client`. |
| 3a | `03a_a2a_concepts.ipynb` | AgentCard, skills, executor, EventQueue. |
| 3b | `03b_a2a_agent_cards.ipynb` | Render both agent cards as styled views. |
| 3c | `03c_a2a_walkthrough.ipynb` | Drive the executor in-process. |
| 4a | `04a_graph_state_schema.ipynb` | WorkflowState fields; reducer behavior. |
| 4b | `04b_graph_topology.ipynb` | Render the LangGraph PNG; per-node responsibilities. |
| 4c | `04c_graph_llm_prompts.ipynb` | The two LLM prompts verbatim; failure modes. |
| 4d | `04d_graph_walkthrough.ipynb` | Stream node-by-node; state diffs at every step. |
| 5a | `05a_inventory_and_expiry.ipynb` | SlotPool, event listener, expiry sweep. |
| 6  | `06_end_to_end.ipynb` | Full negotiation with real Ollama. |
| 7a | `07a_network_concepts.ipynb` | SDN_MOCK, gNMI policer, tc tbf, iperf3. |
| 7b | `07b_network_topology.ipynb` | Inline topology drawn from inventory. |
| 7c | `07c_network_before_after.ipynb` | Visual: 0 Mbps → 5 Mbps after settlement. |
| 7d | `07d_network_router_config.ipynb` | gNMI Set body, tc command, mock vs real. |

Every notebook follows the same skeleton: **Concepts → Setup → Build →
Run → Inspect → Recap**. Concept notebooks are mostly markdown;
walkthrough notebooks drive the renderers in `notebooks/_viz.py`.
```

- [ ] **Step 3: Commit**

```bash
git add notebooks/README.md notebooks/01_chain.ipynb notebooks/02_mcp.ipynb \
        notebooks/03_a2a.ipynb notebooks/04_consumer_graph.ipynb \
        notebooks/05_end_to_end.ipynb
git commit -m "chore(notebooks): drop old 5-notebook series; new README index"
git push
```

---

## Phase 3: Per-notebook scaffolds

Each notebook gets exactly one task. Implementation builds the file via
`nbformat`. Use this template helper at the top of every notebook task:

```python
# Run this in a uv shell or paste into a python script for each notebook.
import nbformat as nbf
nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(...),
    nbf.v4.new_code_cell(...),
    ...
]
nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3"}}
nbf.write(nb, "notebooks/<file>.ipynb")
```

For each notebook task: list the cells in order. Use `M:` for markdown
and `C:` for code. After writing, sanity-check via `nbformat.read`.

### Task 14: 00_overview

**Files:**
- Create: `notebooks/00_overview.ipynb`

- [ ] **Step 1: Build the notebook**

Cells:

- M: `# 00 — Overview\n\nThe full system in one page. **Read this first.**\n\nTwo agents (consumer, provider) negotiate a time-bound bandwidth lease, settle it on Ethereum via an atomic on-chain swap (ETH ↔ ERC-721 credential), and the provider activates SDN policy bound to that credential. This series unpacks every layer.`
- M: ```\n## The 6-stage flow\n\n1. **Discover** — consumer fetches the provider's AgentCard.\n2. **Browse + Quote** — consumer asks for the catalog and a price quote.\n3. **Lock payment** — consumer calls `escrow.requestAgreement{value: priceWei}`.\n4. **Mint + swap** — provider mints an NFT, calls `escrow.deposit`; the contract atomically transfers NFT→consumer and ETH→provider.\n5. **Present credential** — consumer signs a fresh nonce, provider verifies on-chain ownership.\n6. **Activate SDN** — provider pushes a gNMI policer + tc rate-limit to the PE/CE bound to the NFT's `endpoint`.\n```
- C: standard sys.path + import boilerplate.
- C: `from notebooks._viz import render_mermaid`
- C: render a mermaid sequence diagram of the 6 stages (paste mermaid source). Diagram shows actors `Consumer`, `Provider`, `Escrow`, `NFT`, `SDN`.
- M: ## Where to go next — table linking each layer to its first notebook in the series.

Mermaid source for the sequence cell:

```python
render_mermaid("""
sequenceDiagram
  participant C as Consumer
  participant P as Provider
  participant E as Escrow
  participant N as NFT
  participant S as SDN
  C->>P: discover (AgentCard)
  C->>P: browse + request_quote
  C->>E: requestAgreement{value}
  E-->>P: AgreementRequested event
  P->>N: mint(agreement, mbps, duration, endpoint)
  P->>E: deposit(agreement, tokenId)
  E->>N: transfer NFT to consumer
  E->>P: pay ETH
  C->>P: present_credential (signed nonce)
  P->>N: ownerOf(tokenId) check
  P->>S: allocate_bandwidth (gNMI + tc)
  P-->>C: status=active, endpoint
""")
```

- [ ] **Step 2: Verify it parses**

Run: `uv run python -c "import nbformat; nbformat.read('notebooks/00_overview.ipynb', as_version=4); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add notebooks/00_overview.ipynb
git commit -m "feat(notebooks): 00_overview — system-level 6-stage flow"
git push
```

### Task 15: 01a_chain_contract_model

**Files:**
- Create: `notebooks/01a_chain_contract_model.ipynb`

- [ ] **Step 1: Build the notebook**

Cells:

- M: `# 01a — Chain: contract model\n\nWe study the two contracts before we deploy them.`
- M: full prose section quoting `BandwidthEscrow.Agreement`:
  - the struct fields one by one
  - the 5-value `Status` enum (NONE/REQUESTED/ACTIVE/CLOSED/CANCELLED) — note that CLOSED is reserved for future use
  - the custom errors
  - why `requestDeadline = block.timestamp + 1 hours`
- M: prose section quoting `BandwidthNFT.TokenMetadata` — note all metadata is on-chain, no IPFS, owner-only mint.
- M: a short paragraph explaining ERC721Holder (the escrow can hold an NFT briefly during atomic swap).
- C: imports — `from pathlib import Path`; read both `.sol` files and display them with `IPython.display.Code`:
  ```python
  from IPython.display import Code, display
  display(Code(filename="contracts/src/BandwidthEscrow.sol", language="solidity"))
  display(Code(filename="contracts/src/BandwidthNFT.sol", language="solidity"))
  ```
- M: "## Why ERC-721 for the credential" — 3 paragraphs: ownership transfer == credential transfer, on-chain enumerability, off-chain verifiability via `ownerOf`.

- [ ] **Step 2: Verify**

Run: `uv run python -c "import nbformat; nbformat.read('notebooks/01a_chain_contract_model.ipynb', as_version=4); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add notebooks/01a_chain_contract_model.ipynb
git commit -m "feat(notebooks): 01a_chain_contract_model — Solidity types & enums"
git push
```

### Task 16: 01b_chain_escrow_lifecycle

**Files:**
- Create: `notebooks/01b_chain_escrow_lifecycle.ipynb`

- [ ] **Step 1: Build the notebook**

Cells:

- M: `# 01b — Chain: escrow lifecycle\n\nThe contract's state machine, transition by transition.`
- C: render mermaid stateDiagram-v2:

```python
render_mermaid("""
stateDiagram-v2
  [*] --> NONE
  NONE --> REQUESTED : requestAgreement (consumer, msg.value)
  REQUESTED --> ACTIVE : deposit (provider, tokenId)
  REQUESTED --> CANCELLED : cancel (consumer or after deadline)
  ACTIVE --> [*]
  CANCELLED --> [*]
""")
```

- M: per-transition table:
  - `requestAgreement` — actor, params, `msg.value`, event `AgreementRequested`
  - `deposit` — provider-only, the four-step atomic swap inside it
  - `cancel` — two paths (consumer anytime; anyone after `requestDeadline`)
- M: dedicated subsection on **Checks-Effects-Interactions** inside `deposit`. Quote the actual code (5-7 lines from `BandwidthEscrow.sol:98-125`). Explain why `ag.status = Status.ACTIVE` MUST come before `nftContract.safeTransferFrom(...)` and the ETH transfer. State the reentrancy implication.
- M: side note on `ERC721Holder` and `safeTransferFrom` accepting NFT into the escrow.
- C: load the deployed contract and display its `getAgreement` ABI fragment for reference (read from `shared/abi/BandwidthEscrow.json`).

```python
import json
from pathlib import Path
abi = json.loads(Path("shared/abi/BandwidthEscrow.json").read_text())
fns = [f for f in abi if f.get("type") == "function" and f["name"] in ("requestAgreement", "deposit", "cancel", "getAgreement")]
print(json.dumps(fns, indent=2))
```

- [ ] **Step 2: Verify**

Run: `uv run python -c "import nbformat; nbformat.read('notebooks/01b_chain_escrow_lifecycle.ipynb', as_version=4); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add notebooks/01b_chain_escrow_lifecycle.ipynb
git commit -m "feat(notebooks): 01b_chain_escrow_lifecycle — state machine + CEI"
git push
```

### Task 17: 01c_chain_nft_minting

**Files:**
- Create: `notebooks/01c_chain_nft_minting.ipynb`

- [ ] **Step 1: Build the notebook**

Cells:

- M: `# 01c — Chain: NFT credential\n\nWhat exactly is in a BandwidthNFT, and why it IS the credential.`
- M: prose explaining each `TokenMetadata` field: `agreementId`, `bandwidthMbps`, `durationSeconds`, `startTime`, `endpoint`. Note the endpoint is `clab://<pe>/<subinterface>` — the literal binding from credential to network identifier. `startTime = block.timestamp` at mint.
- M: section "Why on-chain metadata, not tokenURI/IPFS" — verifiability without an extra trust assumption; small enough to be cheap.
- M: section "Why owner-only mint" — `Ownable(initialOwner)` set to provider EOA in deployment script.
- C: setup boilerplate.
- C: spawn anvil + deploy + mint a single NFT (no escrow flow). Use:

```python
from shared.anvil import anvil
from shared.config import Config
from shared.deploy import deploy_contracts
from shared.chain import make_web3, send_tx, extract_token_id
from shared.contracts import get_nft_contract
from eth_account import Account

DEPLOYER = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'

ctx = anvil(port=18546)
rpc_url = ctx.__enter__()
cfg = Config(rpc_url=rpc_url, deployer_private_key=DEPLOYER,
             provider_private_key=PROVIDER, consumer_private_key=CONSUMER,
             sdn_mock=True)
deploy_contracts(cfg)
w3 = make_web3(cfg)
nft = get_nft_contract(w3)
provider_account = Account.from_key(PROVIDER)
tx, receipt = send_tx(w3, provider_account, PROVIDER,
    nft.functions.mint(provider_account.address, 1234, 5, 600,
                       'clab://pe1/eth-1.100'))
token_id = extract_token_id(receipt, nft)
print('tokenId:', token_id)
```

- C: render the metadata as a "ticket card":

```python
from IPython.display import HTML
meta = nft.functions.getTokenMetadata(token_id).call()
fields = ["agreementId", "bandwidthMbps", "durationSeconds", "startTime", "endpoint"]
rows = "".join(f"<tr><td><b>{k}</b></td><td><code>{v}</code></td></tr>"
               for k, v in zip(fields, meta))
HTML(f"<div style='border:2px dashed #1b5e20;padding:12px;border-radius:8px;"
     f"max-width:480px;font-family:system-ui'>"
     f"<div style='font-size:18px;font-weight:600'>"
     f"🎫 BandwidthNFT #{token_id}</div>"
     f"<table style='font-size:13px'>{rows}</table></div>")
```

- C: teardown — `ctx.__exit__(None, None, None)`.

- [ ] **Step 2: Verify**

Run: `uv run python -c "import nbformat; nbformat.read('notebooks/01c_chain_nft_minting.ipynb', as_version=4); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add notebooks/01c_chain_nft_minting.ipynb
git commit -m "feat(notebooks): 01c_chain_nft_minting — TokenMetadata as a ticket card"
git push
```

### Task 18: 01d_chain_walkthrough

**Files:**
- Create: `notebooks/01d_chain_walkthrough.ipynb`

- [ ] **Step 1: Build the notebook**

Cells:

- M: `# 01d — Chain walkthrough\n\nWalk one full trade. Render every state change.`
- C: setup boilerplate (imports + sys.path + viz).
- C: spawn anvil + deploy. Same as 01c but use `port=18547` to avoid clashes if multiple notebooks run.
- C: snapshot initial balances:

```python
def balances():
    return {
        "consumer": w3.eth.get_balance(consumer_account.address),
        "provider": w3.eth.get_balance(provider_account.address),
        "escrow": w3.eth.get_balance(escrow.address),
    }
b0 = balances(); b0
```

- C: stage 1 — `requestAgreement`:

```python
agreement_id = 1234
mbps, duration, price_wei = 5, 600, 10**16
tx1, _ = send_tx(w3, consumer_account, CONSUMER,
    escrow.functions.requestAgreement(agreement_id, provider_account.address,
                                      mbps, duration), value=price_wei)
display(render_chain_status(escrow, agreement_id))
```

- C: stage 2 — `mint`:

```python
tx2, mint_rcpt = send_tx(w3, provider_account, PROVIDER,
    nft.functions.mint(provider_account.address, agreement_id,
                       mbps, duration, 'clab://pe1/eth-1.100'))
token_id = extract_token_id(mint_rcpt, nft)
print('tokenId =', token_id)
```

- C: stage 3 — `approve` + `deposit` (atomic swap):

```python
send_tx(w3, provider_account, PROVIDER,
        nft.functions.approve(escrow.address, token_id))
tx3, _ = send_tx(w3, provider_account, PROVIDER,
        escrow.functions.deposit(agreement_id, token_id))
display(render_chain_status(escrow, agreement_id))
```

- M: explanation of the three balance shifts that happen INSIDE `deposit`.
- C: render before/after balances as a small HTML table; difference column in wei and ETH.

```python
b1 = balances()
from IPython.display import HTML
def w2e(v): return f"{v/10**18:.4f} ETH"
rows = "".join(
    f"<tr><td>{k}</td><td>{w2e(b0[k])}</td><td>{w2e(b1[k])}</td>"
    f"<td>{w2e(b1[k]-b0[k])}</td></tr>"
    for k in b0)
HTML(f"<table style='border-collapse:collapse;font-family:monospace;font-size:13px'>"
     f"<thead><tr><th>actor</th><th>before</th><th>after</th><th>Δ</th></tr></thead>"
     f"<tbody>{rows}</tbody></table>")
```

- C: render full event timeline (escrow + NFT events from block 0):

```python
from web3 import Web3
events = []
for name in ("AgreementRequested", "AgreementActive", "AgreementCancelled"):
    evt = getattr(escrow.events, name, None)
    if evt:
        for log in evt.get_logs(fromBlock=0):
            tx_hash = log["transactionHash"].hex() if hasattr(log["transactionHash"], "hex") else str(log["transactionHash"])
            gas = w3.eth.get_transaction_receipt(tx_hash)["gasUsed"]
            events.append({"event": name, "block": log["blockNumber"],
                           "args": dict(log["args"]),
                           "gas": int(gas), "txHash": tx_hash})
for log in nft.events.Transfer().get_logs(fromBlock=0):
    tx_hash = log["transactionHash"].hex() if hasattr(log["transactionHash"], "hex") else str(log["transactionHash"])
    gas = w3.eth.get_transaction_receipt(tx_hash)["gasUsed"]
    events.append({"event": "Transfer", "block": log["blockNumber"],
                   "args": {k: str(v) for k, v in dict(log["args"]).items()},
                   "gas": int(gas), "txHash": tx_hash})
events.sort(key=lambda e: (e["block"], e["event"]))
display(render_event_timeline(events))
```

- C: teardown.
- M: recap — pointer to 02a (next layer up: MCP).

- [ ] **Step 2: Verify parses**

Run: `uv run python -c "import nbformat; nbformat.read('notebooks/01d_chain_walkthrough.ipynb', as_version=4); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add notebooks/01d_chain_walkthrough.ipynb
git commit -m "feat(notebooks): 01d_chain_walkthrough — full trade with state pills + timeline"
git push
```

### Task 19: 02a_mcp_concepts

**Files:**
- Create: `notebooks/02a_mcp_concepts.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 02a — MCP concepts`. Sections:
  - **What MCP is** — model-context-protocol, JSON-RPC over stdio/HTTP/in-process.
  - **FastMCP** — `@mcp.tool()` decorator wraps a function with a JSON Schema derived from type hints + docstring.
  - **Tools vs resources vs prompts** — we only use tools.
  - **Transports** — in-process (this repo's tests + the FastAPI app's mounted `/mcp`), stdio (CLI tools), HTTP (separate process).
  - **Why both agents are MCP servers** — the consumer also exposes its tools so other agents could orchestrate it.
- C: render mermaid request-flow diagram:

```python
render_mermaid("""
graph LR
  caller[Caller code]
  client[fastmcp.Client]
  server[FastMCP server]
  fn[Decorated python fn]
  caller -->|"call_tool(name, args)"| client
  client -->|JSON-RPC| server
  server -->|"validates against<br/>JSON Schema"| fn
  fn -->|return value| server
  server -->|JSON-RPC response| client
  client -->|"result.content[0].text"| caller
""")
```

- M: pointer to 02b/02c.

- [ ] **Step 2: Verify** — `uv run python -c "import nbformat; nbformat.read('notebooks/02a_mcp_concepts.ipynb', as_version=4); print('ok')"`
- [ ] **Step 3: Commit**

```bash
git add notebooks/02a_mcp_concepts.ipynb
git commit -m "feat(notebooks): 02a_mcp_concepts — MCP/FastMCP mental model"
git push
```

### Task 20: 02b_mcp_tool_catalog

**Files:**
- Create: `notebooks/02b_mcp_tool_catalog.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 02b — MCP tool catalog`. Three sections: "Provider tools (8)", "Consumer tools (7)", "Side-by-side".
- C: setup boilerplate.
- C: build provider MCP and render:

```python
from provider.mcp_server import build_mcp_server as build_provider_mcp
cfg_p = Config(provider_private_key=PROVIDER, sdn_mock=True)
mcp_p, _ = build_provider_mcp(cfg_p)
display(render_mcp_tools(mcp_p))
```

- C: build consumer MCP and render:

```python
from consumer.mcp_server import build_mcp_server as build_consumer_mcp
cfg_c = Config(consumer_private_key=CONSUMER)
mcp_c, _ = build_consumer_mcp(cfg_c)
display(render_mcp_tools(mcp_c))
```

- M: prose mapping which consumer tool calls which provider tool:
  - `discover_provider` → `/.well-known/agent-card.json` (no MCP — pure HTTP)
  - `browse_catalog` → A2A `get_catalog` → MCP `get_catalog`
  - `request_quote` → A2A `request_quote` → MCP `request_quote`
  - `present_credential` → A2A `activate` → MCP `verify_credential_ownership` + `allocate_bandwidth`
  - local-only: `lock_payment`, `await_settlement`, `verify_credential` (chain reads/writes)

- [ ] **Step 2: Verify** — same nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/02b_mcp_tool_catalog.ipynb
git commit -m "feat(notebooks): 02b_mcp_tool_catalog — visual inspector for both servers"
git push
```

### Task 21: 02c_mcp_walkthrough

**Files:**
- Create: `notebooks/02c_mcp_walkthrough.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 02c — MCP walkthrough\n\nCall provider tools through `fastmcp.Client`. No A2A, no chain.`
- C: setup boilerplate.
- C: build provider MCP + tool_log:

```python
from provider.mcp_server import build_mcp_server
cfg = Config(provider_private_key=PROVIDER, sdn_mock=True)
mcp, tool_log = build_mcp_server(cfg)
```

- C: list tools + call `get_catalog`:

```python
import asyncio, json
from fastmcp import Client

async def demo():
    async with Client(mcp) as c:
        tools = await c.list_tools()
        print('Tools:')
        for t in tools:
            print(f'  - {t.name}')
        catalog = await c.call_tool('get_catalog', {})
        return json.loads(catalog.content[0].text)
catalog = asyncio.get_event_loop().run_until_complete(demo())
catalog
```

- M: explanation of `result.content[0].text` shape — FastMCP serializes the return value as text content.
- C: call `request_quote`:

```python
async def quote():
    async with Client(mcp) as c:
        r = await c.call_tool('request_quote',
            {'package_id': 'medium',
             'consumer_address': '0x000000000000000000000000000000000000dEaD'})
        return json.loads(r.content[0].text)
quote_data = asyncio.get_event_loop().run_until_complete(quote())
quote_data
```

- C: render `tool_log`:

```python
from IPython.display import HTML
rows = "".join(
    f"<tr><td>{e['ts']:.2f}</td><td><code>{e['tool']}</code></td>"
    f"<td>{e['status']}</td><td><code style='font-size:12px'>{e['args']}</code></td></tr>"
    for e in tool_log)
HTML(f"<table style='border-collapse:collapse;font-size:13px'>"
     f"<thead style='background:#f6f8fa'><tr><th>ts</th><th>tool</th><th>status</th><th>args</th></tr></thead>"
     f"<tbody>{rows}</tbody></table>")
```

- M: recap; chain-touching tools (mint_credential, complete_swap) are deferred to 05a.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/02c_mcp_walkthrough.ipynb
git commit -m "feat(notebooks): 02c_mcp_walkthrough — call read-only tools end-to-end"
git push
```

### Task 22: 03a_a2a_concepts

**Files:**
- Create: `notebooks/03a_a2a_concepts.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 03a — A2A concepts`. Sections:
  - **What A2A is** — Google's Agent-to-Agent SDK; protobuf-on-the-wire; JSON-RPC binding.
  - **AgentCard** — discovery document at `/.well-known/agent-card.json`.
  - **Skills** — id/name/description/tags/examples; how the consumer's `discover_provider` checks `REQUIRED_PROVIDER_SKILLS`.
  - **Executor pattern** — `AgentExecutor.execute(context, queue)` enqueues `TaskArtifactUpdateEvent` then `TaskStatusUpdateEvent`.
  - **protobuf payload** — `Message → parts[*].data` is `google.protobuf.Value(struct_value=Struct)`. Use `MessageToDict` / `ParseDict`.
- C: render mermaid sequence diagram for one A2A call:

```python
render_mermaid("""
sequenceDiagram
  participant C as Consumer (a2a.client)
  participant H as Provider HTTP /a2a (JSONRPC)
  participant E as Executor
  participant Q as EventQueue
  C->>H: send_message(Message[parts])
  H->>E: execute(context, queue)
  E->>Q: TaskArtifactUpdateEvent (data part)
  E->>Q: TaskStatusUpdateEvent COMPLETED
  Q-->>H: stream events
  H-->>C: artifact_update chunk
""")
```

- M: short note on shape quirks: `WhichOneof('payload')`, `artifact_update.artifact.parts[0].data`.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/03a_a2a_concepts.ipynb
git commit -m "feat(notebooks): 03a_a2a_concepts — protocol mental model"
git push
```

### Task 23: 03b_a2a_agent_cards

**Files:**
- Create: `notebooks/03b_a2a_agent_cards.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 03b — Agent cards\n\nThe discovery payload, rendered.`
- C: setup boilerplate.
- C: render provider card:

```python
from provider.agent_card import build_provider_agent_card
from google.protobuf.json_format import MessageToDict
cfg_p = Config(provider_private_key=PROVIDER, sdn_mock=True)
card_p = build_provider_agent_card(cfg_p)
card_p_dict = MessageToDict(card_p, preserving_proto_field_name=True)
display(render_agent_card(card_p_dict))
```

- C: render consumer card:

```python
from consumer.agent_card import build_consumer_agent_card
cfg_c = Config(consumer_private_key=CONSUMER)
card_c = build_consumer_agent_card(cfg_c)
display(render_agent_card(MessageToDict(card_c, preserving_proto_field_name=True)))
```

- M: side-by-side commentary:
  - provider has 3 skills (`get_catalog`, `request_quote`, `activate`); consumer has 1 (`purchase_bandwidth`).
  - provider exposes JSONRPC at `/a2a`; consumer exposes HTTP at `/chat`.
  - both use `text/plain` and/or `application/json`.
- C: dump the card JSON in raw form for completeness:

```python
import json; print(json.dumps(card_p_dict, indent=2))
```

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/03b_a2a_agent_cards.ipynb
git commit -m "feat(notebooks): 03b_a2a_agent_cards — both cards rendered + raw JSON"
git push
```

### Task 24: 03c_a2a_walkthrough

**Files:**
- Create: `notebooks/03c_a2a_walkthrough.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 03c — A2A walkthrough\n\nDrive the provider's executor in-process. No port; no httpx.`
- C: setup boilerplate (include the FakeQueue + helpers from existing 03_a2a):

```python
from provider.agent_executor import BandwidthProviderExecutor
from provider.mcp_server import build_mcp_server
from a2a.types import Message, Part
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.struct_pb2 import Struct, Value
from unittest.mock import MagicMock

cfg = Config(provider_private_key=PROVIDER, sdn_mock=True)
mcp, _ = build_mcp_server(cfg)
executor = BandwidthProviderExecutor(mcp)

class FakeQueue:
    def __init__(self): self.events = []
    async def enqueue_event(self, e): self.events.append(e)

def data_part(d):
    s = Struct(); ParseDict(d, s)
    return Part(data=Value(struct_value=s), media_type='application/json')

def make_context(payload):
    msg = Message(message_id='m1', parts=[data_part(payload)])
    ctx = MagicMock(); ctx.message = msg; ctx.task_id = 't1'; ctx.context_id = 'c1'
    return ctx

def payload_of(event):
    return MessageToDict(event.artifact.parts[0].data, preserving_proto_field_name=True)
```

- C: drive `get_catalog` and render the artifact + status events:

```python
import asyncio
from IPython.display import HTML
async def run_action(payload):
    q = FakeQueue()
    await executor.execute(make_context(payload), q)
    return q.events

events = asyncio.get_event_loop().run_until_complete(run_action({"action": "get_catalog"}))
for e in events:
    cls = type(e).__name__
    print(cls)
    if hasattr(e, 'artifact'):
        print(' ', payload_of(e))
    elif hasattr(e, 'status'):
        print(' status =', e.status.state)
```

- C: drive `request_quote` and render via `render_chat_log`:

```python
events = asyncio.get_event_loop().run_until_complete(run_action({
    "action": "request_quote", "package_id": "medium",
    "consumer_address": "0x000000000000000000000000000000000000dEaD"}))
log = []
for e in events:
    if hasattr(e, 'artifact'):
        log.append({"from": "provider", "message": str(payload_of(e))})
display(render_chat_log(log))
```

- M: explanation that `activate` is deferred to 06_end_to_end because it requires a real signed nonce against a deployed contract.
- C: render the executor's mermaid dispatch diagram (action → MCP tools):

```python
render_mermaid("""
graph LR
  A[action: get_catalog] --> M1[MCP get_catalog]
  B[action: request_quote] --> M2[MCP request_quote]
  C[action: activate] --> M3[MCP verify_credential_ownership]
  C --> M4[MCP allocate_bandwidth]
""")
```

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/03c_a2a_walkthrough.ipynb
git commit -m "feat(notebooks): 03c_a2a_walkthrough — drive executor with FakeQueue"
git push
```

### Task 25: 04a_graph_state_schema

**Files:**
- Create: `notebooks/04a_graph_state_schema.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 04a — Graph state schema`. Sections:
  - `WorkflowState` is a `TypedDict, total=False`.
  - Field-by-field table with: name, type, written-by-node, read-by-node.
  - `log` and `thinking` are append-mutated lists; every node returns `{"log": state["log"]}` to preserve them.
  - Why `agreement_id` is `str` (consumer carries it as a string for JSON safety).
- C: import + display the TypedDict via `inspect`:

```python
import inspect
from consumer.graph import WorkflowState
print(inspect.getsource(WorkflowState))
```

- C: render a manual table mapping fields to writing nodes (HTML in `_viz`-style):

```python
from IPython.display import HTML
rows_data = [
    ("user_message",        "str",       "(initial)",      "pick_tier_node, summary_node"),
    ("provider_url",        "str",       "discover_node",  "all A2A nodes"),
    ("provider_urls",       "list[str]", "discover_node",  "browse_node"),
    ("offers",              "list[dict]","browse_node",    "pick_tier_node"),
    ("catalog",             "list[dict]","browse_node",    "pick_tier_node"),
    ("chosen_tier",         "str",       "pick_tier_node", "quote_node, summary_node"),
    ("chosen_mbps",         "float",     "pick_tier_node", "verify_node, summary_node"),
    ("agreement_id",        "str",       "quote_node",     "lock_node, settle_node, summary_node"),
    ("tx_hash",             "str",       "lock_node",      "(observability)"),
    ("token_id",            "int",       "settle_node",    "present_node, verify_node, summary_node"),
    ("settle_attempts",     "int",       "settle_node",    "_settle_route"),
    ("activation",          "dict",      "present_node",   "(observability)"),
    ("on_chain_verification","dict",     "verify_node",    "(observability)"),
    ("final_response",      "str",       "summary_node|error_node", "—"),
    ("log",                 "list[dict]","every node",     "every node"),
    ("thinking",            "list[str]", "pick_tier_node, summary_node", "—"),
    ("error",               "str|None",  "any node on failure", "_route_after, _settle_route"),
]
rows = "".join(f"<tr><td><code>{n}</code></td><td><code>{t}</code></td>"
               f"<td>{w}</td><td>{r}</td></tr>" for n,t,w,r in rows_data)
HTML(f"<table style='border-collapse:collapse;font-size:12px;font-family:system-ui'>"
     f"<thead style='background:#f6f8fa'><tr><th>field</th><th>type</th>"
     f"<th>written by</th><th>read by</th></tr></thead>"
     f"<tbody>{rows}</tbody></table>")
```

- M: pointer to 04b for the topology view.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/04a_graph_state_schema.ipynb
git commit -m "feat(notebooks): 04a_graph_state_schema — every WorkflowState field charted"
git push
```

### Task 26: 04b_graph_topology

**Files:**
- Create: `notebooks/04b_graph_topology.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 04b — Graph topology`. Renders the LangGraph PNG inline, then walks every node.
- C: setup + build graph with stub tools (tools dict can be all `lambda *a, **k: '{}'` — we never invoke):

```python
from consumer.graph import build_graph
from shared.config import Config

cfg = Config(consumer_private_key=CONSUMER)
async def _noop(*a, **k): return "{}"
def _noop_sync(*a, **k): return "{}"
tools = {n: (_noop if n in {"discover_provider","browse_catalog","request_quote","present_credential"} else _noop_sync)
         for n in ("discover_provider","browse_catalog","request_quote","lock_payment",
                   "await_settlement","present_credential","verify_credential")}
graph = build_graph(cfg, tools)
```

- C: render the LangGraph PNG via the helper:

```python
from IPython.display import Image
png = graph.get_graph().draw_mermaid_png()
Image(png)
```

- C: print the mermaid source so readers can read the conditional edges:

```python
print(graph.get_graph().draw_mermaid())
```

- M: per-node responsibility table (10 nodes):
  - `discover_node` — fetches AgentCards, drops providers missing required skills.
  - `browse_node` — `get_catalog` from each surviving provider; merges by best price.
  - `pick_tier_node` — **LLM call**; deterministic fallback if output isn't a valid tier word.
  - `quote_node` — `request_quote` for the chosen tier; populates `agreement_id`.
  - `lock_node` — sends `escrow.requestAgreement`; populates `tx_hash`.
  - `settle_node` — polls `getAgreement`; sets `token_id` on ACTIVE; retries up to 3.
  - `present_node` — sends signed nonce via A2A `activate`.
  - `verify_node` — independent on-chain check (`ownerOf`, metadata mbps match).
  - `summary_node` — **LLM call** (informational); builds `final_response`.
  - `error_node` — terminal sink for any `state["error"]`.
- M: subsection on `_settle_route` — only true conditional loop in the graph.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/04b_graph_topology.ipynb
git commit -m "feat(notebooks): 04b_graph_topology — LangGraph PNG + per-node table"
git push
```

### Task 27: 04c_graph_llm_prompts

**Files:**
- Create: `notebooks/04c_graph_llm_prompts.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 04c — LLM prompts`. Two LLM-touching nodes; we show each prompt verbatim.
- M: section A: **pick_tier prompt** — paste the actual prompt string from `consumer/graph.py:154-159`. Explain why "EXACTLY ONE WORD".
- M: subsection — when the LLM disobeys: deterministic regex parse + `deterministic_tier_pick` rules from `consumer/tier_selection.py`.
- C: import and demonstrate the deterministic fallback:

```python
from consumer.tier_selection import deterministic_tier_pick, rank_catalog
catalog = [
    {"packageId": "small",  "mbps": 2, "durationSeconds": 600, "priceWei": 10**16},
    {"packageId": "medium", "mbps": 5, "durationSeconds": 600, "priceWei": 2*10**16},
    {"packageId": "large",  "mbps": 8, "durationSeconds": 600, "priceWei": 8*10**16},
]
print('"I need 5 Mbps" →', deterministic_tier_pick("I need 5 Mbps", catalog)["packageId"])
print('"cheapest please" →', deterministic_tier_pick("cheapest please", catalog)["packageId"])
print('"asdf" →', deterministic_tier_pick("asdf", catalog)["packageId"])
```

- M: section B: **summary prompt**. Paste the prompt from `consumer/graph.py:303-310`. Note that `final_response` is template-built, not LLM-built — the LLM call is decorative/pedagogical.
- C: stub both LLM calls and run through `pick_tier_node` (covered in 04d). For this notebook, show three example LLM outputs and how each is parsed:

```python
import re
def parse_pick(raw, valid):
    for token in re.findall(r"[a-zA-Z]+", raw.lower()):
        if token in valid:
            return token
    return None
valid = {"small", "medium", "large"}
for raw in ["medium", "I would say MEDIUM is best", "42"]:
    print(repr(raw), "→", parse_pick(raw, valid) or "DETERMINISTIC FALLBACK")
```

- M: recap.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/04c_graph_llm_prompts.ipynb
git commit -m "feat(notebooks): 04c_graph_llm_prompts — both prompts + parser semantics"
git push
```

### Task 28: 04d_graph_walkthrough

**Files:**
- Create: `notebooks/04d_graph_walkthrough.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 04d — Graph walkthrough\n\nStream the graph node-by-node with stubs.`
- C: setup + stubs (reuse the pattern from existing `04_consumer_graph.ipynb`).

```python
from consumer.graph import build_graph
from langchain_ollama import ChatOllama
import json

fake_catalog = [
    {'packageId': 'small',  'mbps': 2, 'durationSeconds': 600, 'priceWei': 10**16, 'availableSlots': 1},
    {'packageId': 'medium', 'mbps': 5, 'durationSeconds': 600, 'priceWei': 2*10**16, 'availableSlots': 1},
    {'packageId': 'large',  'mbps': 8, 'durationSeconds': 600, 'priceWei': 8*10**16, 'availableSlots': 1},
]

async def discover(url): return json.dumps({'name': 'P', 'version': '1',
    'skills': ['get_catalog', 'request_quote', 'activate']})
async def browse(url): return json.dumps(fake_catalog)
async def quote(url, pkg): return json.dumps({'agreementId': '777', 'priceWei': 2*10**16,
    'bandwidthMbps': 5, 'durationSeconds': 600})
def lock(aid): return 'OK 0xdeadbeef'
def settle(aid): return 'OK tokenId=99'
async def present(url, tid): return json.dumps({'status': 'active', 'bandwidthMbps': 5, 'tokenId': tid})
def verify(tid): return json.dumps({'ok': True, 'owner': '0xC', 'ownerIsConsumer': True,
    'agreementId': 777, 'mbps': 5, 'durationSeconds': 600,
    'secondsRemaining': 600, 'endpoint': 'clab://pe1/eth-1.100'})

tools = {'discover_provider': discover, 'browse_catalog': browse,
         'request_quote': quote, 'lock_payment': lock,
         'await_settlement': settle, 'present_credential': present,
         'verify_credential': verify}

class _R:
    def __init__(self, c): self.content = c
async def fake_ainvoke(self, prompt, *a, **kw):
    return _R('medium' if 'EXACTLY ONE WORD' in prompt else 'ok')
ChatOllama.ainvoke = fake_ainvoke

cfg = Config(consumer_private_key=CONSUMER)
graph = build_graph(cfg, tools)
```

- C: stream node-by-node and show state diff after each node:

```python
import asyncio
async def stream_with_diff():
    initial = {'user_message': 'I need 5 Mbps',
               'provider_url': 'http://provider:8002',
               'log': [], 'thinking': []}
    prev = dict(initial)
    diffs = []
    async for step in graph.astream(initial):
        for node, output in step.items():
            cur = {**prev, **(output if isinstance(output, dict) else {})}
            diffs.append((node, prev, cur))
            prev = cur
    return diffs

diffs = asyncio.get_event_loop().run_until_complete(stream_with_diff())
for node, prev_s, cur_s in diffs:
    from IPython.display import display, HTML
    display(HTML(f"<h4 style='margin:8px 0 4px'>node: <code>{node}</code></h4>"))
    display(render_state(cur_s, prev_s))
```

- C: ainvoke once for the full final state and render the conversation log + final state:

```python
final = asyncio.get_event_loop().run_until_complete(graph.ainvoke({
    'user_message': 'I need 5 Mbps',
    'provider_url': 'http://provider:8002',
    'log': [], 'thinking': []}))
display(render_chat_log(final['log']))
display(render_state(final))
```

- M: recap; pointer to 05a (inventory layer) and 06 (real run with Ollama).

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/04d_graph_walkthrough.ipynb
git commit -m "feat(notebooks): 04d_graph_walkthrough — stream with state diffs"
git push
```

### Task 29: 05a_inventory_and_expiry

**Files:**
- Create: `notebooks/05a_inventory_and_expiry.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 05a — Inventory + expiry\n\nWhere "I have a slot" lives, and how the provider reclaims one.`
- M: sections:
  - **The catalog** — `provider/catalog.py` constants (3 tiers, prices, durations).
  - **The inventory file** — `provider/inventory.txt` JSONL; format quoted from the docstring.
  - **SlotPool semantics** — `reserve` / `release` / `available_count` / `lookup`; `fcntl.LOCK_EX`; expiry-on-read reclaim.
  - **Quote TTL** — 300s; `pending_quotes` cleanup.
  - **Event listener** — polls `AgreementRequested`, drives `mint_credential` + `complete_swap`.
  - **Expiry sweep** — every 30s, calls `revoke_bandwidth` and `slot_pool.release` for expired slots.
- C: load and render the live inventory:

```python
import json
from pathlib import Path
rows = [json.loads(line) for line in Path("provider/inventory.txt").read_text().splitlines() if line.strip()]
from IPython.display import HTML
slot_rows = []
for r in rows:
    for s in r["slots"]:
        slot_rows.append((r["tier"], r["mbps"], r["durationSeconds"],
                          s["pe"], s["subinterface"], s["ce"],
                          s["agreementId"], s["expiresAt"]))
html_rows = "".join(f"<tr>{''.join(f'<td>{c}</td>' for c in row)}</tr>" for row in slot_rows)
HTML(f"<table style='border-collapse:collapse;font-size:13px;font-family:monospace'>"
     f"<thead style='background:#f6f8fa'><tr>"
     f"<th>tier</th><th>mbps</th><th>dur</th>"
     f"<th>pe</th><th>subif</th><th>ce</th>"
     f"<th>aid</th><th>expiresAt</th></tr></thead>"
     f"<tbody>{html_rows}</tbody></table>")
```

- C: walkthrough — copy inventory to a tmp dir, reserve, list, release:

```python
import shutil, tempfile, time
from shared.slot_pool import SlotPool

td = tempfile.mkdtemp()
inv_path = Path(td) / "inventory.txt"
shutil.copy("provider/inventory.txt", inv_path)
pool = SlotPool(inv_path)
print('available medium:', pool.available_count('medium'))
slot = pool.reserve('medium', agreement_id=42, duration_seconds=2)
print('reserved:', slot)
print('available medium now:', pool.available_count('medium'))

time.sleep(3)
print('expired ids:', pool.expired_agreement_ids())
print('available medium after read+reclaim:', pool.available_count('medium'))
```

- M: short note: `expired_agreement_ids` is the read-only enumeration; the `expiry_sweep_loop` consumes those plus calls `revoke_bandwidth`. We don't run the sweep loop here (no MCP); 06_end_to_end exercises it implicitly.
- M: pointer to 06 + 07a-d.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/05a_inventory_and_expiry.ipynb
git commit -m "feat(notebooks): 05a_inventory_and_expiry — slot pool + sweep semantics"
git push
```

### Task 30: 06_end_to_end

**Files:**
- Create: `notebooks/06_end_to_end.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 06 — End-to-end\n\nFull negotiation in-process: anvil + provider FastAPI + consumer FastAPI + real Ollama.`
- M: prerequisites callout: `ollama serve` must be running with `llama3.2:3b` pulled.
- C: setup boilerplate.
- C: spawn anvil + deploy + start both FastAPI apps in threads (port the existing `05_end_to_end.ipynb` setup verbatim — `serve(app, port)` helper, free_port, env vars). Use the existing notebook's logic; don't re-derive.
- C: render mermaid sequence diagram of the full flow across 5 actors (Consumer-graph, Consumer-MCP, Provider-A2A, Provider-MCP, Chain, Ollama).
- C: snapshot inventory before:

```python
inv_before = Path("provider/inventory.txt").read_text()
display(HTML(f"<pre>{inv_before}</pre>"))
```

- C: POST `/chat` with `"I need 5 Mbps for 10 minutes"` and capture response:

```python
import httpx, asyncio
async def chat():
    async with httpx.AsyncClient(timeout=180.0) as http:
        r = await http.post(f'{consumer_url}/chat',
                            json={"message": "I need 5 Mbps for 10 minutes"})
        return r.json()
body = asyncio.get_event_loop().run_until_complete(chat())
display(render_chat_log(body['log']))
```

- C: snapshot inventory after; display side-by-side:

```python
inv_after = Path("provider/inventory.txt").read_text()
display(HTML(f"<table><tr><th>before</th><th>after</th></tr>"
             f"<tr><td><pre>{inv_before}</pre></td>"
             f"<td><pre>{inv_after}</pre></td></tr></table>"))
```

- C: fetch on-chain events via `/chain_events` and render with timeline helper:

```python
async def chain():
    async with httpx.AsyncClient(timeout=10.0) as http:
        return (await http.get(f'{consumer_url}/chain_events')).json()
events = asyncio.get_event_loop().run_until_complete(chain())
display(render_event_timeline(events))
```

- C: teardown — stop both servers, exit anvil context.
- M: pointer to 07a-d for the network layer view of the SAME flow.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/06_end_to_end.ipynb
git commit -m "feat(notebooks): 06_end_to_end — full negotiation with rich rendering"
git push
```

### Task 31: 07a_network_concepts

**Files:**
- Create: `notebooks/07a_network_concepts.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 07a — Network concepts`. Sections:
  - **What SDN_MOCK gates** — `provider/mcp_server.py` returns no-op JSON when `cfg.sdn_mock=True` for `allocate_bandwidth`/`revoke_bandwidth`/`verify_bandwidth`. Real path delegates to `srl_bandwidth.bandwidth.*`.
  - **Mental model** — three layers per slot: gNMI policer at the PE (rate limit), tc tbf on the CE (queue), iperf3 verify (UDP probe between CE peers).
  - **Endpoint binding** — `clab://<pe>/<subinterface>` is what the NFT carries; the provider looks up `(pe, subinterface, ce)` from inventory by `agreementId`.
  - **CE peer pairing** — `provider/app.py:31` hard-codes `CE_PEER = {"ce1":"ce2","ce2":"ce1","ce3":"ce4","ce4":"ce3"}` because verify needs a destination.
  - **Why three tools, not one** — allocate is producer (mint side); revoke is dual (expiry sweep); verify is a separate measurement op so the consumer never bypasses the contract.
- C: render layered diagram:

```python
render_mermaid("""
graph TB
  subgraph Provider
    A[allocate_bandwidth]
    R[revoke_bandwidth]
    V[verify_bandwidth]
  end
  subgraph PE [PE router]
    G[gNMI policer]
  end
  subgraph CE [CE host]
    T[tc tbf]
    I[iperf3 server]
  end
  A --> G
  A --> T
  R --> G
  R --> T
  V --> I
""")
```

- M: pointer to upstream `srl-gnmi-bandwidth-poc` repo (already in `pyproject.toml [tool.uv.sources]`).
- M: pointer to 07b/07c/07d.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/07a_network_concepts.ipynb
git commit -m "feat(notebooks): 07a_network_concepts — SDN_MOCK + gNMI/tc/iperf3 model"
git push
```

### Task 32: 07b_network_topology

**Files:**
- Create: `notebooks/07b_network_topology.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 07b — Network topology\n\nDrawn live from the inventory file and the CE-peer map.`
- C: setup boilerplate.
- C: load inventory + CE_PEER, render topology with no active slots:

```python
import json
from pathlib import Path
from provider.app import CE_PEER
rows = [json.loads(l) for l in Path("provider/inventory.txt").read_text().splitlines() if l.strip()]
display(render_topology_from_rows(rows, active_agreement_ids=set(), ce_peer=CE_PEER))
```

- M: explain the resulting graph: 3 slots → 3 CE→PE edges; CE peer pairs shown as dotted edges.
- C: render the per-tier summary table:

```python
from IPython.display import HTML
trows = "".join(f"<tr><td>{r['tier']}</td><td>{r['mbps']}</td>"
                f"<td>{r['durationSeconds']}</td>"
                f"<td>{r['slots'][0]['pe']}</td>"
                f"<td>{r['slots'][0]['subinterface']}</td>"
                f"<td>{r['slots'][0]['ce']}</td></tr>" for r in rows)
HTML(f"<table style='border-collapse:collapse;font-size:13px;font-family:system-ui'>"
     f"<thead><tr><th>tier</th><th>mbps</th><th>dur</th>"
     f"<th>pe</th><th>subif</th><th>ce</th></tr></thead>"
     f"<tbody>{trows}</tbody></table>")
```

- M: note: this notebook reads inventory at runtime, so editing `provider/inventory.txt` and re-running the cell updates the diagram.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/07b_network_topology.ipynb
git commit -m "feat(notebooks): 07b_network_topology — live diagram from inventory.txt"
git push
```

### Task 33: 07c_network_before_after (the marquee visual)

**Files:**
- Create: `notebooks/07c_network_before_after.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 07c — Before / after\n\nThe consumer starts with **0 Mbps**. After settlement: **5 Mbps** on the medium-tier slot. A toggle below shows both states at once.`
- C: setup boilerplate.
- C: load inventory + CE_PEER:

```python
import json
from pathlib import Path
from provider.app import CE_PEER
rows = [json.loads(l) for l in Path("provider/inventory.txt").read_text().splitlines() if l.strip()]
```

- C: build the "before" frame — render topology with NO active agreements, plus a styled "Consumer: 0 Mbps" banner:

```python
from IPython.display import HTML, display
def banner(label, value, color):
    return HTML(f"<div style='background:{color};color:white;padding:10px;"
                f"border-radius:8px;font-family:system-ui;text-align:center;"
                f"max-width:400px;font-size:18px;font-weight:600'>"
                f"{label}: {value}</div>")

before_top = render_topology_from_rows(rows, set(), CE_PEER)
before = HTML(banner("Consumer", "0 Mbps", "#888").data + before_top.data
              if hasattr(before_top, 'data')
              else f"<div>{banner('Consumer', '0 Mbps', '#888').data}</div>")
```

- C: simulate "after" — pretend `agreementId=777` is bound to the medium slot (mutate the rows in-memory):

```python
rows_after = json.loads(json.dumps(rows))  # deep copy
for r in rows_after:
    if r["tier"] == "medium":
        r["slots"][0]["agreementId"] = 777
        r["slots"][0]["expiresAt"] = 9999999999
after_top = render_topology_from_rows(rows_after, {777}, CE_PEER)
after = HTML(banner("Consumer", "5 Mbps (medium tier)", "#1b5e20").data
             + (after_top.data if hasattr(after_top, 'data') else ''))
```

- C: drive the toggle:

```python
toggle_before_after(before, after)
```

- M: explain that the topology helper applies a green `linkStyle` to active edges (see `notebooks/_viz.py`), so the toggle flips the highlight on the medium-tier link.
- M: instructions to run a real before/after via `06_end_to_end` then re-render this notebook with `agreementId` from the live `provider/inventory.txt`.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/07c_network_before_after.ipynb
git commit -m "feat(notebooks): 07c_network_before_after — the 0→5 Mbps toggle visual"
git push
```

### Task 34: 07d_network_router_config

**Files:**
- Create: `notebooks/07d_network_router_config.ipynb`

- [ ] **Step 1: Build**

Cells:

- M: `# 07d — Router config\n\nWhat would actually be pushed to the network when SDN_MOCK=false.`
- C: setup boilerplate.
- C: side-by-side: call `allocate_bandwidth` against an SDN_MOCK=true MCP and render the response:

```python
import asyncio, json
from fastmcp import Client
from provider.mcp_server import build_mcp_server
cfg_mock = Config(provider_private_key=PROVIDER, sdn_mock=True)
mcp_mock, _ = build_mcp_server(cfg_mock)

async def alloc(mcp):
    async with Client(mcp) as c:
        r = await c.call_tool("allocate_bandwidth",
            {"customer_id": "0xC0FFEE", "pe": "pe1",
             "subinterface": "ethernet-1/3.0", "mbps": 5.0})
        return json.loads(r.content[0].text)

mock_resp = asyncio.get_event_loop().run_until_complete(alloc(mcp_mock))
mock_resp
```

- M: explain the mock body: `gnmi_pushed=False, tc_applied=False, message="mocked"`.
- M: section "What real mode pushes" — paste a representative gNMI Set request body for a Nokia SR Linux QoS policer (template form, not the live srl_bandwidth payload — keep it readable):

```python
from IPython.display import Markdown
Markdown("""
```yaml
# gNMI Set request (illustrative)
update:
  - path: /interface[name=ethernet-1/3]/subinterface[index=0]/qos
    val:
      input:
        classifiers:
          ipv4-classifier: customer-class
        policers:
          - name: customer-policer
            cir: 5000000        # 5 Mbps in bits/sec
            cbs: 625000
            action: drop-on-exceed
```

```bash
# tc tbf on the CE host (illustrative)
tc qdisc add dev eth1.100 root tbf rate 5mbit burst 32kbit latency 50ms
```
""")
```

- M: section "Verify probe" — paste an iperf3 UDP probe template + a sample `verify_bandwidth` mocked response:

```python
asyncio.get_event_loop().run_until_complete(alloc(mcp_mock))  # warm
async def verify(mcp):
    async with Client(mcp) as c:
        r = await c.call_tool("verify_bandwidth",
            {"src_ce": "ce3", "dst_ce": "ce4", "expected_mbps": 5.0})
        return json.loads(r.content[0].text)
verify_resp = asyncio.get_event_loop().run_until_complete(verify(mcp_mock))
verify_resp
```

- M: closing notes:
  - The repo does not ship a `.clab.yml`; the topology lives in upstream `srl-gnmi-bandwidth-poc`.
  - SDN_MOCK=false requires `srl-bandwidth` (already a dep) AND a running clab topology + reachable `pe1`/`pe2` over gNMI.
  - For the local mock path, this entire notebook runs offline.

- [ ] **Step 2: Verify** — nbformat check.
- [ ] **Step 3: Commit**

```bash
git add notebooks/07d_network_router_config.ipynb
git commit -m "feat(notebooks): 07d_network_router_config — mock vs real gNMI/tc/iperf3"
git push
```

---

## Phase 4: Final smoke test

### Task 35: Headless notebook execution check

**Files:**
- Modify: `tests/test_viz.py` (add a smoke runner) OR create a new `tests/test_notebooks_smoke.py`

- [ ] **Step 1: Add a marker-gated smoke test that executes notebooks**

Create `tests/test_notebooks_smoke.py`:

```python
"""Headless execution of the offline notebooks via nbclient.

Skip notebooks that require external services:
  - 01c, 01d, 05a (anvil + forge)
  - 06 (anvil + ollama)
  - 02b/02c/03c partial (build provider MCP — ok in-process, no chain calls)

This test is opt-in via NOTEBOOK_SMOKE=1 because it can take ~30s.
"""
from __future__ import annotations

import os
import pathlib
import pytest
import nbformat
from nbclient import NotebookClient

OFFLINE_OK = [
    "00_overview.ipynb",
    "01a_chain_contract_model.ipynb",
    "01b_chain_escrow_lifecycle.ipynb",
    "02a_mcp_concepts.ipynb",
    "02b_mcp_tool_catalog.ipynb",
    "02c_mcp_walkthrough.ipynb",
    "03a_a2a_concepts.ipynb",
    "03b_a2a_agent_cards.ipynb",
    "03c_a2a_walkthrough.ipynb",
    "04a_graph_state_schema.ipynb",
    "04b_graph_topology.ipynb",
    "04c_graph_llm_prompts.ipynb",
    "04d_graph_walkthrough.ipynb",
    "05a_inventory_and_expiry.ipynb",
    "07a_network_concepts.ipynb",
    "07b_network_topology.ipynb",
    "07c_network_before_after.ipynb",
    "07d_network_router_config.ipynb",
]


@pytest.mark.skipif(
    os.environ.get("NOTEBOOK_SMOKE") != "1",
    reason="set NOTEBOOK_SMOKE=1 to run notebook execution smoke test",
)
@pytest.mark.parametrize("name", OFFLINE_OK)
def test_notebook_executes(name):
    nb_path = pathlib.Path("notebooks") / name
    nb = nbformat.read(nb_path, as_version=4)
    NotebookClient(nb, timeout=120, kernel_name="python3").execute()
```

- [ ] **Step 2: Run the smoke test locally**

```bash
NOTEBOOK_SMOKE=1 uv run pytest tests/test_notebooks_smoke.py -v
```

Expected: PASS for every notebook in `OFFLINE_OK`. Failures here mean a notebook's code path is broken — open the failing notebook, fix, re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/test_notebooks_smoke.py
git commit -m "test(notebooks): opt-in headless execution smoke test"
git push
```

---

## Phase 5: Merge

### Task 36: Merge feat/pedagogical-notebooks into main

- [ ] **Step 1: Verify the branch is clean**

```bash
git status
```

Expected: clean working tree on `feat/pedagogical-notebooks`.

- [ ] **Step 2: Run full test suite once more**

```bash
uv run pytest tests/test_viz.py -v
NOTEBOOK_SMOKE=1 uv run pytest tests/test_notebooks_smoke.py -v
```

Expected: all green.

- [ ] **Step 3: Merge into main and delete the branch (per user CLAUDE.md)**

```bash
git checkout main
git merge --no-ff feat/pedagogical-notebooks
git push origin main
git branch -d feat/pedagogical-notebooks
git push origin --delete feat/pedagogical-notebooks
```

---

## Self-review notes

- **Spec coverage:** every numbered notebook in the spec maps to a task (Tasks 14–34). The `_viz.py` helper surface (9 renderers) is covered by Tasks 4–12. Cleanup is Task 13. Smoke test is Task 35. Merge is Task 36.
- **Type consistency:** every notebook task uses the same import line and same private-key constants. `render_chain_status` accepts a `web3` contract handle; the dict variant is `render_chain_status_from_dict`. `render_topology` accepts a `SlotPool`; the rows variant is `render_topology_from_rows`.
- **Network notebooks are LAST**, per the user's explicit instruction.
- **`06_end_to_end`** is the only notebook that requires Ollama; everything else is offline-runnable.
- **`01c`, `01d`, `05a` (partial), `06`** require `anvil` + `forge` on PATH; the smoke test skips them.
- **No placeholders.** Every code block contains executable code; every prose section names what it explains.

