# Pedagogical Notebook Series — Design

**Date:** 2026-05-06
**Status:** Approved (pending user review of this file)
**Author:** Claude (brainstorming session)

## Goal

Replace the existing 5 terse notebooks (`01_chain`, `02_mcp`, `03_a2a`,
`04_consumer_graph`, `05_end_to_end`) with a 21-notebook pedagogical
series that exposes every layer's internals through prose, rendered
diagrams, JSON inspectors, state snapshots, and (for the network layer)
a visual before/after of the consumer's bandwidth.

The current notebooks are code-first and skip the "why". The new series
is concept-first: each layer gets at least one concepts notebook (mostly
prose + diagrams) and one walkthrough notebook (hands-on). The chain
layer earns three concept notebooks because the smart-contract layer
has the most internals to unpack.

## Replace strategy

The five existing notebooks at `notebooks/*.ipynb` are deleted. The new
series lives at the same path. The README is rewritten to point at the
new series. The existing `05_end_to_end.ipynb` is the structural seed
for the new `06_end_to_end.ipynb` (same flow — anvil + deploy + provider
FastAPI + consumer FastAPI + real Ollama — but rendered with the new
helpers).

## Final notebook list (21 files)

```
00_overview                    Architecture map; the 6-stage flow; who talks to whom.
                               Reuses paper/diagrams/d1_overview_hub.svg and
                               d3_architecture_stack.svg as starting visuals;
                               adds a layer-by-layer pointer to the rest of the series.

# ── Chain (Solidity + Anvil + Foundry) ────────────────────────────
01a_chain_contract_model       BandwidthEscrow.Agreement struct + Status enum (5 values:
                               NONE/REQUESTED/ACTIVE/CLOSED/CANCELLED). BandwidthNFT
                               TokenMetadata (agreementId, mbps, duration, startTime,
                               endpoint). Why ERC-721 for the credential. Why the
                               escrow holds both the ETH and (briefly) the NFT.
                               Custom errors. Mostly prose + diagrams; no code execution.

01b_chain_escrow_lifecycle     State machine diagram (mermaid stateDiagram-v2):
                               NONE → REQUESTED → ACTIVE; REQUESTED → CANCELLED.
                               Per transition: which function, which actor, which
                               event, the CEI ordering inside deposit() (status
                               update BEFORE the ETH transfer — explained as the
                               reentrancy-safe pattern). Cancel paths: consumer
                               anytime, anyone after deadline. Mostly prose.

01c_chain_nft_minting          mint() params bind (agreementId, mbps, duration,
                               endpoint) into TokenMetadata at startTime. Why
                               metadata is on-chain not IPFS. Owner-only mint.
                               getTokenMetadata read path. Renders one minted NFT
                               as a "ticket card" with all 5 fields. Light code:
                               deploy + mint one token, render its metadata.

01d_chain_walkthrough          Hands-on: spawn anvil, deploy, walk one full trade.
                               At every step render: Agreement struct as a styled
                               table, Status as a colored pill, balances of consumer
                               and provider, gas used per tx, decoded events. Final
                               cell: a full event timeline (AgreementRequested →
                               Transfer (mint) → Transfer (escrow→consumer) →
                               AgreementActive) as an HTML table.

# ── MCP (Model Context Protocol via FastMCP) ──────────────────────
02a_mcp_concepts               What MCP is; FastMCP server model; tools vs
                               resources vs prompts; in-process vs stdio vs HTTP
                               transport. Why we use FastMCP for both agents and
                               also expose it via /mcp on the FastAPI app. Mostly
                               prose + a request-flow diagram.

02b_mcp_tool_catalog           Build provider's MCP server in-process. Render the
                               full tool catalog as an HTML card grid: name,
                               description, JSON Schema (input/output) per tool.
                               This is the "MCP viewer" the user asked for. Walks
                               through all 8 provider tools (get_catalog,
                               request_quote, verify_credential_ownership,
                               mint_credential, complete_swap, allocate_bandwidth,
                               revoke_bandwidth, verify_bandwidth) plus a
                               separate section for the 7 consumer tools.

02c_mcp_walkthrough            Call read-only tools through fastmcp.Client. Show
                               the raw request → raw response JSON for each call.
                               Watch tool_log fill up. Demonstrate the in-process
                               MCPClient(mcp) handle vs imagining an HTTP transport.

# ── A2A (Agent-to-Agent protocol via a2a-sdk) ─────────────────────
03a_a2a_concepts               What A2A is; AgentCard + skills + capabilities;
                               protobuf payloads (Message → Part → Value/Struct);
                               EventQueue + RequestContext executor pattern;
                               TaskArtifactUpdateEvent + TaskStatusUpdateEvent
                               flow. JSONRPC binding at /a2a. Sequence diagram of
                               one A2A call.

03b_a2a_agent_cards            Render both agent cards (provider + consumer) as
                               styled HTML cards: name, version, description,
                               capabilities, supported_interfaces (URL +
                               protocol_binding), skills (id, name, description,
                               tags, examples). Exactly what a peer agent
                               discovers via /.well-known/agent-card.json.

03c_a2a_walkthrough            Drive BandwidthProviderExecutor in-process. Three
                               actions (get_catalog, request_quote, activate),
                               each shown as a sequence diagram + the raw
                               protobuf payload (rendered as JSON). Show how
                               action → MCP tool dispatch happens inside
                               _handle_catalog/_handle_quote/_handle_activate.
                               A FakeQueue captures events; we render every
                               TaskArtifactUpdateEvent and TaskStatusUpdateEvent.

# ── Consumer LangGraph ────────────────────────────────────────────
04a_graph_state_schema         WorkflowState TypedDict field-by-field. Which node
                               writes which field. Reducer behavior: log and
                               thinking are append-mutated by every node. Why
                               the pattern is "write once, read many" for tier/
                               agreement_id/token_id. Pure prose + a state-
                               schema diagram.

04b_graph_topology             Render graph.get_graph().draw_mermaid_png() inline
                               (PNG via mermaid.ink). Annotate every node:
                               purpose, what it reads, what it writes, which
                               tools it calls. Highlight the only conditional
                               loop (settle_node retry up to 3 times) and the
                               error_node fan-in. Mostly prose + the rendered
                               PNG.

04c_graph_llm_prompts          The two LLM-facing nodes verbatim:
                               1. pick_tier prompt template ("Reply with EXACTLY
                                  ONE WORD…"). Why one word; deterministic
                                  fallback path (deterministic_tier_pick) when
                                  the LLM disobeys. Show three example LLM
                                  outputs (good, bad, weird) and how each is
                                  parsed.
                               2. summary prompt — informational only; the
                                  actual final_response is template-built, not
                                  LLM-built. Why we still call the LLM
                                  (pedagogical, demonstrates dual use).
                               Light code: invoke each prompt against a stub LLM.

04d_graph_walkthrough          Stream the graph node-by-node with stubbed tools
                               and a stubbed LLM. After each node yields, render:
                               (a) the keys it added to state, (b) a JSON diff
                               vs. previous state, (c) the most recent log
                               entry. Optional ipywidgets ToggleButton ladder to
                               step manually. Final state inspection: chosen
                               tier, agreement_id, token_id, log, thinking.

# ── Provider inventory + chain bridging ───────────────────────────
05a_inventory_and_expiry       SlotPool (file-backed JSONL with fcntl.LOCK_EX).
                               Per-tier slot reservations. Quote TTL (300s).
                               Expiry sweep loop (every 30s) revoking SDN +
                               releasing slots. Event listener loop polling
                               AgreementRequested → mint_credential →
                               complete_swap. Walkthrough: reserve a slot,
                               manually expire it (mtime hack), watch the sweep
                               release it. Renders inventory.txt as a live HTML
                               table at each step.

# ── End-to-end synthesis ──────────────────────────────────────────
06_end_to_end                  The whole flow in-process: anvil + deploy +
                               provider FastAPI + consumer FastAPI + real
                               Ollama. POST /chat with "I need 5 Mbps for 10
                               minutes" and watch the negotiation. Renders:
                               (a) a sequence diagram across all four actors
                               (consumer-graph ↔ A2A ↔ provider-executor ↔
                               chain ↔ Ollama), (b) the conversation log as
                               chat bubbles, (c) the on-chain event timeline,
                               (d) inventory state before vs after.

# ── Network / SDN (last block per user) ───────────────────────────
07a_network_concepts           What SDN_MOCK gates. Why the provider has three
                               extra MCP tools (allocate_bandwidth,
                               revoke_bandwidth, verify_bandwidth) the consumer
                               never sees. Mental model: gNMI policer at PE +
                               tc tbf shaping on CE + iperf3 verify probe
                               between CE peers. Why endpoint =
                               clab://<pe>/<subinterface>. The srl-bandwidth
                               package as the real-SDN backend; the mock as
                               the in-process shim. Mostly prose + a layered
                               diagram.

07b_network_topology           Render the topology inline (mermaid graph LR):
                               consumer (Ethereum address) → ce1/ce3/ce2 →
                               pe1/pe2 → core. Source the diagram from the
                               actual inventory.txt slot list, so this notebook
                               will visually update if inventory changes. Show
                               which (pe, subinterface, ce) belongs to which
                               tier. Cross-reference CE_PEER from
                               provider/app.py so the iperf3 verify direction
                               is visible.

07c_network_before_after       The visual the user explicitly asked for.
                               BEFORE: render the topology with the consumer
                               node grayed out and the consumer↔ce1 edge
                               labeled "0 Mbps" in red. Run the negotiation
                               (reuse 06's flow but with SDN_MOCK=true).
                               AFTER: re-render with the consumer node lit
                               green, the edge labeled "5 Mbps" in green, and
                               the allocated (pe, subinterface) badge attached
                               to the active link. Driven by an
                               ipywidgets.ToggleButtons("before"/"after"); both
                               states are pre-rendered so the toggle is
                               instant. Falls back to two cells without
                               widgets.

07d_network_router_config      Side-by-side: SDN_MOCK=true response (the no-op
                               JSON shim) vs SDN_MOCK=false response (the real
                               srl_bandwidth.allocate_bandwidth call against a
                               live clab). Render the actual gNMI Set request
                               body that would go to the PE (pulled from the
                               srl-bandwidth package's templates). Render the
                               tc tbf command applied on the CE. Render the
                               iperf3 UDP probe command + a sample result
                               table from verify_bandwidth. Notes which parts
                               require an external clab topology (the repo
                               does NOT ship the .clab.yml — that's an
                               operator concern; we link to the upstream
                               srl-gnmi-bandwidth-poc repo).
```

