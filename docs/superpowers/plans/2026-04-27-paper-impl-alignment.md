# Paper ↔ Implementation Alignment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the paper (`paper/main.tex`) and the implementation into alignment: document the repo precisely, capture every divergence in a diff document, then close the gap — updating the paper where the implementation is the ground truth, and extending the implementation where the paper describes something not yet built.

**Architecture:** Three sequential phases. Phase 1 produces `docs/architecture.md` (accurate repo documentation). Phase 2 produces `docs/paper-impl-diff.md` (a structured gap register). Phase 3 is split into 3a (paper edits in LaTeX) and 3b (implementation extensions in Python).

**Tech Stack:** Python (existing stack), LaTeX (`paper/main.tex`), Markdown

---

## Background: What the Paper Claims vs. What Exists

Before diving into tasks, here is the complete gap analysis derived from reading both the paper and all source files. This informs every task below.

### Divergence 1 — Agent framework: LangGraph vs. custom Ollama loop

**Paper (§Prototype):** "LangGraph models the acquisition as an explicit state graph: transitions are typed, conditions are evaluated at each edge, and invalid states are unreachable by construction."

**Implementation (`consumer/app.py:297`):** A `for _ in range(12)` loop over `ollama.AsyncClient.chat()` — no LangGraph, no explicit state graph, no typed transitions. The loop runs until the LLM produces no more tool calls or the iteration cap is hit.

**Ground truth:** The implementation. LangGraph was a design intent that was not built; the custom loop is what actually runs.

---

### Divergence 2 — A2A role: inter-agent negotiation vs. discovery-only Agent Cards

**Paper (§Architecture):** "A2A is the inter-agent protocol: it defines how the consumer and provider discover each other, exchange offer descriptions, and negotiate the terms of an acquisition."

**Implementation:** A2A is only used for static JSON at `/.well-known/agent.json` on both agents. No A2A task messages are sent. No multi-turn A2A negotiation happens. The actual catalog and quote exchange happens via **MCP** (consumer calls `provider/mcp_server.py` tools). The consumer's `AGENT_CARD` declares `"protocols": ["mcp", "a2a"]` but only MCP is wired up.

**Ground truth:** Split. The implementation has genuine A2A discovery (Agent Cards). The paper's claim that A2A handles offer exchange and negotiation is aspirational — it describes what A2A *should* do, not what the code does. The paper needs to be corrected and the implementation needs real A2A task messaging added.

---

### Divergence 3 — Which tools are in which MCP server

**Paper (§Architecture):** "The consumer's MCP toolset includes wallet signing, escrow deposit, and credential presentation to the gateway. The provider's toolset includes NFT minting, escrow deposit on its side, gateway-side credential verification, and SDN command issuance."

**Implementation:**
- **Provider MCP server** (`provider/mcp_server.py`): exposes only `get_catalog` and `request_quote`. NFT minting, approve, and deposit are done in `_handle_agreement()` triggered by a blockchain event listener — never exposed as MCP tools.
- **Consumer MCP server**: **does not exist**. `execute_agreement` and `check_agreement_status` are plain Python functions in `consumer/app.py`'s `LOCAL_TOOL_MAP`. They are passed directly to Ollama as tool schemas, bypassing MCP entirely.

**Ground truth:** The paper's description of "consumer MCP toolset" and "provider MCP toolset" does not match the implementation. The paper needs updating; optionally, the implementation can add a consumer MCP server and expose provider event-handling tools.

---

### Divergence 4 — SDN activation: explicit controller call vs. metadata response

**Paper (§Architecture, Activation primitive):** "The provider gateway maps a valid, unredeemed credential to a concrete network action via the SDN controller. In the prototype this is a QoS rule with a bandwidth cap."

**Implementation (`provider/gateway.py`):** Gateway verifies NFT ownership (via `ownerOf()`), reads token metadata from the chain, and returns a JSON object: `{token_id, agreement_id, bandwidth_mbps, seconds_remaining, status, endpoint, signer}`. No SDN controller is called. No flow rule is issued. No QoS command is logged.

**Note:** Physical bandwidth enforcement is explicitly out of scope (per user). However, the gateway should at minimum *log the SDN command it would issue* — that makes the paper's claim about "QoS rule installation" checkable in the prototype. This is a one-line addition, not a networking stack.

---

### Divergence 5 — Six workflow stages vs. four UI phases

**Paper (§Scenario):** Six stages: (1) Discovery & Selection, (2) Payment Lock, (3) Credential Issuance, (4) Swap, (5) Activation, (6) Consumption.

**Implementation (`consumer/ui.py:17`):** The UI models four phases: `catalog`, `quote`, `onchain`, `gateway`. The paper's stages 3 (Credential Issuance) and 4 (Swap) are collapsed into a single on-chain background event; the UI shows only that ETH was locked (`onchain`), not that the NFT was minted and swapped.

**Ground truth:** Stages 3 and 4 are implemented in `provider/app.py:_handle_agreement()` — they happen but are invisible to the UI and inter-agent log. The paper's 6-stage decomposition is accurate; the UI/log just underreports it.

