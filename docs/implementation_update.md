# Implementation Update Roadmap

> What needs to be built to match the target architecture described in `paper/main.tex`.
> Smart contracts (`BandwidthEscrow`, `BandwidthNFT`) are **not** on this list — they already match the paper.

---

## IU-1 — Real A2A task messaging (inter-agent negotiation)

**What the paper says:**
> "A2A is the inter-agent protocol: the consumer sends a structured task message carrying its intent; the provider responds with a concrete offer."

**What exists:**
Both agents serve `/.well-known/agent.json` (A2A Agent Cards — discovery only). No A2A task messages are sent. The consumer calls the provider's MCP server directly without any A2A negotiation round.

**What to build:**
- Consumer: before calling `get_catalog` via MCP, send an A2A `tasks/send` message to the provider with structured intent: `{desired_mbps, max_price_wei, duration_seconds}`.
- Provider: handle incoming A2A tasks, evaluate the catalog, and respond with an A2A offer payload: `{packageId, priceWei, bandwidthMbps, durationSeconds, agreementId}`.
- After the A2A offer exchange, the consumer proceeds with MCP tool calls (or uses the offer data directly to call `execute_agreement`).

**Files to touch:**
- `consumer/app.py` — add `_send_a2a_task()` before the MCP tool-call loop
- `provider/app.py` — add `POST /a2a/tasks/send` endpoint that evaluates intent and returns offer
- New `consumer/a2a_client.py` — async A2A task client
- New `provider/a2a_handler.py` — A2A task handler logic

**Why this matters:** This is the single largest gap between paper and implementation. Without it, "A2A" in the system is only a static JSON file.

---

## IU-2 — Consumer MCP server (expose on-chain tools via MCP)

**What the paper says:**
> "The consumer's MCP server exposes on-chain tools: wallet signing, escrow deposit (`requestAgreement`), and credential presentation to the gateway."

**What exists:**
`execute_agreement` and `check_agreement_status` are plain Python functions in `LOCAL_TOOL_MAP` inside `consumer/app.py`. They are injected directly into Ollama's tool schema — they are not served via any MCP server.

**What to build:**
- New `consumer/mcp_server.py` — FastMCP server wrapping `execute_agreement` and `check_agreement_status` as MCP tools.
- Mount it in `consumer/app.py` (same pattern as `provider/mcp_server.py`).
- Update `AGENT_CARD` to declare `mcp_endpoint: "/mcp"`.
- The LLM reasoning loop fetches its own tool schemas from its local MCP server (same `fastmcp.Client` pattern as the provider).

**Files to touch:**
- New: `consumer/mcp_server.py`
- Modify: `consumer/app.py` — mount MCP server, fetch local tools via MCP client

**Note:** This does not change behavior — the tools do the same thing. It makes the paper's "consumer MCP toolset" description accurate.

---

## IU-3 — Expand provider MCP server (expose event-handling tools)

**What the paper says:**
> "The provider's MCP server exposes service tools: catalog lookup, quote generation, NFT minting, and deposit for the atomic swap."

**What exists:**
Provider MCP server (`provider/mcp_server.py`) exposes only `get_catalog` and `request_quote`. NFT minting and `deposit` are done internally by the event listener — never accessible via MCP.

**What to build:**
- Add `mint_nft(agreement_id)` and `complete_swap(agreement_id, token_id)` as MCP tools on the provider server.
- These would be called by the provider agent's LLM reasoning loop (triggered after it receives the A2A task and decides to fulfill the agreement), rather than by the blockchain event listener alone.
- Keep the event listener as a fallback/alternative path.

**Files to touch:**
- Modify: `provider/mcp_server.py` — add `mint_nft`, `complete_swap` tools
- Modify: `provider/app.py` — provider agent LLM loop calls these tools after A2A task receipt

**Why this matters:** Currently the provider has no LLM reasoning loop — it's purely event-driven. Adding one (even minimal) makes it a true "provider agent" in the paper's sense.

---

## IU-4 — SDN command placeholder in gateway

**What the paper says:**
> "The gateway verifies on-chain NFT ownership and translates service parameters into an SDN controller command — a QoS flow rule."

**What exists:**
`provider/gateway.py` verifies NFT ownership and returns service metadata. No SDN command is issued or logged.

**What to build:**
After ownership verification, log the SDN command that would be issued:

```python
log.info(
    f"[SDN] FLOW_MOD: match=dst:{signer} "
    f"action=set_bandwidth:{bandwidth_mbps}Mbps "
    f"duration:{duration_seconds}s endpoint:{endpoint}"
)
```

