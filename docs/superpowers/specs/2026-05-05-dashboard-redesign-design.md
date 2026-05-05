# Dashboard Redesign — Two-Agent Symmetric Layout

**Date:** 2026-05-05
**Scope:** `consumer/ui.py` (full rewrite). No backend changes required; reuses existing `/chat`, `/log`, `/catalog_proxy`, `/check_token`, `/probe_proxy` endpoints, plus the agent-card and MCP-tool inventories already defined in code.

---

## Problem

The dashboard is the project's primary teaching surface and the main vehicle for paper figures. The current UI has three gaps:

1. **Agent Cards are invisible.** `consumer/agent_card.py` and `provider/agent_card.py` define the A2A identity (name, version, skills, endpoints) but the UI never surfaces them.
2. **MCP tools are invisible.** `consumer/mcp_server.py` (7 tools) and `provider/mcp_server.py` (8 tools) are the actual mechanism by which each agent acts, but the UI shows only post-hoc message bubbles, hiding the tool layer.
3. **The "agent-to-agent" framing is muted.** Two agents negotiating is the headline, but the current layout (chat | linear timeline) reads as request/response, not as peers exchanging messages.

A separate suggestion (numeric-input "operator" mockup) removed the human chat entirely. The chat must stay — the project's headline is "human-intent → autonomous agents."

---

## Audience and priorities

This dashboard serves two audiences with overlapping needs:

- **Paper / research artifact** — single screenshot must capture every protocol layer (chat → consumer agent + MCP tools → A2A wire → provider agent + MCP tools → on-chain → SDN/NFT). Density beats polish.
- **Teaching / tutorial** — labels, color-coded zones, and live-firing tool highlighting so a learner can map UI → code.

Live conference demo is **not** a priority; we don't optimize for narration or animation.

---

## Approach: two-agent symmetric layout

The two agents face each other across a central "A2A wire." Each agent gets a panel that surfaces its **Agent Card** (identity + skills) and its **MCP tools** (status-tagged, with live highlighting on the firing tool). Human chat sits below the consumer panel; on-chain events sit below the wire. NFT credential + SDN rule status spans the bottom.

```
┌──────────────────────────────────────────────────────────────────────┐
│ HEADER · status pill                                                 │
├──────────────────────────────────────────────────────────────────────┤
│ PIPELINE STRIP · 6 stages: discover → quote → lock → mint → swap → activate │
├─────────────────────┬─────────────────────────┬─────────────────────┤
│ 🛒 CONSUMER AGENT   │ ↔ A2A WIRE              │ 🏪 PROVIDER AGENT    │
│  agent card         │  message bubbles        │  agent card          │
│  · name, version    │  · consumer ← left      │  · name, version     │
│  · wallet, endpoint │  · provider → right     │  · wallet, endpoint  │
│  · skills (chips)   │  · on-chain markers     │  · skills (chips)    │
│  · 7 MCP tools      │    interleaved          │  · 8 MCP tools       │
│    (live status)    │                         │    (live status)     │
├─────────────────────┴───────────┬─────────────┴─────────────────────┤
│ 👤 HUMAN → CONSUMER chat        │ ⛓ ON-CHAIN EVENTS                  │
│  intent input + agent reply     │  tx hashes, gas, block             │
├─────────────────────────────────┴───────────────────────────────────┤
│ 🪪 NFT CREDENTIAL & SDN RULE — token id, owner, status, rule, qos   │
├──────────────────────────────────────────────────────────────────────┤
│ 📡 IPERF PROBE chart (collapsible — only visible if samples exist)   │
└──────────────────────────────────────────────────────────────────────┘
```

Sidebar keeps the Ollama model selector and the "Clear session" button. Gateway-token verification and iperf controls move out of the sidebar into the bottom NFT/probe row, since they only matter once a credential exists.

---

## Sections in detail

### 1. Header

- Title: `A2A Bandwidth Provisioning — autonomous agent demo`
- Subtitle: brief one-liner with project framing (Orange Labs · MCP-driven · atomic on-chain swap · SDN)
- Status pill (right): `IDLE` / `ACTIVE · turn N` / `COMPLETE` derived from `st.session_state.timeline`

### 2. Pipeline strip — 6 stages

Six tile-style cards in a row, replacing the current 4-pill stepper. Stages map to existing `STEP_ORDER` plus two new ones to match the actual MCP flow:

| # | Label | Done when |
|---|---|---|
| 01 | Discovery | `browse_catalog` MCP call returns |
| 02 | Quote | `request_quote` MCP call returns |
| 03 | Payment Lock | `lock_payment` returns OK |
| 04 | Atomic Swap | `complete_swap` event seen (or `await_settlement` returns OK) |
| 05 | Activation | `present_credential` / `verify_credential_ownership` returns ok |
| 06 | Consumption | iperf probe sample exists OR gateway response received |

State per stage: `done` (green), `active` (blue), `pending` (gray). Derived from existing inter-agent log + a new MCP-tool-call log (see §6).

### 3. Triptych: Consumer panel · A2A wire · Provider panel

`st.columns([1, 1.2, 1])` with custom HTML in each column.

#### 3a. Consumer Agent panel (left)

Single panel with three sub-sections:

**Agent Card section** — pulled from `build_consumer_agent_card()`:
- Name, version
- Description (truncated to one line, expandable)
- Wallet address (from `wallet_address` MCP tool, fetched once on page load)
- A2A endpoint URL
- Currently selected Ollama model

**A2A Skills** — chip row of `agent_card.skills[].name` (just `purchase_bandwidth`).

**MCP Tools** — vertical list. Each tool row: tool name + tag (`a2a` / `on-chain` / `local`) + status indicator. Status comes from a new MCP-tool-call log emitted by `consumer/app.py` (see *Data the UI needs that the backend doesn't provide today*). States:
- `idle` — gray
- `firing` — blue glow + "fire" border
- `done` — green checkmark

Tool list (from `consumer/mcp_server.py`):
| Tool | Tag |
|---|---|
| `wallet_address` | local |
| `sign_message` | local |
| `browse_catalog` | a2a |
| `request_quote` | a2a |
| `lock_payment` | on-chain |
| `await_settlement` | on-chain |
| `present_credential` | a2a |

#### 3b. A2A wire (center)

Reuses the current phase-bubble parser but with a left/right layout: consumer messages align left with indigo accent, provider messages align right with blue accent. On-chain markers (`requestAgreement`, `mint`, `deposit`) appear as full-width arrow rows interleaved chronologically. The phase status pills (`done`/`active`) are dropped here — that information moved to the pipeline strip — keeping the wire focused on payload content.

Header label of the wire: `Agent-to-Agent Wire · JSON-RPC over HTTP · N msgs`.

#### 3c. Provider Agent panel (right)

Mirror of 3a, pulling from `build_provider_agent_card()`.

**Agent Card section**:
- Name, version, description
- Wallet address (fetched once via `GET {PROVIDER_BASE_URL}/address` — endpoint already exists)
- A2A endpoint URL
- SDN mode (`mock` / `real`) — fetched from a new `GET /status` endpoint or hard-coded from env.

**A2A Skills**: `get_catalog`, `request_quote`, `activate`.

**MCP Tools** (from `provider/mcp_server.py`):
| Tool | Tag |
|---|---|
| `get_catalog` | read |
| `request_quote` | read |
| `verify_credential_ownership` | read |
| `mint_credential` | on-chain |
| `complete_swap` | on-chain |
| `allocate_bandwidth` | sdn |
| `revoke_bandwidth` | sdn |
| `verify_bandwidth` | sdn |

Provider-side MCP-tool firing status requires the provider to emit tool-call events (see *Data the UI needs that the backend doesn't provide today*, item 1).

### 4. Human → Consumer chat panel (bottom-left)

Same `st.chat_input` and `st.chat_message` calls as today. Wrapped in a panel with header `👤 Human → Consumer · intent · reasoning trace`. Below the input, an expander shows the agent's "thinking" traces (already provided by `/chat` response).

### 5. On-chain Events panel (bottom-right)

Replaces the current "chain" bubble interleaving. New view: monospace event list with one row per blockchain event, columns `event name · args · gas · block`. Events parsed by extending `_parse_log_to_phases` to also extract a flat list of chain-named events (already partially derivable from existing log strings like `"requestAgreement() sent."`).

If the existing log isn't structured enough, we add a new `/chain_events` endpoint to `consumer/app.py` that polls Anvil for events emitted by the escrow + NFT contracts since session start. Decision: **start with parsing the existing log**; add `/chain_events` only if parsing turns out lossy.

### 6. NFT credential & SDN rule strip (full-width)

Single horizontal card with five columns: `Token ID · Owner · Status · SDN Rule · QoS Class`. Populated from the existing `/check_token` endpoint, called automatically once the timeline shows the activation phase complete (instead of requiring the sidebar button click).

The "Verify token" button moves into this strip as a manual override. The "Run iperf3 probe" button also moves here.

### 7. iperf probe chart (full-width, collapsible)

Same as today but only rendered if `st.session_state.probe_samples` is non-empty. Wrapped in `st.expander("📡 Bandwidth probe", expanded=False)`.

---

## Data the UI needs that the backend doesn't provide today

Three new pieces:

1. **MCP tool-call event stream.** Today the inter-agent log captures `[MCP] tool_name(...)` strings on the consumer side, but provider-side tool calls are invisible (the provider's MCP server fires inside its own process). Add: provider-side log emission so each `@mcp.tool` invocation is logged to a shared file or in-process buffer that `consumer/app.py` aggregates and exposes via `/log`. The consumer-side log already contains MCP markers — we just need to parse them more strictly into `{tool, agent, status, ts}` records.

2. **Provider wallet address.** Add a `GET /address` route to `provider/app.py` (mirrors the consumer's existing one) that returns `_provider_account.address`.

3. **Provider SDN status.** Optional: add `GET /status` returning `{sdn_mock: bool, srl_available: bool}`. If we skip this, the panel reads the value from a Streamlit env var — fine for v1.

Items 2 and 3 are small additions. Item 1 is the biggest backend touch: it requires a logging shim around the FastMCP server in `provider/mcp_server.py` so tool calls show up in the inter-agent log alongside A2A messages.

---

## Streamlit-specific implementation notes

- All custom panels are rendered with `st.markdown(..., unsafe_allow_html=True)`, matching the current file's style. No JS, no custom components.
- The triptych uses `st.columns([1, 1.2, 1])`. Bottom row uses `st.columns([1, 1])`. Streamlit 1.37+ supports nested columns if needed; the design avoids them.
- A single `<style>` block is injected at the top of the script (CSS variables for the color palette) so per-panel HTML stays compact.
- Page rerun model: every `st.chat_input` submission triggers one `st.rerun()` after `/chat` responds. No background polling — same as today.
- iperf probe chart stays as `st.line_chart` inside the expander.
- Sidebar shrinks to: Ollama model selector + Clear session.

## Color palette (locked)

- Consumer accent: indigo `#818cf8`
- Provider accent: blue `#60a5fa`
- A2A wire / activation: green `#34d399`
- On-chain / blockchain: amber `#f59e0b`
- Done / success: green `#22c55e`
- Active / firing: blue `#3b82f6`
- Pending / idle: gray `#555`
- Background: `#0d0d12` (page) / `#13131c` (panels)

## Out of scope

- Animations or transitions on tool firing (just a static "fire" border + glow).
- Real-time push updates from the backend; we keep request/response + `st.rerun()`.
- Replacing Streamlit with a custom React frontend.
- Mobile responsiveness; the dashboard is laptop/projector-sized only.
- Multi-session view (one consumer, one provider, one user) — same as today.

## Risks

- **Streamlit HTML rendering quirks.** Heavy custom HTML can hit Streamlit's sanitizer or layout-collapse bugs. Mitigation: incremental — port section by section, verify each renders before moving on.
- **Provider MCP-tool logging requires a shim.** If the FastMCP API doesn't expose a clean tool-call hook, we may need to wrap each `@mcp.tool` definition manually. Acceptable cost.
- **Density on small screens.** At <1200 px width the triptych will wrap. Acceptable since the artifact target is paper/laptop, not mobile.

## Acceptance criteria

A run of "I need 50 Mbps for 30 minutes" via chat must show, in a single screenshot:
1. Both agent cards (name, version, wallet, skills) populated.
2. Consumer-side MCP tools showing `browse_catalog ✓`, `request_quote ✓`, `lock_payment ✓`, `await_settlement ✓`, `present_credential ✓`.
3. Provider-side MCP tools showing `get_catalog ✓`, `request_quote ✓`, `mint_credential ✓`, `complete_swap ✓`, `verify_credential_ownership ✓`, `allocate_bandwidth ✓`.
4. A2A wire with at least 6 message bubbles, alternating consumer-left / provider-right, plus on-chain marker rows interleaved.
5. On-chain events panel showing `AgreementRequested`, `Transfer` (mint), `Deposit` events with gas.
6. NFT/SDN strip populated with token id, status `ACTIVE`, SDN rule string.
7. Pipeline strip with all 6 stages green.