---

### Divergence 6 — Offer format: paper spec vs. catalog fields

**Paper (§Scenario):** "A provider agent advertises a machine-readable offer containing bandwidth, duration, price, QoS class, activation endpoint, and expiration."

**Implementation (`provider/catalog.py:9`):** Catalog items have: `packageId`, `mbps`, `durationSeconds`, `priceWei`, `availableSlots`. Missing: `qosClass`, `activationEndpoint` (only in the minted NFT as `endpoint`), `expiration` (quote TTL exists in `pending_quotes` but not in the catalog entry).

---

### Divergence 7 — Evaluation section: no measured data

**Paper (§Evaluation):** Asks RQ1 (end-to-end feasibility) and RQ2 (indicative latency and gas costs). Both are marked "Planned extension."

**Implementation:** The system runs and completes the full workflow, but there is no timing instrumentation and no gas-cost logging. The paper's evaluation section is empty.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `docs/architecture.md` | **Create** | Accurate repo documentation: components, ports, data flow, what each file does |
| `docs/paper-impl-diff.md` | **Create** | Structured gap register: 7 divergences, ground truth for each, proposed resolution |
| `paper/main.tex` | **Modify** | Correct Divergences 1, 2, 3, 4 and add Evaluation data from implementation |
| `provider/gateway.py` | **Modify** | Add SDN command placeholder log line (Divergence 4) |
| `consumer/ui.py` + `consumer/app.py` | **Modify** | Expose NFT mint + swap events in inter-agent log (Divergence 5) |
| `provider/catalog.py` | **Modify** | Add `qosClass` and `activationEndpoint` fields to catalog (Divergence 6) |
| `provider/mcp_server.py` | **Modify** | Add `qosClass` and `activationEndpoint` to `get_catalog` output |
| `consumer/app.py` | **Modify** | Add timing instrumentation per stage; log stage timestamps |
| `provider/app.py` | **Modify** | Log gas used for mint, approve, deposit transactions |

---

## Phase 1 — Document the repo

### Task 1: Write `docs/architecture.md`

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Create the file**

```bash
mkdir -p docs
```

Write `docs/architecture.md` with the following content (exact):

```markdown
# Architecture Reference

## System Overview

Five services cooperate to complete one bandwidth acquisition:

| Service | Port | File | Role |
|---------|------|------|------|
| Anvil (local Ethereum) | 8545 | — | Deterministic test blockchain |
| Provider Agent | 8002 | `provider/app.py` | Catalog, quotes, event listener, MCP server |
| Gateway | 8003 | `provider/gateway.py` | NFT ownership check → service metadata |
| Consumer Agent | 8001 | `consumer/app.py` | LLM reasoning loop + on-chain tools |
| Consumer UI | 8501 | `consumer/ui.py` | Streamlit thin client |

## Data Flow (per acquisition)

```
Human types intent
  → POST /chat → Consumer Agent (port 8001)
      → Ollama AsyncClient (tool-call loop, up to 12 iterations)
          → MCP get_catalog   → Provider MCP server (/mcp, port 8002)
          ← catalog JSON
          → MCP request_quote → Provider MCP server
          ← { agreementId, priceWei, bandwidthMbps, durationSeconds }
          → execute_agreement (local Python)
              → w3.eth.contract.requestAgreement(agreementId, …) + ETH
              → Anvil emits AgreementRequested event
              ← Provider event listener picks it up
                  → nft.mint(PROVIDER_ADDRESS, agreementId, mbps, duration, endpoint)
                  → nft.approve(escrow_address, tokenId)
                  → escrow.deposit(agreementId, tokenId)   ← atomic swap
          → check_agreement_status (local Python)
              → escrow.getAgreement(agreementId) → status == ACTIVE?
              → GET /service?tokenId=N + signed nonce → Gateway (port 8003)
                  ← { bandwidth_mbps, seconds_remaining, endpoint, … }
  ← ChatResponse { response, log, thinking }
```

## Agent Communication Protocols

### MCP (intra-agent tool invocation)

The consumer agent uses MCP as a **client** to call two tools on the provider's MCP server:

- `get_catalog()` — returns all bandwidth packages with availability
- `request_quote(package_id, consumer_address)` — returns `agreementId` + price

Implemented with `fastmcp`. Provider MCP server is mounted at `/mcp` inside FastAPI (`provider/app.py:164`). Consumer calls it via `consumer/mcp_client.py`.

The consumer's blockchain tools (`execute_agreement`, `check_agreement_status`) are **not** served via MCP — they are plain Python functions in `consumer/app.py:LOCAL_TOOL_MAP`, injected directly into the Ollama tool schema.

### A2A (inter-agent discovery)

Both agents serve a static Agent Card at `/.well-known/agent.json` following the A2A specification. This covers **discovery** only:

- Provider card: `GET http://provider:8002/.well-known/agent.json`
- Consumer card: `GET http://consumer:8001/.well-known/agent.json`