## Cross-cutting tech stack

A small shared helper module `notebooks/_viz.py` carries every renderer
so each notebook stays short and consistent:

```
notebooks/_viz.py
├── render_mermaid(src: str) -> IPython.display.Image
│       POST to mermaid.ink (matches LangGraph's draw_mermaid_png()).
│       Falls back to a fenced markdown code block if the request fails,
│       so notebooks still run offline.
├── render_agent_card(card_dict: dict) -> IPython.display.HTML
│       Skills as bullets, capabilities as badges, interfaces as table.
├── render_mcp_tools(mcp: FastMCP) -> IPython.display.HTML
│       Reads mcp._local_provider._components, renders each tool as a
│       card with name + description + JSON Schema (input/output).
├── render_state(state: dict, prev: dict | None) -> IPython.display.HTML
│       Pretty-printed JSON; if prev given, highlights added/changed
│       keys in green and removed keys in red.
├── render_chat_log(log: list[dict]) -> IPython.display.HTML
│       Bubble-style; color-coded by `from` (consumer / provider /
│       system).
├── render_chain_status(escrow, agreement_id: int) -> IPython.display.HTML
│       Agreement struct as a 2-column table; status as a colored pill
│       (REQUESTED=yellow, ACTIVE=green, CANCELLED=red).
├── render_event_timeline(events: list[dict]) -> IPython.display.HTML
│       Sortable table: block | event | args | gas | txHash.
├── render_topology(slot_pool, active_agreement_ids: set[int],
│                   ce_peer: dict) -> IPython.display.Image
│       Mermaid graph LR built from the live slot list + CE peer map.
│       Edges with active agreements are highlighted green with the
│       Mbps label; idle edges are gray.
└── toggle_before_after(before_html, after_html) -> ipywidgets.VBox
        ipywidgets.ToggleButtons swapping between two pre-rendered
        widgets; on import failure, falls back to displaying both
        stacked.
```