Also return a `sdn_command` field in the response JSON so it appears in the inter-agent log and UI.

**Files to touch:**
- Modify: `provider/gateway.py` — add `logging`, add log line + response field

**Effort:** ~10 minutes.

---

## IU-5 — Expose NFT mint + swap events in inter-agent log

**What the paper says:**
Six workflow stages including Credential Issuance (stage 3) and Swap (stage 4).

**What exists:**
The UI shows four phases: `catalog`, `quote`, `onchain`, `gateway`. Stages 3 and 4 happen in `provider/app.py:_handle_agreement()` but are never logged to `inter_agent_log` — they are invisible in the UI.

**What to build:**
- Add a `provider_event_log: list[dict]` in `provider/app.py` that records NFT mint and swap events with tx hashes and gas used.
- Add `GET /events` endpoint on the provider.
- Consumer UI polls `/events` after the on-chain phase to show stages 3 and 4 in the transcript.
- Add `credential_issuance` and `swap` to the UI stepper.

**Files to touch:**
- Modify: `provider/app.py` — add `provider_event_log`, append mint/swap events, add `/events` endpoint
- Modify: `consumer/ui.py` — poll provider `/events`, add two new stepper phases

---

## IU-6 — QoS class and offer expiration in catalog

**What the paper says:**
> "Each catalog entry specifies bandwidth, duration, price, QoS class, and available slot count. A quote response includes a 60-second TTL."

**What exists:**
Catalog items: `{packageId, mbps, durationSeconds, priceWei, availableSlots}`. Quote responses: `{agreementId, priceWei, bandwidthMbps, durationSeconds}`. No `qosClass`, no `quoteTtlSeconds`.

**What to build:**
- Add `qosClass` to each CATALOG entry (`"best-effort"`, `"assured-forwarding"`, `"expedited-forwarding"`).
- Add `activationEndpoint` to each CATALOG entry (currently only in the minted NFT).
- Add `quoteTtlSeconds: 60` to quote responses.

**Files to touch:**
- Modify: `provider/catalog.py` — add fields to CATALOG list and `make_quote` return value
- Modify: `provider/mcp_server.py` — update docstring

**Effort:** ~15 minutes.

---

## IU-7 — Per-stage timing and gas instrumentation

**What the paper says:**
> "Indicative latency and gas costs for one successful run."

**What exists:**
No timing instrumentation. Gas used is available in transaction receipts but not logged or surfaced.

**What to build:**
- In `consumer/app.py:run_consumer()`: record `time.perf_counter()` before/after each stage (MCP discovery, A2A exchange, each tool call).
- In `provider/app.py:_handle_agreement()`: log `receipt["gasUsed"]` for mint, approve, deposit.
- Append a `[TIMING]` entry to `inter_agent_log` at end of `run_consumer`.
- Optionally: expose a `/metrics` endpoint on the consumer returning last-run timing breakdown.

**Files to touch:**
- Modify: `consumer/app.py`
- Modify: `provider/app.py`

---

## Priority Order

| Priority | Item | Effort | Paper alignment impact |
|----------|------|--------|----------------------|
| **1** | IU-1 Real A2A task messaging | Large | Critical — closes the biggest gap |
| **2** | IU-3 Expand provider MCP + provider LLM loop | Medium | High — makes provider a true agent |
| **3** | IU-2 Consumer MCP server | Small | Medium — matches paper's toolset description |
| **4** | IU-5 Mint/swap in UI transcript | Small | Medium — makes all 6 stages visible |
| **5** | IU-4 SDN command placeholder | Tiny | Low — one log line |
| **6** | IU-6 QoS class in catalog | Tiny | Low — data field additions |
| **7** | IU-7 Timing + gas instrumentation | Small | Low — fills evaluation section |

---

## What Does NOT Need to Change

- `contracts/` — `BandwidthEscrow.sol` and `BandwidthNFT.sol` accurately implement the paper's payment and authorization primitives. No changes needed.
- `shared/contracts.py` — correctly loads deployed addresses and ABIs.
- `provider/gateway.py` core logic — NFT ownership verification via `ownerOf()` is correct. Only the SDN log line (IU-4) is missing.
- `consumer/mcp_client.py` — MCP client utilities are correct and will be reused for IU-2.
- `provider/catalog.py` inventory logic — file-locking, slot tracking, and lease expiration are correct.
- Docker/Makefile setup — deployment orchestration is not affected by any of the above.