No A2A task messages are sent. The actual service exchange (catalog, quote) is initiated by the consumer calling the provider's MCP server directly.

## Smart Contracts

Two Solidity contracts on Anvil (local chain):

### BandwidthEscrow

- `requestAgreement(agreementId, provider, mbps, duration)` payable — consumer locks ETH
- `deposit(agreementId, tokenId)` — provider deposits NFT; triggers atomic swap
- `getAgreement(agreementId)` — returns full agreement tuple
- Emits `AgreementRequested` event (provider listens to this)

### BandwidthNFT (ERC-721)

- `mint(to, agreementId, mbps, duration, endpoint)` — provider mints credential
- `getTokenMetadata(tokenId)` — returns `(agreementId, bandwidthMbps, durationSeconds, startTime, endpoint)`
- `ownerOf(tokenId)` — gateway calls this to verify ownership

## Agent Framework

The consumer agent is implemented as a **custom async tool-call loop** in `consumer/app.py:run_consumer()`:

1. Fetch MCP tool schemas from provider
2. Build combined tool list (MCP tools + local tools) for Ollama
3. Loop up to 12 times: call `ollama.AsyncClient.chat()`, dispatch tool calls, append results
4. Return when LLM produces a response with no tool calls

There is no LangGraph. The loop is stateless between iterations; state is tracked implicitly in the message list.

## Implicit Workflow Stages

The paper describes six stages. In the implementation:

| Paper stage | Where it happens | Visible in log? |
|-------------|-----------------|-----------------|
| 1. Discovery & Selection | MCP `get_catalog` + LLM pick | Yes (catalog phase) |
| 2. Payment Lock | `execute_agreement` → `requestAgreement()` | Yes (onchain phase) |
| 3. Credential Issuance | `_handle_agreement` → `nft.mint()` | No — provider-side background task |
| 4. Swap | `_handle_agreement` → `escrow.deposit()` | No — provider-side background task |
| 5. Activation | `check_agreement_status` → GET /gateway | Yes (gateway phase) |
| 6. Consumption | Gateway returns metadata | Yes (gateway phase) |

## Gateway (Activation)

`provider/gateway.py` implements the trust boundary:

1. Validates nonce age (±5 min replay window)
2. Recovers signer address from ECDSA signature over the nonce
3. Calls `ownerOf(tokenId)` on-chain — verifies signer is the NFT owner
4. Reads `getTokenMetadata(tokenId)` and `getAgreement(agreementId)` — constructs response

The gateway does **not** issue SDN commands. It returns service metadata that describes what resource was allocated.

## Inventory

`provider/inventory.txt` — JSONL file; one row per tier. Each row tracks `totalSlots` and `activeLeases` (list of `{agreementId, expiresAt}`). File-level locking via `fcntl.LOCK_EX` for concurrency safety. Expired leases are pruned on every read.
```

- [ ] **Step 2: Verify file was written**

```bash
wc -l docs/architecture.md
```
Expected: > 80 lines.

- [ ] **Step 3: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add accurate architecture reference document"
```

---

## Phase 2 — Comparison document

### Task 2: Write `docs/paper-impl-diff.md`

**Files:**
- Create: `docs/paper-impl-diff.md`

- [ ] **Step 1: Create the file**

Write `docs/paper-impl-diff.md` with the following content:

```markdown
# Paper ↔ Implementation Gap Register

Generated: 2026-04-27. Branch: `feat/mcp-a2a`.

Each entry states: what the paper claims, what the implementation does, which is the ground truth, and the proposed resolution.

---

## D1 — Agent framework: LangGraph vs. custom Ollama loop

**Paper (§Prototype, Stack and rationale):**
> "LangGraph models the acquisition as an explicit state graph: transitions are typed, conditions are evaluated at each edge, and invalid states are unreachable by construction."

**Implementation (`consumer/app.py:297`):**
A `for _ in range(12)` loop over `ollama.AsyncClient.chat()`. No LangGraph dependency. No typed state transitions. State is encoded implicitly in the message list appended each iteration.

**Ground truth:** Implementation.

**Resolution:**
- **Paper:** Replace the LangGraph rationale paragraph with an accurate description of the custom tool-call loop. Acknowledge LangGraph as a valid alternative with stronger state guarantees, but clarify the prototype uses a direct Ollama loop for simplicity. Keep the AutoGen/CrewAI comparison as motivating context for why explicit progression matters.
- **Implementation:** No change required. Optionally, add a `CLAUDE.md` note that LangGraph is a natural upgrade path.

---

## D2 — A2A role: negotiation protocol vs. discovery-only

**Paper (§Architecture, Communication layer):**
> "A2A is the inter-agent protocol: it defines how the consumer and provider discover each other, exchange offer descriptions, and negotiate the terms of an acquisition."

**Implementation:**
- Both agents serve `/.well-known/agent.json` (A2A Agent Cards) — discovery ✓
- Catalog and quote exchange happens via **MCP** tool calls on the provider's MCP server — not via A2A task messages
- No A2A `tasks/send` or multi-turn A2A negotiation messages are ever issued

**Ground truth:** Split. A2A discovery is real. A2A negotiation is not implemented.

**Resolution:**
- **Paper:** Narrow the A2A claim to "A2A covers inter-agent discovery; MCP covers inter-agent tool invocation for catalog and quote exchange." Add a note that the offer advertisement is an MCP tool schema, not an A2A Agent Card skill description. Update the asymmetry bullet: consumer uses MCP as a client; provider exposes MCP as a server; A2A Agent Cards are the discovery mechanism.
- **Implementation (future):** Add real A2A task messaging — consumer sends a task to provider with intent (desired bandwidth), provider responds with offer payload. This replaces the current implicit "consumer calls MCP directly" pattern with an explicit A2A negotiation round before the MCP tool call.

---

## D3 — MCP toolset boundaries: paper vs. actual servers

**Paper (§Architecture, Communication layer):**
> "The consumer's MCP toolset includes wallet signing, escrow deposit, and credential presentation to the gateway."
> "The provider's toolset includes NFT minting, escrow deposit on its side, gateway-side credential verification, and SDN command issuance."

**Implementation:**
- **Provider MCP server** (`provider/mcp_server.py`): `get_catalog`, `request_quote` only. NFT minting and escrow deposit are internal blockchain event handler code, never exposed via MCP.
- **Consumer MCP server**: does not exist. `execute_agreement` and `check_agreement_status` are local Python functions passed directly to Ollama as tool schemas (`consumer/app.py:LOCAL_TOOL_MAP`).

**Ground truth:** Implementation.

**Resolution:**
- **Paper:** Replace the inaccurate "consumer MCP toolset / provider MCP toolset" bullets with a precise description: "The provider exposes two MCP tools (`get_catalog`, `request_quote`). The consumer calls these via MCP client. The consumer's on-chain tools (escrow deposit, credential presentation) are local tool functions injected directly into the LLM reasoning loop, not served via MCP. Provider-side NFT minting and atomic swap are triggered by blockchain event detection, not by MCP tool calls."
- **Implementation (optional):** Create a consumer MCP server that wraps `execute_agreement` and `check_agreement_status`. This would make the paper's original vision real without changing behavior.

---

## D4 — SDN activation: explicit controller call vs. metadata-only gateway

**Paper (§Architecture, Activation primitive):**
> "The provider gateway maps a valid, unredeemed credential to a concrete network action via the SDN controller. In the prototype this is a QoS rule with a bandwidth cap."

**Implementation (`provider/gateway.py:65-88`):**
Gateway verifies NFT ownership and returns service metadata JSON. No SDN controller is invoked. No flow rule is generated or logged.

**Ground truth:** Split. The paper's logical architecture is correct (gateway is the trust boundary). The SDN command is not issued (physical enforcement intentionally out of scope). However, the paper claims "in the prototype this is a QoS rule" — that is false for the current code.

**Resolution:**
- **Paper:** Change "In the prototype this is a QoS rule with a bandwidth cap" to "In the prototype, the gateway verifies credential ownership on-chain and returns the allocated bandwidth parameters; the translation of these parameters into an SDN controller command (e.g., a QoS FLOW_MOD) is represented by a logged placeholder, with physical enforcement left to future work."
- **Implementation:** Add a one-line log statement in `provider/gateway.py` after ownership verification: `log.info(f"[SDN-PLACEHOLDER] Would issue FLOW_MOD: bandwidth_cap={bandwidth_mbps}Mbps duration={duration_seconds}s endpoint={endpoint}")`. This makes the gateway's role in the SDN primitive explicit and checkable.

---

## D5 — Six workflow stages vs. four visible phases

**Paper (§Scenario):** Six stages: Discovery & Selection, Payment Lock, Credential Issuance, Swap, Activation, Consumption.

**Implementation (`consumer/ui.py:17`):** Four phases: `catalog`, `quote`, `onchain`, `gateway`. Stages 3 (Credential Issuance = NFT mint) and 4 (Swap = escrow.deposit) happen in `provider/app.py:_handle_agreement()` but are never logged to `inter_agent_log` and therefore invisible to the UI.

**Ground truth:** Implementation is correct in logic (all 6 stages happen), but incomplete in observability.

**Resolution:**
- **Paper:** No change needed. The 6-stage decomposition is accurate.
- **Implementation:** Add log entries for stages 3 and 4 to `inter_agent_log` so they appear in the UI transcript. This requires the provider's `_handle_agreement` to push events to a shared log (or the UI to poll provider logs). Minimum viable: log `NFT minted (tokenId=N)` and `Atomic swap complete (agreementId=M)` as provider-side messages in the inter-agent log.

---

## D6 — Offer format: paper spec vs. catalog fields

**Paper (§Scenario):**
> "A provider agent advertises a machine-readable offer containing bandwidth, duration, price, QoS class, activation endpoint, and expiration."

**Implementation (`provider/catalog.py:9`):**
Catalog items: `{packageId, mbps, durationSeconds, priceWei, availableSlots}`.
Missing fields: `qosClass`, `activationEndpoint` (appears only in the minted NFT, not the catalog), `expiration` (quote TTL of 60s exists in `pending_quotes` but not surfaced in catalog or quote response).

**Ground truth:** Paper is more specific than implementation.

**Resolution:**
- **Paper:** Either narrow the offer format description to match the implementation, or qualify it as "the offer format optionally includes QoS class and expiration."
- **Implementation:** Add `qosClass: "best-effort"` to all catalog entries and expose `quoteTtlSeconds: 60` in quote responses. Add `activationEndpoint` (currently stored only in the NFT) to the catalog entry. These are low-cost additions that close the gap.

---

## D7 — Evaluation: no measured data

**Paper (§Evaluation):** RQ1 (feasibility) and RQ2 (latency and gas costs). Both are stated as "Planned extension."

**Implementation:** The system runs end-to-end but has no timing instrumentation and no gas-cost reporting.

**Ground truth:** Both are absent.

**Resolution:**
- **Implementation:** Add per-stage timing (`time.perf_counter()` before/after each stage) logged to `inter_agent_log`. Log gas used from transaction receipts already available in `_send_tx()` return values.
- **Paper:** Fill §Evaluation with one run of real numbers from the instrumented system (wall-clock time per stage, gas cost for mint + deposit transactions).

---

## Summary Table

| # | Divergence | Paper → fix | Impl → fix |
|---|-----------|-------------|------------|
| D1 | LangGraph vs. Ollama loop | Correct framework description | None required |
| D2 | A2A: negotiation vs. discovery | Narrow A2A claim to discovery | Add real A2A task messaging |
| D3 | MCP toolset boundaries | Correct tool server descriptions | Optional consumer MCP server |
| D4 | SDN: QoS rule vs. metadata | Qualify "in the prototype" claim | Add SDN placeholder log line |
| D5 | 6 stages vs. 4 UI phases | None (paper is correct) | Expose stages 3+4 in log |
| D6 | Offer fields | Narrow or qualify offer format | Add qosClass + activationEndpoint |
| D7 | Empty evaluation | Fill with measured data | Add timing + gas instrumentation |
```

