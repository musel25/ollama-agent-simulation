# Dashboard UI Revamp — Design Spec

**Date:** 2026-04-20  
**Scope:** `consumer/ui.py` (full rewrite), `consumer/app.py` (system prompt fix only)

---

## Problem

1. **Multi-prompt to trigger contract** — the LLM re-queries the catalog on every message even when the user has already named a tier, requiring 2–3 prompts before it calls `request_agreement_on_chain`.
2. **UI doesn't show the A2A story** — the PoC's main value is two agents negotiating and executing a blockchain contract autonomously. The current UI buries that in a raw text log.

---

## What Changes

### 1. `consumer/app.py` — System prompt fix (minimal change)

**Root cause:** The system prompt says "Always query the catalog first", so the LLM calls `query_provider_catalog` on every turn regardless of intent. It also stops after `request_agreement_on_chain` and waits for the user instead of immediately calling `check_agreement_status`.

**Fix:** Replace the system prompt with one that:
- Skips catalog query if the user already named a tier (`small`, `medium`, `large`)
- Calls `request_agreement_on_chain` immediately when intent is clear
- Calls `check_agreement_status` automatically after requesting — no user confirmation needed
- Still calls catalog first only when the user is genuinely browsing/undecided

New system prompt (exact text):
```
You are a bandwidth procurement agent for a blockchain-based network service.

Tools available:
1. query_provider_catalog — fetch available packages and prices
2. request_agreement_on_chain — get a quote and lock ETH on-chain
3. check_agreement_status — verify settlement and get the active token

Rules:
- If the user names a specific tier (small, medium, or large), call request_agreement_on_chain IMMEDIATELY — do NOT query the catalog first.
- Only call query_provider_catalog when the user is browsing, undecided, or explicitly asks for options.
- After calling request_agreement_on_chain, ALWAYS call check_agreement_status in the same turn without waiting for the user.
- If check_agreement_status returns REQUESTED (not yet settled), tell the user to check again shortly.
- CRITICAL: Only report the EXACT agreementId and tokenId returned by the tools. NEVER guess or use example numbers.
```

No other changes to `consumer/app.py`.

---

### 2. `consumer/ui.py` — Full rewrite

#### Layout

```
┌─────────────┬─────────────────────────────────────────────┐
│   Sidebar   │  [Stepper: Catalog → Quote → On-chain → GW] │
│  Settings   ├──────────────────┬──────────────────────────┤
│  GW Check   │  🧑 Human        │  🤖↔🤖 A2A Transcript   │
│             │  (chat)          │  (timeline + catalog)    │
└─────────────┴──────────────────┴──────────────────────────┘
```

- **Sidebar** (190px): unchanged — model selector, gateway token check
- **Top stepper bar**: 4 pills — `Catalog › Quote › On-chain TX › Gateway` — derived from session state, lights up as steps complete
- **Left column (38%)**: Human chat — `st.chat_message` bubbles, minimal; a note "Human decides package — agents handle the rest"
- **Right column (62%)**: Split vertically:
  - **A2A Transcript** (scrollable, flex-grow): timeline phases (see below)
  - **Catalog strip** (pinned bottom, ~110px): 3 compact cards, always visible, selected package highlighted

#### Timeline — data model

Session state holds a cumulative list: `st.session_state.timeline: list[Phase]`

A `Phase` is a dict:
```python
{
  "step": "catalog" | "quote" | "onchain" | "gateway",
  "status": "done" | "active" | "pending",
  "turn": int,           # which chat turn produced this phase
  "messages": [          # A2A messages within this phase
    {"from": "consumer" | "provider" | "chain" | "gateway", "text": str}
  ],
  "summary": str,        # short human-readable result (e.g. "3 tiers available")
}
```

#### Timeline — parsing

After each `/chat` call the UI receives `log: list[dict]` where each entry has `{"from": "consumer"|"provider", "message": str}`. The UI parses these into phases by matching message patterns:

| Log entry pattern | Phase | `from` label |
|---|---|---|
| `"GET /catalog"` | catalog | consumer |
| provider response with `Mbps` lines | catalog | provider |
| `"POST /quote"` | quote | consumer |
| provider response with `agreementId=` | quote | provider |
| `"requestAgreement()"` | onchain | consumer |
| `"tx:"` in message | onchain | chain |
| `"Gateway response:"` | gateway | gateway |

New log entries from the current turn are appended to `st.session_state.timeline`; existing phases are not re-parsed (cumulative).

#### Timeline — rendering

Each phase renders as:
- **Phase header**: colored dot (green=done, blue=active, gray=pending) + step name + status badge + turn number
- **A2A thread**: indented, left-bordered, one bubble per message
  - `consumer` → dark indigo bubble, label "🛒 consumer agent"  
  - `provider` → dark blue bubble, label "🏪 provider agent"
  - `chain` → dark amber bubble, label "⛓ blockchain", monospace font
  - `gateway` → dark green bubble, label "🌐 gateway"
- **Pending phases**: grayed out, "Waiting…" text, no thread

#### Stepper bar — derivation

```python
def current_step(timeline):
    completed = {p["step"] for p in timeline if p["status"] == "done"}
    if "gateway" in completed: return "gateway"
    if "onchain" in completed: return "gateway"   # waiting for gateway
    if "quote"   in completed: return "onchain"
    if "catalog" in completed: return "quote"
    return "catalog"
```

Pill styles: done=green border, active=blue border + text, idle=gray.

#### Catalog strip — rendering

Same data as today (`/catalog_proxy`), rendered as 3 compact horizontal cards with a thin slot-fill bar. The package matching the active agreement's tier gets a green border highlight. Refresh button triggers `st.rerun()`.

#### State management

```python
UI_STATE_VERSION = 3   # bump to clear stale state on deploy
# keys: chat_history, timeline, active_tier
```

`active_tier` is set when parsing a `"POST /quote package_id=<tier>"` log entry. Used to highlight the catalog card.

---

## What Stays the Same

- All FastAPI endpoints in `consumer/app.py` (`/chat`, `/log`, `/catalog_proxy`, `/check_token`, `/address`)
- Provider, gateway, blockchain, smart contract logic — untouched
- Docker / docker-compose — untouched
- The `log` field in `ChatResponse` — still the source of truth; UI parses it client-side

---

## Out of Scope

- Real-time streaming during agent execution (Streamlit request/response model; post-turn display is sufficient)
- React migration
- Multiple concurrent sessions
