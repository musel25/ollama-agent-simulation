# Dashboard Redesign — Two-Agent Symmetric Layout

**Date:** 2026-05-05
**Scope:** `consumer/ui.py` (full rewrite) + small additions to `provider/app.py` and `provider/mcp_server.py` (tool-call logging) and to `consumer/app.py` (cumulative log + new `/chain_events` endpoint). Reuses existing `/chat`, `/catalog_proxy`, `/check_token`, `/probe_proxy`, `/address` endpoints, plus the agent-card and MCP-tool inventories already defined in code.

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
- **Teaching / tutorial** — labels, color-coded zones, and per-turn tool-call highlighting (which MCP tools just fired) so a learner can map UI → code.

Live conference demo is **not** a priority; we don't optimize for narration or animation.

---

## Approach: two-agent symmetric layout

The two agents face each other across a central "A2A wire." Each agent gets a panel that surfaces its **Agent Card** (identity + skills) and its **MCP tools** (status-tagged: `not yet fired` / `fired this turn` / `fired previously`). Human chat sits below the consumer panel; on-chain events sit below the wire. NFT credential + SDN rule status spans the bottom.

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
- Status pill (right): one of `IDLE` (no turns yet) / `BUSY · turn N` (a `/chat` call is in flight; Streamlit shows the spinner) / `READY · turn N` (last turn completed). Derived from `st.session_state.turn` and a `running` flag set around the `httpx.post` call. There is no real-time mid-turn streaming — Streamlit's request/response model means the pill only flips once per turn.

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

**MCP Tools** — vertical list. Each tool row: tool name + tag (`a2a` / `on-chain` / `local`) + status indicator. Streamlit's `/chat` is fully request/response (the LangGraph runs to completion before returning), so there is no real "live firing" state. Statuses are turn-relative:
- `not yet fired` — gray, never seen in the inter-agent log
- `fired this turn` — blue accent + green checkmark, last turn it appeared in equals `st.session_state.turn`
- `fired previously` — dim green checkmark, fired in an earlier turn

The consumer-side log already contains `[MCP] tool_name(...)` markers (emitted by `consumer/graph.py:_log_call`), so no backend changes are needed for the consumer panel — the UI just parses those markers and tags them with the current turn.

Tool list (from `consumer/mcp_server.py`):
| Tool | Tag | Notes |
|---|---|---|
| `browse_catalog` | a2a | fires from `browse_node` and `catalog_info_node` |
| `request_quote` | a2a | fires from `quote_node` |
| `lock_payment` | on-chain | fires from `lock_node` |
| `await_settlement` | on-chain | fires from `settle_node` |
| `present_credential` | a2a | fires from `present_node` |
| `wallet_address` | local | **ambient** — used by `/address` endpoint and inside other tools, never as a graph-driven MCP call. Shown for completeness, never lights up via chat. |
| `sign_message` | local | **ambient** — `present_credential` signs inline rather than calling this tool. Shown for completeness. |

The "ambient" tools render with a dotted border and a small "ambient" tag so users understand they exist but don't fire in the buy flow.

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
| Tool | Tag | Notes |
|---|---|---|
| `get_catalog` | read | fires via A2A `BandwidthProviderExecutor._handle_catalog` |
| `request_quote` | read | fires via A2A `BandwidthProviderExecutor._handle_quote` |
| `verify_credential_ownership` | read | fires via A2A `BandwidthProviderExecutor._handle_activate` |
| `mint_credential` | on-chain | fires from event listener `_handle_agreement` after `AgreementRequested` |
| `complete_swap` | on-chain | fires from event listener `_handle_agreement` |
| `allocate_bandwidth` | sdn | fires via A2A `_handle_activate` |
| `verify_bandwidth` | sdn | fires from `/probe` endpoint |
| `revoke_bandwidth` | sdn | **expiry-driven** — fires only from `provider/expiry.py:expiry_sweep_loop`, never in the buy flow. Shown with dotted border + `expiry` tag. |