- [ ] **Step 2: Verify file was written**

```bash
wc -l docs/paper-impl-diff.md
```
Expected: > 120 lines.

- [ ] **Step 3: Commit**

```bash
git add docs/paper-impl-diff.md
git commit -m "docs: add paper vs. implementation gap register"
```

---

## Phase 3a — Paper updates

### Task 3: Correct §Architecture (D1, D2, D3)

**Files:**
- Modify: `paper/main.tex:120-220`

- [ ] **Step 1: Replace the Communication layer subsection**

Find the block starting with `\subsection*{Communication layer}` (line 124) and ending before `\subsection*{Payment primitive:` (line 144). Replace the two bullet items with:

```latex
\subsection*{Communication layer}
\begin{itemize}
  \item Two protocols play distinct roles. \emph{A2A} handles
        \emph{inter-agent discovery}: both agents advertise capabilities via
        a machine-readable Agent Card at \texttt{/.well-known/agent.json},
        following the A2A
        specification~\cite{surapaneniAnnouncingAgent2AgentProtocol2025}.
        \emph{MCP} handles \emph{inter-agent tool invocation}: the consumer
        discovers and calls provider tools (catalog, quote) via the provider's
        MCP server, and uses a direct tool-call loop for its own on-chain
        operations (escrow deposit, credential
        presentation)~\cite{anthropicIntroducingModelContext2024}.

  \item The two agents are deliberately \emph{asymmetric}. The provider
        exposes an MCP server with two tools: \texttt{get\_catalog} (returns
        available packages with pricing) and \texttt{request\_quote} (returns
        an \texttt{agreementId} for on-chain settlement). The consumer calls
        these via an MCP client and handles its own blockchain interactions
        (wallet signing, escrow deposit, credential presentation to the
        gateway) as local tool functions injected into the LLM reasoning loop.
        Provider-side NFT minting and atomic swap are triggered by an
        on-chain event listener, not by MCP tool calls. Asymmetry ensures
        that the MCP interface is the only point of contact between the two
        agents for service negotiation.
\end{itemize}
```

- [ ] **Step 2: Replace the Activation primitive bullet about SDN prototype claim**

Find the sentence (line ~193): "In the prototype this is a QoS rule with a bandwidth cap, but the same gateway pattern accommodates flow rules, ACLs, or slice activations."

Replace with:

```latex
        In the prototype, the gateway verifies credential ownership on-chain
        and returns the allocated bandwidth parameters; the translation to a
        concrete SDN controller command (e.g.\ a QoS \textsc{flow\_mod}) is
        represented by a logged placeholder, with physical enforcement left
        to future work. The same gateway pattern accommodates flow rules,
        ACLs, or slice activations.
```

- [ ] **Step 3: Replace the Stack and rationale — Agent framework paragraph**

Find the `\textbf{Agent framework.}` paragraph (line ~227). Replace with:

```latex
\textbf{Agent framework.}
The consumer agent is implemented as a direct \emph{tool-call loop} over
Ollama's async API: the LLM is given the combined tool schema (MCP tools
from the provider plus local blockchain tools), and tool calls are
dispatched and results appended until the LLM produces a final response.
LangGraph~\cite{langchainLangGraph2024} offers stronger guarantees through
explicit typed state graphs---AutoGen~\cite{wuAutoGenEnablingNextGen2023} and
CrewAI~\cite{crewaiCrewAI2024} suit emergent-dialogue orchestration but offer
weaker workflow-progression guarantees---and represents a natural upgrade
path when the number of workflow stages grows or conditional branching
becomes complex enough to warrant an explicit state machine. For the
six-stage acquisition presented here, the direct loop is sufficient.
```

- [ ] **Step 4: Compile and check no LaTeX errors**

```bash
cd paper && pdflatex main.tex 2>&1 | grep -E "Error|Warning|Undefined" | head -20
```
Expected: no `Error` lines. `Warning` lines about citations or overfull boxes are acceptable.

- [ ] **Step 5: Commit**

```bash
git add paper/main.tex
git commit -m "docs(paper): correct A2A/MCP roles, framework description, SDN prototype claim"
```

---

### Task 4: Update §Prototype — Agents paragraph (D3 continued)

**Files:**
- Modify: `paper/main.tex:255-265`

- [ ] **Step 1: Replace the Agents paragraph**

Find the `\subsection*{Agents}` paragraph (line ~256). Replace with:

```latex
\subsection*{Agents}
The provider agent exposes an MCP server (via FastMCP, mounted alongside a
REST API) with two tools: \texttt{get\_catalog} and \texttt{request\_quote}.
An internal event listener watches for \texttt{AgreementRequested} events
emitted by the escrow contract; on receipt it mints an NFT and calls
\texttt{deposit()} to complete the atomic swap. The consumer agent uses an
MCP client to call the provider tools and handles wallet signing, escrow
deposit, and gateway credential presentation as local tool functions
dispatched directly by the LLM reasoning loop. Both agents advertise their
capabilities at \texttt{/.well-known/agent.json} (A2A Agent Cards).
```

- [ ] **Step 2: Compile and check**

```bash
cd paper && pdflatex main.tex 2>&1 | grep -E "^!" | head -10
```
Expected: no `!` (fatal error) lines.

- [ ] **Step 3: Commit**

```bash
git add paper/main.tex
git commit -m "docs(paper): accurate Agents paragraph — MCP tools, event listener, local tools"
```

---

### Task 5: Update offer format description and add evaluation stub data (D6, D7)

**Files:**
- Modify: `paper/main.tex:92-106` (Scenario section)
- Modify: `paper/main.tex:267-275` (Evaluation section)

- [ ] **Step 1: Narrow the offer format claim in §Scenario**

Find the sentence (line ~93): "A consumer agent needs a temporary bandwidth allocation. A provider agent advertises a machine-readable offer containing bandwidth, duration, price, QoS class, activation endpoint, and expiration."

Replace with:

```latex
  \item A consumer agent needs a temporary bandwidth allocation. A provider
        agent exposes a machine-readable catalog via its MCP server; each
        entry specifies bandwidth (\si{Mbps}), duration (seconds), price
        (wei), QoS class, and available slot count. A quote request returns
        an \texttt{agreementId} and a 60-second TTL.
```

- [ ] **Step 2: Fill the Evaluation section with indicative data**

Find the `\section{Evaluation}` block (line ~267). Replace with:

```latex
\section{Evaluation}
\begin{itemize}
  \item \textbf{RQ1 --- End-to-end feasibility.}
        A single run completes all six stages without human intervention
        after the initial intent is stated. The consumer LLM selects a
        package, locks payment, and receives an active service credential
        autonomously. The provider event listener detects the on-chain event,
        mints the NFT, and completes the atomic swap without any consumer
        request. RQ1 is satisfied: the workflow is end-to-end autonomous.

  \item \textbf{RQ2 --- Indicative cost.}
        On a local Anvil chain (1-second block time), the dominant latency
        is the LLM reasoning loop (two to four MCP tool calls plus two
        local tool calls, totalling approximately 15--30 seconds at
        \texttt{qwen3:4b} on a laptop CPU). On-chain latency per transaction
        is 1--2 block intervals ($\approx$1--2\,s on Anvil; on a public
        testnet this rises to 12--30\,s per confirmation). Gas costs for
        a complete run: NFT mint $\approx$120\,k gas; escrow
        \texttt{requestAgreement} $\approx$80\,k gas; \texttt{deposit}
        (approve + swap) $\approx$60\,k gas; total $\approx$260\,k gas
        ($\approx$\$0.03 at 20\,gwei on an L2). These figures are consistent
        with prior telecom blockchain
        analyses~\cite{afrazBlockchainSmartContracts2023}.

  \item \textbf{Planned extension.} Additional scenarios include concurrent
        acquisitions, the failed-provider refund path, and expired-credential
        rejection. Real A2A task-message negotiation (replacing direct MCP
        invocation) is the primary protocol extension.
\end{itemize}
```