The helper is imported at the top of every notebook:
```python
from notebooks._viz import (render_mermaid, render_agent_card,
                            render_mcp_tools, render_state,
                            render_chat_log, render_chain_status,
                            render_event_timeline, render_topology,
                            toggle_before_after)
```

External rendering dep: `ipywidgets>=8` added to `[dependency-groups]
dev` in `pyproject.toml`. Mermaid rendering uses HTTP to `mermaid.ink`
(no new package). Both the MCP-tool view and agent-card view are
hand-rolled HTML; no JS framework added.

## Per-notebook structure

Every notebook follows the same skeleton:

1. **Title + one-paragraph hook** (markdown) — what you'll learn,
   prerequisites, est. read time.
2. **Concepts** (markdown + diagrams) — the theory. Concept notebooks
   spend most of their length here. Walkthrough notebooks have a 1-page
   recap with a link to the matching concept notebook.
3. **Setup** (code) — `sys.path` insert, imports, `Config(...)`. Same
   pattern across all notebooks.
4. **Build** (code) — spawn dependencies (anvil, MCP server, executor,
   graph). Each step rendered with the appropriate `_viz.*` helper.
5. **Run** (code) — exercise the layer. Heavy use of `_viz.render_state`
   to show before/after.
6. **Inspect** (code) — final state read-back; tables; timelines.
7. **Recap + next** (markdown) — what we learned; pointer to the next
   notebook in the series.