Provider-side MCP-tool firing status requires the provider to emit tool-call events (see *Data the UI needs that the backend doesn't provide today*, item 1).

### 4. Human → Consumer chat panel (bottom-left)

Same `st.chat_input` and `st.chat_message` calls as today. Wrapped in a panel with header `👤 Human → Consumer · intent · reasoning trace`. Below the input, an expander shows the agent's "thinking" traces (already provided by `/chat` response).

### 5. On-chain Events panel (bottom-right)

Replaces the current "chain" bubble interleaving. New view: monospace event list with one row per blockchain event, columns `event name · args · gas · block`.

**Source of truth:** the inter-agent log carries hints (`requestAgreement() sent. tx=…`, `Agreement ACTIVE. tokenId=…`) but lacks gas, block number, and the `Deposit` event entirely. Add a small `GET /chain_events?since_block=N` endpoint to `consumer/app.py` that uses `escrow.events.AgreementRequested.get_logs` + `escrow.events.Deposit.get_logs` + `nft.events.Transfer.get_logs` (all already exposed via `shared.contracts`). Returns `[{event, args, gas, block, txHash}]`. The dashboard polls this once after each chat turn returns and merges into `st.session_state.chain_events` (cumulative across turns; never reset until "Clear session").

**Cumulative state — important.** `inter_agent_log` is cleared at the top of every `/chat` call (`consumer/app.py:run_consumer`), so anything sourced from it must be accumulated client-side in `st.session_state`. The existing `_merge_timeline` already does this for the A2A wire; we add `chain_events` next to it.

### 6. NFT credential & SDN rule strip (full-width)

Single horizontal card with five columns: `Token ID · Owner · Status · SDN Rule · QoS Class`. Populated from the existing `/check_token` endpoint, called automatically once the timeline shows the activation phase complete (instead of requiring the sidebar button click).

The "Verify token" button moves into this strip as a manual override. The "Run iperf3 probe" button also moves here.

### 7. iperf probe chart (full-width, collapsible)

Same as today but only rendered if `st.session_state.probe_samples` is non-empty. Wrapped in `st.expander("📡 Bandwidth probe", expanded=False)`.

---

## Data the UI needs that the backend doesn't provide today

Three pieces (one is bigger than I first estimated, two are trivial).

### 1. Provider-side MCP tool-call log — bigger than expected

The provider fires 6 of its 8 MCP tools during a buy turn, across two execution paths:
- **A2A path** (`BandwidthProviderExecutor`): `get_catalog`, `request_quote`, `verify_credential_ownership`, `allocate_bandwidth`
- **Event-listener path** (`provider/app.py:_handle_agreement`): `mint_credential`, `complete_swap`
- **`/probe` path**: `verify_bandwidth`
- **Expiry path** (out of scope): `revoke_bandwidth`

None of these emit anything visible to the consumer's `/log`. Plan:

a. **Add a small in-process deque** in `provider/app.py` (e.g. `tool_call_log: deque = deque(maxlen=500)`) that stores `{tool, ts, args_summary, status}` entries.

b. **Wrap each `@mcp.tool` definition in `provider/mcp_server.py`** (or — simpler — override `mcp.tool()` to install a logging hook). Each invocation appends one entry on entry and updates the same entry on return. FastMCP exposes a single `Client(mcp).call_tool(...)` path so all four invocation sites flow through the same hook.

c. **Add `GET /tool_log` to `provider/app.py`** returning the deque as JSON. Optional `?since_ts=…` query param for incremental polling.

d. **Dashboard polls `provider:8002/tool_log`** once after each chat turn returns (NOT during — the spinner is already covering the user-visible window). Note timing nuance: `mint_credential` and `complete_swap` fire from the async event listener and may complete a few hundred ms after `await_settlement` returns OK on the consumer side. Since `await_settlement` only returns OK once `complete_swap` has landed and the agreement is `ACTIVE`, by the time `/chat` returns those tools have always already fired. So a single post-chat poll is sufficient.

e. **Dashboard merges provider tool log into `st.session_state.provider_tool_log`** with the same per-turn cumulative pattern as the consumer log.

### 2. Cumulative consumer log

`consumer/app.py:run_consumer` calls `inter_agent_log.clear()` at the top of every chat turn. The UI already side-steps this for the A2A wire by accumulating into `st.session_state.timeline`. We extend the same pattern to:
- `st.session_state.consumer_tool_log` — parsed `[MCP] tool_name(...)` markers
- `st.session_state.provider_tool_log` — from `/tool_log`
- `st.session_state.chain_events` — from `/chain_events` (see §5)

No backend change required for this — purely a UI accumulator.

### 3. Provider SDN status (trivial)

Optional `GET /status` returning `{sdn_mock: bool, srl_available: bool}`. If we skip it, the panel reads `SDN_MOCK` from the env on the dashboard side via `os.environ.get`. **Decision: skip the endpoint, read the env var.** One less surface to maintain.

Note: provider `/address` is already implemented (`provider/app.py:195`); my earlier draft incorrectly listed it as a needed addition.

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
- Fired this turn: blue `#3b82f6`
- Not yet fired / pending: gray `#555`
- Ambient (defined but not in buy flow): dotted gray border
- Background: `#0d0d12` (page) / `#13131c` (panels)

## Out of scope

- Animations or transitions on tool firing (just a static accent border on tools that fired this turn).
- Real-time push updates from the backend; we keep request/response + `st.rerun()`.
- Streaming the LangGraph state mid-turn back to the UI. The graph runs to completion inside `/chat`, then returns. If we ever want true mid-turn highlighting we'd need SSE or a polling loop on `consumer:8001/log` while the spinner is up.
- Replacing Streamlit with a custom React frontend.
- Mobile responsiveness; the dashboard is laptop/projector-sized only.
- Multi-session view (one consumer, one provider, one user) — same as today.

## Risks

- **Streamlit HTML rendering quirks.** Heavy custom HTML can hit Streamlit's sanitizer or layout-collapse bugs. Mitigation: incremental — port section by section, verify each renders before moving on.
- **Provider MCP-tool logging requires a shim.** If FastMCP doesn't expose a clean middleware hook, we wrap each `@mcp.tool` definition manually (or wrap once via a decorator that re-decorates the existing tools). Acceptable cost.
- **Tests reference `consumer/graph.py` MCP tool wrappers via monkey-patching** (`tests/test_consumer_graph.py:25`). If we reorganize tool plumbing in graph.py we'll break tests; the plan is to add tool-call logging *only* on the provider side, leaving the consumer graph and its tests untouched.
- **Density on small screens.** At <1200 px width the triptych will wrap. Acceptable since the artifact target is paper/laptop, not mobile.
- **Event-listener timing.** `mint_credential` / `complete_swap` fire from `provider/app.py:_event_listener` ~1-3s after `requestAgreement` is observed on chain. Because the consumer's `await_settlement` only returns OK once status is ACTIVE (which requires `complete_swap`), by the time `/chat` returns these tools have always landed. If the listener ever moves to a slower polling interval, the dashboard would need a short retry on `/tool_log` — note this in the implementation plan.

## Acceptance criteria

A run of "I need 5 Mbps for 10 minutes" via chat must show, in a single screenshot:
1. Both agent cards (name, version, wallet, skills, A2A endpoint) populated.
2. Consumer-side MCP tools showing `browse_catalog ✓`, `request_quote ✓`, `lock_payment ✓`, `await_settlement ✓`, `present_credential ✓` (all "fired this turn"). The two ambient tools (`wallet_address`, `sign_message`) shown but unlit.
3. Provider-side MCP tools showing `get_catalog ✓`, `request_quote ✓`, `verify_credential_ownership ✓`, `mint_credential ✓`, `complete_swap ✓`, `allocate_bandwidth ✓` (all fired this turn). `verify_bandwidth` only lights up if iperf probe was run; `revoke_bandwidth` stays unlit.
4. A2A wire with at least 6 message bubbles, alternating consumer-left / provider-right, plus on-chain marker rows interleaved.
5. On-chain events panel showing at least `AgreementRequested`, `Transfer` (mint, NFT), `Deposit` events with their gas + tx hash + block.
6. NFT/SDN strip populated with token id, owner, status `ACTIVE`, SDN rule string, QoS class.
7. Pipeline strip with all 6 stages green.