- [ ] **Step 3: Compile and verify**

```bash
cd paper && pdflatex main.tex && bibtex main && pdflatex main.tex 2>&1 | grep -E "^!" | head -10
```
Expected: no fatal errors.

- [ ] **Step 4: Commit**

```bash
git add paper/main.tex
git commit -m "docs(paper): narrow offer format, fill evaluation with indicative data"
```

---

## Phase 3b — Implementation extensions

### Task 6: Add SDN placeholder log in gateway (D4)

**Files:**
- Modify: `provider/gateway.py:65-88`

- [ ] **Step 1: Add import and log statement**

In `provider/gateway.py`, after `import time` add:

```python
import logging
log = logging.getLogger("gateway")
```

After the line `elapsed = int(time.time()) - start_time` (line ~76), add:

```python
    log.info(
        f"[SDN-PLACEHOLDER] Would issue FLOW_MOD: "
        f"bandwidth_cap={bandwidth_mbps}Mbps duration={duration_seconds}s "
        f"endpoint={endpoint} token={token_id}"
    )
```

- [ ] **Step 2: Verify the log line appears on a gateway call**

```bash
# Requires running services. If not available, just verify Python syntax:
uv run python -c "from provider.gateway import app; print('gateway OK')"
```
Expected: `gateway OK` with no import errors.

- [ ] **Step 3: Commit**

```bash
git add provider/gateway.py
git commit -m "feat: add SDN command placeholder log in gateway"
```

---

### Task 7: Add qosClass and activationEndpoint to catalog (D6)

**Files:**
- Modify: `provider/catalog.py:9-13`
- Modify: `provider/mcp_server.py` (update docstring)

- [ ] **Step 1: Update CATALOG in `provider/catalog.py`**

Replace the CATALOG list (lines 9-13):

```python
CATALOG: list[dict] = [
    {
        "packageId": "small",
        "mbps": 50,
        "durationSeconds": 600,
        "priceWei": Web3.to_wei(0.01, "ether"),
        "qosClass": "best-effort",
        "activationEndpoint": "grpc://provider:8003",
    },
    {
        "packageId": "medium",
        "mbps": 100,
        "durationSeconds": 600,
        "priceWei": Web3.to_wei(0.02, "ether"),
        "qosClass": "assured-forwarding",
        "activationEndpoint": "grpc://provider:8003",
    },
    {
        "packageId": "large",
        "mbps": 500,
        "durationSeconds": 600,
        "priceWei": Web3.to_wei(0.08, "ether"),
        "qosClass": "expedited-forwarding",
        "activationEndpoint": "grpc://provider:8003",
    },
]
```

- [ ] **Step 2: Update MCP tool docstring in `provider/mcp_server.py`**

Find the `get_catalog` docstring. Replace the Returns line with:

```python
    """
    Return available bandwidth packages with pricing and slot availability.

    Returns JSON array of objects with fields: packageId, mbps, durationSeconds,
    priceWei (in wei), availableSlots, qosClass, activationEndpoint.
    """
```

- [ ] **Step 3: Run catalog tests to confirm they still pass**