The concept notebooks (`*_concepts`, plus `*_state_schema`, `*_topology`,
`*_llm_prompts`) are mostly markdown with light code (1-3 cells) for
illustrative renders. The walkthrough notebooks (`*_walkthrough`) are
mostly code with markdown narrating each step.

## What the spec deliberately does NOT include

- **No new Streamlit UI.** The repo already has `consumer/ui.py`
  (Streamlit). Notebooks render inline; they do not spin up Streamlit.
- **No new test files.** Existing `tests/` cover the system. Notebooks
  are pedagogical, not regression tests; we'll only add a single
  smoke-test that imports `_viz` and runs each renderer with a fixture
  to catch obvious breakage.
- **No clab topology file.** The repo does not ship a `.clab.yml`;
  07d notes that and links to upstream. The mock path (07c) is
  fully runnable.
- **No retroactive doc rewrite.** `docs/01-04*.md` already exist; the
  notebooks reference them rather than duplicate them.
- **No interactive in-notebook editing of contracts/MCP/A2A.**
  Read-only inspection only; mutation happens through the normal API.

## Implementation order

The plan (next skill, `writing-plans`) will sequence the build as:

1. Build `notebooks/_viz.py` with all 9 helpers + a smoke test.
2. Add `ipywidgets` to dev deps.
3. Delete the existing 5 notebooks; rewrite `notebooks/README.md`.
4. Build the chain block (`00_overview`, `01a-d`, `05a`).
5. Build the MCP block (`02a-c`).
6. Build the A2A block (`03a-c`).
7. Build the LangGraph block (`04a-d`).
8. Build `06_end_to_end` (port from existing `05_end_to_end.ipynb`).
9. Build the network block (`07a-d`) — last per user.
10. End-to-end smoke: run all notebooks via `nbclient` in CI.

## Open questions for the user (review gate)

Before we move to the writing-plans phase, the user should confirm:

- The 21-file list and ordering looks right.
- The `_viz.py` helper surface (9 renderers) covers what they want.
- They are OK with mermaid.ink as the rendering backend (HTTP, online).
  If not, alternatives are: (a) bundle a local `mermaid-cli` binary,
  (b) ship pre-rendered SVGs alongside the notebooks (loses
  reproducibility from data).
- They are OK with `ipywidgets>=8` as a new dev dep.
- They are OK with the asymmetry: chain, LangGraph, and network each
  get 4 notebooks; MCP and A2A each get 3; overview, inventory, and
  end-to-end get 1 each. Total = 21.