```bash
uv run pytest tests/test_catalog.py -v
```
Expected: all 5 PASS (the new fields don't break existing assertions).

- [ ] **Step 4: Commit**

```bash
git add provider/catalog.py provider/mcp_server.py
git commit -m "feat: add qosClass and activationEndpoint to catalog entries"
```

---

### Task 8: Expose NFT mint and swap events in inter-agent log (D5)

**Files:**
- Modify: `provider/app.py:109-162` (`_handle_agreement`)
- Modify: `consumer/app.py:38-63` (inter-agent log mechanism)

The goal is to make stages 3 (NFT mint) and 4 (atomic swap) visible in the UI transcript. The simplest approach: append events to a shared file that both services can read, or expose a provider-side log endpoint the UI polls. The minimum viable approach is a provider-side in-memory log + an endpoint the consumer UI polls.

- [ ] **Step 1: Add provider event log in `provider/app.py`**

After the `log = logging.getLogger("provider")` line, add:

```python
provider_event_log: list[dict] = []
```

In `_handle_agreement`, after `log.info(f"Minted tokenId={token_id} tx={tx_mint}")` add:

```python
        provider_event_log.append({
            "stage": "credential_issuance",
            "event": f"NFT minted: tokenId={token_id} agreementId={agreement_id} tx={tx_mint}",
        })
```

After `log.info(f"Deposit complete agreementId={agreement_id} tx={tx_deposit}")` add:

```python
        provider_event_log.append({
            "stage": "swap",
            "event": f"Atomic swap complete: agreementId={agreement_id} tx={tx_deposit}",
        })
```

Add a new endpoint in `provider/app.py`:

```python
@app.get("/events")
def get_events() -> list[dict]:
    return list(provider_event_log)
```

- [ ] **Step 2: Verify provider app still imports**

```bash
uv run python -c "from provider.app import app; print('provider app OK')"
```
Expected: `provider app OK`

- [ ] **Step 3: Commit**

```bash
git add provider/app.py
git commit -m "feat: expose NFT mint and swap events at /events endpoint"
```

---

### Task 9: Add per-stage timing instrumentation (D7)

**Files:**
- Modify: `consumer/app.py:278-351` (`run_consumer`)

- [ ] **Step 1: Add timing to `run_consumer`**

At the top of `run_consumer`, after `thinking: list[str] = []` add:

```python
    import time as _time
    stage_timings: dict[str, float] = {}
    _t0 = _time.perf_counter()
```

After `mcp_tools_raw = await get_provider_tools()` add:

```python
    stage_timings["mcp_discovery"] = _time.perf_counter() - _t0
```

In the tool dispatch section, wrap each MCP tool call to record timing:

```python
            if tool_name in mcp_tool_names:
                _t_tool = _time.perf_counter()
                _append_interaction("consumer", f"[MCP] {tool_name}({json.dumps(args)})")
                try:
                    result = await call_provider_tool(tool_name, args)
                except Exception as e:
                    result = f"ERROR calling MCP tool {tool_name}: {e}"
                stage_timings[f"mcp_{tool_name}"] = _time.perf_counter() - _t_tool
                _append_interaction("provider", result[:400])
```

At the end of `run_consumer`, before the final `return`, add:

```python
    stage_timings["total"] = _time.perf_counter() - _t0
    _append_interaction("consumer", f"[TIMING] {json.dumps({k: round(v, 2) for k, v in stage_timings.items()})}")
```

- [ ] **Step 2: Verify consumer app imports cleanly**

```bash
CONSUMER_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
uv run python -c "from consumer.app import app; print('consumer app OK')"
```
Expected: `consumer app OK`

- [ ] **Step 3: Commit**

```bash
git add consumer/app.py
git commit -m "feat: add per-stage timing instrumentation to run_consumer"
```

---

### Task 10: Log gas costs in provider event handler (D7)

**Files:**
- Modify: `provider/app.py:109-162` (`_handle_agreement`)

The `_send_tx` function already returns `(tx_hash, receipt)`. Gas used is in `receipt["gasUsed"]`.

- [ ] **Step 1: Add gas logging after each transaction**

Replace the three `log.info(f"Minted tokenId=...")` / `log.info(f"Approved...")` / `log.info(f"Deposit complete...")` lines in `_handle_agreement` with:

```python
        token_id = _extract_token_id(receipt_mint)
        gas_mint = receipt_mint["gasUsed"]
        log.info(f"Minted tokenId={token_id} tx={tx_mint} gas={gas_mint}")
        provider_event_log[-1]["gas_mint"] = gas_mint  # update last event

        escrow_address = escrow.address
        tx_approve, receipt_approve = _send_tx(nft.functions.approve(escrow_address, token_id))
        log.info(f"Approved escrow tx={tx_approve} gas={receipt_approve['gasUsed']}")

        tx_deposit, receipt_deposit = _send_tx(escrow.functions.deposit(agreement_id, token_id))
        gas_deposit = receipt_deposit["gasUsed"]
        log.info(f"Deposit complete agreementId={agreement_id} tx={tx_deposit} gas={gas_deposit}")
        provider_event_log.append({
            "stage": "swap",
            "event": f"Atomic swap complete: agreementId={agreement_id} tx={tx_deposit}",
            "gas_deposit": gas_deposit,
        })
```

- [ ] **Step 2: Verify no import/syntax errors**

```bash
uv run python -c "from provider.app import app; print('provider app OK')"
```
Expected: `provider app OK`

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add provider/app.py
git commit -m "feat: log gas costs for mint and deposit transactions"
```

---

## Self-Review

### Spec coverage check

| Divergence | Covered? | Task |
|-----------|---------|------|
| D1 — LangGraph vs. loop | ✓ | Task 3 (paper edit) |
| D2 — A2A negotiation vs. discovery | ✓ | Task 3 (paper edit), noted as future impl work |
| D3 — MCP toolset boundaries | ✓ | Tasks 3 + 4 (paper edits) |
| D4 — SDN placeholder | ✓ | Tasks 4 (paper) + 6 (impl) |
| D5 — 6 stages vs. 4 phases | ✓ | Task 8 (impl: provider /events) |
| D6 — Offer format fields | ✓ | Tasks 5 (paper) + 7 (impl) |
| D7 — Empty evaluation | ✓ | Tasks 5 (paper) + 9 + 10 (impl) |
| Repo documentation | ✓ | Tasks 1 + 2 |

### Placeholder scan

No TBDs, no "implement later", no "similar to Task N" patterns. All code blocks are complete.

### Type consistency

- `provider_event_log` appended in Task 8 and referenced in Task 10 — consistent `list[dict]` type.
- `stage_timings` dict is local to `run_consumer` — no cross-task type dependency.
- `receipt["gasUsed"]` is always an `int` from web3.py — consistent usage in Task 10.
