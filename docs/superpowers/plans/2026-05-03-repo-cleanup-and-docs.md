# Repo Cleanup and Documentation Restructure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove legacy pre-MCP code, fix repo hygiene, and replace the three overlapping top-level docs with a seven-file documentation set under `docs/` written for a zero-knowledge reader.

**Architecture:** Pure cleanup + documentation. No application-code changes. Executes as 11 sequential commits on `feat/mcp-a2a`, each self-contained and pushable. Verification by existing tests + docker build at the end.

**Tech Stack:** Markdown, git. No code dependencies added or removed.

**Spec:** `docs/superpowers/specs/2026-05-03-repo-cleanup-and-docs-design.md`

---

## Pre-Flight Checks

Before starting Task 1, verify the working state:

```bash
git status                        # must be on feat/mcp-a2a, clean except .claude/ and diagnosis.md
uv run pytest -q                  # must currently pass
docker compose config > /dev/null # must currently parse
```

If any of these fail, stop and resolve before starting.

---

## Task 1: Remove Legacy Pre-MCP Prototype Files

These five files are a pre-refactor prototype. Both `CODEBASE_REFERENCE.md §11` and `diagnosis.md §6` declare them dead. Verified zero references in any active entry point (Dockerfiles, docker-compose, Makefile, current packages).

**Files:**
- Delete: `app.py`
- Delete: `consumer_agent.py`
- Delete: `provider_server.py`
- Delete: `catalog.txt`
- Delete: `agreements.json`

- [ ] **Step 1: Verify zero live references one more time**

```bash
grep -rn -E "(consumer_agent\.py|provider_server\.py|^app\.py|catalog\.txt|agreements\.json)" \
  --include="*.py" --include="*.yml" --include="*.toml" \
  --include="Dockerfile*" --include="Makefile" \
  --exclude-dir=.venv --exclude-dir=.git \
  --exclude-dir=docs --exclude-dir=paper .
```

Expected output: only matches inside the dead files themselves (`app.py:8: from consumer_agent...`, `provider_server.py:9: CATALOG_FILE = ...`, etc.). Any match in `consumer/`, `provider/`, `shared/`, `tests/`, `docker-compose.yml`, `Makefile`, or any `Dockerfile*` is a STOP — re-evaluate before deleting.

- [ ] **Step 2: Delete the five legacy files**

```bash
git rm app.py consumer_agent.py provider_server.py catalog.txt agreements.json
```

- [ ] **Step 3: Verify tests still pass**

```bash
uv run pytest -q
```

Expected: all tests pass with the same pass count as the pre-flight check. (No test imports any of the deleted modules; legacy files were standalone.)

- [ ] **Step 4: Verify docker compose still parses**

```bash
docker compose config > /dev/null
```

Expected: no output (success).

- [ ] **Step 5: Commit and push**

```bash
git commit -m "$(cat <<'EOF'
chore: remove legacy pre-MCP prototype files

Removes app.py, consumer_agent.py, provider_server.py, catalog.txt,
agreements.json. These were a pre-MCP/pre-blockchain prototype already
flagged as dead in CODEBASE_REFERENCE.md and diagnosis.md, with zero
references from the current consumer/, provider/, shared/ packages or
from any active entry point.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 2: Fix `.gitignore` and `pyproject.toml` Metadata

**Files:**
- Modify: `.gitignore`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add three entries to `.gitignore`**

Append these lines to the end of the file (do not remove existing entries):

```
.claude/
.pytest_cache/
.venv/
```

Final `.gitignore` content (verify after edit):

```
.env
.python-version
__pycache__/
contracts/out/
contracts/cache/
contracts/lib/
contracts/deployments/local.json
.superpowers/
.claude/
.pytest_cache/
.venv/
```

- [ ] **Step 2: Replace placeholder description in `pyproject.toml`**

Find the line:

```
description = "Add your description here"
```

Replace with:

```
description = "Proof-of-concept: two AI agents negotiate and pay for network bandwidth using MCP, A2A, and an Ethereum smart-contract escrow."
```

Leave every other line in `pyproject.toml` unchanged.

- [ ] **Step 3: Verify the changes**

```bash
git diff .gitignore pyproject.toml
```

Expected: only the three new gitignore lines and the one description line change.

```bash
uv run pytest -q
```

Expected: still passes (changes are not code).

- [ ] **Step 4: Commit and push**

```bash
git add .gitignore pyproject.toml
git commit -m "$(cat <<'EOF'
chore: tighten gitignore and pyproject metadata

Adds .claude/, .pytest_cache/, .venv/ to .gitignore and replaces the
'Add your description here' placeholder in pyproject.toml with a
real one-line description.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 3: Move `diagnosis.md` to `docs/paper-alignment.md`

`diagnosis.md` is currently untracked at the repo root. It analyses paper↔code alignment and belongs alongside the other docs.

**Files:**
- Move: `diagnosis.md` → `docs/paper-alignment.md`
- Create (then move): `docs/paper-alignment.md`

- [ ] **Step 1: Move the file**

`diagnosis.md` is untracked, so `git mv` won't work directly. Use plain mv then add:

```bash
mv diagnosis.md docs/paper-alignment.md
```

- [ ] **Step 2: Update internal references inside the moved file**

Open `docs/paper-alignment.md`. The current content references `CODEBASE_REFERENCE.md §X` in several places. Leave those references intact for now — they will be updated in Task 4 when `CODEBASE_REFERENCE.md` is replaced by `docs/04-architecture.md`. No edits to the file in this task.

- [ ] **Step 3: Verify nothing else references the old root path**

```bash
grep -rn "diagnosis\.md" --exclude-dir=.git --exclude-dir=.venv --exclude-dir=docs/superpowers .
```

Expected: zero matches (the spec under `docs/superpowers/specs/` references it, but those are excluded from the grep).

- [ ] **Step 4: Stage and commit**

```bash
git add docs/paper-alignment.md
git status
```

Expected: `new file: docs/paper-alignment.md` and nothing else.

```bash
git commit -m "$(cat <<'EOF'
docs: move diagnosis.md to docs/paper-alignment.md

The paper-vs-code alignment analysis was previously an untracked file
at the repo root. Moves it into docs/ alongside the rest of the
project documentation. Content is unchanged.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 4: Create `docs/04-architecture.md` Replacing `CODEBASE_REFERENCE.md`

`CODEBASE_REFERENCE.md` is the technical reference. We port it to `docs/04-architecture.md`, drop the legacy-file sections (those files no longer exist), and fix any drift against the current code on `feat/mcp-a2a`.

**Files:**
- Create: `docs/04-architecture.md`
- Delete: `CODEBASE_REFERENCE.md`

- [ ] **Step 1: Create `docs/04-architecture.md` by porting `CODEBASE_REFERENCE.md`**

Copy `CODEBASE_REFERENCE.md` to `docs/04-architecture.md` as a starting point:

```bash
cp CODEBASE_REFERENCE.md docs/04-architecture.md
```

- [ ] **Step 2: Update the title and intro of `docs/04-architecture.md`**

Replace the current title (`# Codebase Technical Reference`) with:

```markdown
# Architecture Reference

> **Audience:** developers reading or modifying the code. Assumes you have already read [`01-introduction.md`](01-introduction.md) and the concepts you need from [`02-concepts.md`](02-concepts.md). For end-to-end behaviour, read [`03-walkthrough.md`](03-walkthrough.md) first.
```

Then delete the section labelled "**IMPORTANT:** There are two generations of code in this repo..." through to the end of that paragraph — that warning becomes obsolete once the legacy files are deleted (Task 1).

- [ ] **Step 3: Remove legacy-file mentions from the directory tree**

In the section `## 3. FULL DIRECTORY TREE`, delete these lines:

```
├── app.py                     # Legacy Streamlit app — wraps consumer_agent.py (old HTTP approach)
├── consumer_agent.py          # Legacy consumer — HTTP to provider_server.py (no MCP, no blockchain)
├── provider_server.py         # Legacy provider — plain HTTP, CSV catalog, UUID tokens
├── catalog.txt                # Legacy CSV catalog (consumer_agent.py reads this)
└── agreements.json            # Legacy agreements store (provider_server.py writes this)
```

- [ ] **Step 4: Remove the legacy-files quirk**

In the section `## 11. KNOWN QUIRKS & CONSTRAINTS`, delete the entire bullet that begins:

```
11. **Legacy files (`app.py`, `consumer_agent.py`, `provider_server.py`) are not deleted.**
```

Renumber any subsequent items in that list if needed.

- [ ] **Step 5: Update `gateway.py` reference if present**

In section `## 6. DATA MODELS & SCHEMA`, the entry `### Gateway response (`provider/gateway.py:79`)` references a file that no longer exists (gateway was folded into `provider/agent_executor.py` in commit `dcac0ad`). Verify by:

```bash
ls provider/gateway.py 2>/dev/null && echo "EXISTS" || echo "MISSING"
```

If `MISSING`: remove the entire `### Gateway response` subsection from `04-architecture.md`. The activation response shape is already covered under `provider/agent_executor.py` elsewhere.

- [ ] **Step 6: Update CODEBASE_REFERENCE.md references in `docs/paper-alignment.md`**

```bash
sed -i 's/`CODEBASE_REFERENCE\.md/`docs\/04-architecture.md/g' docs/paper-alignment.md
```

- [ ] **Step 7: Delete `CODEBASE_REFERENCE.md`**

```bash
git rm CODEBASE_REFERENCE.md
```

- [ ] **Step 8: Sanity-check the new doc renders sensibly**

```bash
wc -l docs/04-architecture.md
head -10 docs/04-architecture.md
grep -c "^## " docs/04-architecture.md
```

Expected: ~500–600 lines, title `# Architecture Reference`, around 12 top-level sections.

```bash
grep -n "app\.py\|consumer_agent\.py\|provider_server\.py\|catalog\.txt\|agreements\.json\|provider/gateway\.py" docs/04-architecture.md
```

Expected: zero matches.

- [ ] **Step 9: Commit and push**

```bash
git add docs/04-architecture.md docs/paper-alignment.md
git commit -m "$(cat <<'EOF'
docs: add docs/04-architecture.md replacing CODEBASE_REFERENCE.md

Ports the technical reference into docs/ with legacy-file mentions
removed and the obsolete provider/gateway.py section dropped (gateway
was folded into provider/agent_executor.py in dcac0ad). Updates
docs/paper-alignment.md cross-references to point at the new path.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 5: Write `docs/02-concepts.md`

Concepts primer for a reader with zero prior knowledge. Each concept is 50–250 words with a one-line definition, a short elaboration, and a "**In this project:**" pointer to where it shows up.

**Files:**
- Create: `docs/02-concepts.md`

- [ ] **Step 1: Create the file with the structure below**

Path: `docs/02-concepts.md`

Use exactly these top-level sections in this order. Each numbered subsection covers one concept. Length target: ~600–800 lines total.

```markdown
# Concepts Primer

> **Audience:** anyone who wants to understand the words used in the rest of this documentation. No prior knowledge assumed.
>
> **How to read this doc:** scan the table of contents, jump to whatever concept you don't already know, and skip the rest. Concepts are roughly ordered so that earlier ones are referenced by later ones.

## Table of Contents

1. [Programming and runtime](#1-programming-and-runtime)
2. [AI and agents](#2-ai-and-agents)
3. [Inter-agent protocols: MCP and A2A](#3-inter-agent-protocols-mcp-and-a2a)
4. [Blockchain fundamentals](#4-blockchain-fundamentals)
5. [Tokens and NFTs](#5-tokens-and-nfts)
6. [Payment, escrow, and atomic swap](#6-payment-escrow-and-atomic-swap)
7. [Networking and SDN](#7-networking-and-sdn)
8. [State machines](#8-state-machines)

---

## 1. Programming and runtime

### 1.1 Python
### 1.2 Virtual environment
### 1.3 uv (the package manager used here)
### 1.4 pyproject.toml
### 1.5 FastAPI
### 1.6 Uvicorn
### 1.7 Streamlit
### 1.8 HTTPX
### 1.9 Docker and Docker Compose
### 1.10 Environment variable

## 2. AI and agents

### 2.1 LLM (Large Language Model)
### 2.2 Ollama
### 2.3 Prompt and system prompt
### 2.4 Tool calling
### 2.5 Agent (in this project)
### 2.6 Model context

## 3. Inter-agent protocols: MCP and A2A

### 3.1 The two-protocol design (why both)
### 3.2 MCP (Model Context Protocol)
### 3.3 A2A (Agent-to-Agent)
### 3.4 Agent Card
### 3.5 JSON-RPC

## 4. Blockchain fundamentals

### 4.1 Ethereum
### 4.2 Smart contract
### 4.3 Solidity
### 4.4 Transaction
### 4.5 Gas
### 4.6 Private key and signing
### 4.7 Nonce (chain context)
### 4.8 Event (chain log)
### 4.9 RPC and JSON-RPC over HTTP
### 4.10 Anvil
### 4.11 Foundry and Forge

## 5. Tokens and NFTs

### 5.1 ERC-721
### 5.2 NFT as a credential
### 5.3 ownerOf check

## 6. Payment, escrow, and atomic swap

### 6.1 Escrow
### 6.2 Atomic swap
### 6.3 Status state machine on-chain (NONE → REQUESTED → ACTIVE)
### 6.4 deposit() and refund()

## 7. Networking and SDN

### 7.1 REST API
### 7.2 Port (TCP)
### 7.3 SDN (Software-Defined Networking)
### 7.4 Traffic shaping with `tc tbf`
### 7.5 gNMI
### 7.6 ContainerLab
### 7.7 Mock vs real activation

## 8. State machines

### 8.1 What a state machine is
### 8.2 Three state machines in this project
```

- [ ] **Step 2: Write each concept body using this exact template**

For every numbered subsection (e.g. `### 1.1 Python`), write:

```markdown
### 1.1 Python

**One-liner:** A general-purpose programming language readable enough to look like English.

Two to four sentences expanding the one-liner. Mention the version pinned in this project (3.13). Tie back to anything a beginner might confuse it with (e.g., "not the same as Java despite both running on virtual machines").

**In this project:** the consumer (`consumer/app.py`), provider (`provider/app.py`), shared library (`shared/`), and tests are all Python 3.13. Run scripts with `uv run python ...`, never bare `python`.
```

This three-block shape — **one-liner**, body, **In this project** — must repeat for **every** numbered concept. Do not skip any.

- [ ] **Step 3: Required content notes per concept**

Use these as the seeds. Expand each into the three-block template above. Each entry's "in this project" pointer below is the *minimum* you must include.

| Concept | "In this project" must mention |
|---|---|
| 1.1 Python | Python 3.13, `uv run python` |
| 1.2 Virtual environment | `.venv/` not committed, lives in repo root |
| 1.3 uv | `uv sync`, `uv run`, `uv add`, `uv.lock` |
| 1.4 pyproject.toml | the `[project]` table at the repo root, deps listed there |
| 1.5 FastAPI | `consumer/app.py:app` and `provider/app.py:app` are FastAPI apps |
| 1.6 Uvicorn | the `CMD` in both Dockerfiles starts uvicorn on `:8001` / `:8002` |
| 1.7 Streamlit | `consumer/ui.py` runs on `:8501` |
| 1.8 HTTPX | used inside `consumer/a2a_client.py` and the MCP servers |
| 1.9 Docker and Docker Compose | `docker-compose.yml`, `make up`, `Dockerfile.consumer`, `Dockerfile.provider` |
| 1.10 Environment variable | `.env`, `.env.example`, list the four most important: `RPC_URL`, `*_PRIVATE_KEY`, `OLLAMA_MODEL`, `SDN_MOCK` |
| 2.1 LLM | the local Ollama-served model is the consumer's brain |
| 2.2 Ollama | the `ollama` service in `docker-compose.yml`, the `qwen3:4b` default |
| 2.3 Prompt and system prompt | the system prompt for the consumer agent (no longer a 12-step prompt; the LangGraph nodes drive the flow — but the per-node LLM calls still use focused prompts) |
| 2.4 Tool calling | the LLM picks MCP tools by name; lists the consumer's MCP tool names |
| 2.5 Agent | this project has two: consumer (buyer) and provider (seller) |
| 2.6 Model context | the prompt + tool list + history the LLM sees on each call |
| 3.1 Two-protocol design | MCP = inside one agent (its tools); A2A = between agents (their messages). Reference the paper |
| 3.2 MCP | FastMCP, `consumer/mcp_server.py`, `provider/mcp_server.py`, `/mcp` endpoint |
| 3.3 A2A | `a2a-sdk`, `provider/agent_executor.py`, `consumer/a2a_client.py`, `/a2a` endpoint |
| 3.4 Agent Card | `/.well-known/agent-card.json`, `consumer/agent_card.py`, `provider/agent_card.py` |
| 3.5 JSON-RPC | A2A uses JSON-RPC under the hood; one example request shape |
| 4.1 Ethereum | the local Anvil chain at `:8545`, not a real network |
| 4.2 Smart contract | `BandwidthEscrow.sol`, `BandwidthNFT.sol` under `contracts/src/` |
| 4.3 Solidity | the language those two contracts are written in |
| 4.4 Transaction | the consumer's `requestAgreement(...)` call is the one transaction in the demo |
| 4.5 Gas | mention that on Anvil the gas is fake but the structure is real |
| 4.6 Private key and signing | `CONSUMER_PRIVATE_KEY` and `PROVIDER_PRIVATE_KEY` in `.env`, used for both chain transactions and credential nonces |
| 4.7 Nonce (chain context) | distinguish from the credential nonce in §3 — chain nonce = transaction order; credential nonce = signed challenge |
| 4.8 Event | `AgreementRequested` event, listened to by `provider/expiry.py` and the executor |
| 4.9 RPC and JSON-RPC over HTTP | `RPC_URL=http://anvil:8545` |
| 4.10 Anvil | local fake Ethereum, deterministic, instant blocks |
| 4.11 Foundry and Forge | `forge script script/Deploy.s.sol`, `contracts/foundry.toml` |
| 5.1 ERC-721 | the standard `BandwidthNFT.sol` implements |
| 5.2 NFT as a credential | the NFT *is* the access ticket, no off-chain database lookup |
| 5.3 ownerOf check | `verify_credential_ownership` MCP tool calls `ownerOf()` |
| 6.1 Escrow | `BandwidthEscrow.deposit()` holds ETH until conditions met |
| 6.2 Atomic swap | the `deposit()` body atomically transfers ETH→provider and NFT→consumer; reverts if either fails |
| 6.3 Status state machine | NONE → REQUESTED → ACTIVE, used to gate activation; show the enum values |
| 6.4 deposit() and refund() | refund path on expiry; reference `provider/expiry.py` |
| 7.1 REST API | the consumer exposes `/chat`, `/catalog_proxy`, `/address` |
| 7.2 Port | `:8001` consumer, `:8002` provider, `:8501` UI, `:8545` chain, `:11434` ollama |
| 7.3 SDN | one paragraph; reference the paper §SDN |
| 7.4 Traffic shaping with `tc tbf` | the actual command run on a CE container; cite `srl_bandwidth.allocate_bandwidth` |
| 7.5 gNMI | the protocol used to push configs to SR Linux; mention this is real Nokia tooling |
| 7.6 ContainerLab | the `clab-up`/`clab-down` Make targets, the brother repo at `../srl-gnmi-bandwidth-poc` |
| 7.7 Mock vs real activation | `SDN_MOCK=true` (default) returns canned data; `SDN_MOCK=false` requires ContainerLab up |
| 8.1 What a state machine is | discrete states + allowed transitions + a current-state pointer |
| 8.2 Three state machines | (1) on-chain `Status`, (2) `SlotPool` (free/locked/active per slot), (3) the agent workflow itself (LangGraph nodes since commit `18d8c6d`); cross-reference §6.3 and §3.2 in this doc |

- [ ] **Step 4: Verify the structure**

```bash
wc -l docs/02-concepts.md
grep -c "^### " docs/02-concepts.md
grep -c "^\*\*One-liner:\*\*" docs/02-concepts.md
grep -c "^\*\*In this project:\*\*" docs/02-concepts.md
```

Expected: 600+ lines, 47 `### ` subsections (count concepts above), 47 one-liners, 47 in-project pointers.

- [ ] **Step 5: Commit and push**

```bash
git add docs/02-concepts.md
git commit -m "$(cat <<'EOF'
docs: add docs/02-concepts.md (concepts primer)

Adds a beginner-oriented primer that explains every concept used in
the rest of the documentation — from Python and Docker through MCP,
A2A, smart contracts, NFTs, escrow, and SDN — assuming zero prior
knowledge. Each concept follows a one-liner / elaboration / 'in this
project' template.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 6: Write `docs/03-walkthrough.md`

A narrative trace of one successful `make demo` run, written in the present tense as a story so the reader can follow what each component is doing at each moment.

**Files:**
- Create: `docs/03-walkthrough.md`

- [ ] **Step 1: Create the file with this exact section structure**

```markdown
# End-to-End Walkthrough

> **Audience:** anyone who has read [`01-introduction.md`](01-introduction.md) and at least skimmed [`02-concepts.md`](02-concepts.md). You'll come out of this doc knowing what every component does and how a single typed sentence ends up enforcing a real bandwidth limit.
>
> **What we trace:** a successful run of `make demo` with `SDN_MOCK=true`. The mock-vs-real difference is called out at the end.

## The setup before the user types

## Stage 0 — User intent
## Stage 1 — Discovery (browse catalog)
## Stage 2 — Quote and lock
## Stage 3 — Credential issuance (NFT mint)
## Stage 4 — Atomic swap (escrow ↔ NFT)
## Stage 5 — Activation (present credential, apply rule)
## Stage 6 — Consumption and expiry

## What changes with `SDN_MOCK=false`

## Where to read the code for each stage
```

- [ ] **Step 2: Required content per section**

For each `## Stage N` section, write four sub-blocks **in this order** (use these literal headings as the sub-blocks, no skipping):

```markdown
**What the user sees**
**What happens between components** (ASCII sequence diagram)
**Where in the code**
**Why this stage exists**
```

Required facts per stage (do not invent extra steps; this is the actual flow):

- **Setup before the user types:** the seven services from `docker-compose.yml` are up: `anvil`, `deployer` (one-shot, completed), `ollama`, `ollama-pull-4b`/`ollama-pull-1.7b` (one-shot), `provider-agent`, `consumer-agent`, `consumer-ui`. The provider's `_AgreementRequested_listener` task in `provider/expiry.py` is polling for new agreements. The provider's `SlotPool` has its inventory loaded from `provider/inventory.txt`.

- **Stage 0:** user types `"I need 5 Mbps for 10 minutes"` in the Streamlit UI at `:8501`. Streamlit POSTs to `consumer-agent:8001/chat` with `{"message": ..., "model": "qwen3:4b"}`.

- **Stage 1 — Discovery:** the consumer's LangGraph `browse_node` calls the consumer MCP tool `query_provider_catalog`, which uses `consumer/a2a_client.py` to call provider MCP `get_catalog` over HTTP at `provider-agent:8002/mcp`. The result is a list of tier dicts.

- **Stage 2 — Quote and lock:** `pick_tier_node` picks `medium` (mapping 5 Mbps → medium). `quote_node` calls consumer MCP `request_quote` → provider MCP `quote_tier`, which puts an entry in `pending_quotes`. `lock_node` calls consumer MCP `lock_payment`, which signs a `requestAgreement` transaction against `BandwidthEscrow` on Anvil. The chain emits `AgreementRequested(agreementId, ...)`.

- **Stage 3 — Credential issuance:** the provider's listener picks up the event, calls provider MCP `mint_credential`, which mints an NFT with `BandwidthNFT.safeMint` and writes the `TokenMetadata`. The NFT is owned by the *provider* at this point.

- **Stage 4 — Atomic swap:** the provider's listener immediately calls `BandwidthEscrow.deposit(agreementId, tokenId)`. The contract atomically (a) transfers ETH from escrow to provider, (b) transfers NFT from provider to consumer, (c) flips the agreement status to ACTIVE. Reverts on any failure.

- **Stage 5 — Activation:** consumer's `settle_node` polls until the agreement is ACTIVE, then `present_node` calls A2A `activate` task on the provider. The provider executor calls provider MCP `verify_credential_ownership` (signed nonce + `ownerOf` + status check), then `allocate_bandwidth` (`tc tbf` via Docker exec, or canned response in mock mode).

- **Stage 6 — Consumption and expiry:** the consumer reports active service back to the user. The slot expires after `duration_min`; `provider/expiry.py` sweeps and frees the slot, marking the credential expired (the NFT itself remains in the consumer's wallet as historical proof).

- **`SDN_MOCK=false` differences:** Stage 5's `allocate_bandwidth` actually `docker exec`s into a CE container to run `tc tbf` and pushes a gNMI policer. Verify with `iperf3`. Requires `make clab-up` first.

- **Where to read the code for each stage:** a final table mapping each stage → the file:line that implements it. Pull file:line from `consumer/graph.py` (the LangGraph nodes), `consumer/mcp_server.py`, `consumer/a2a_client.py`, `provider/agent_executor.py`, `provider/mcp_server.py`, `provider/expiry.py`, `contracts/src/BandwidthEscrow.sol`, `contracts/src/BandwidthNFT.sol`.

- [ ] **Step 3: ASCII sequence diagrams**

For each `**What happens between components**` block, draw a sequence diagram in this style:

```
User      Consumer-UI    Consumer-Agent    Consumer-MCP    Provider-MCP    Anvil
 │             │                │                 │                │            │
 │   "5 Mbps"  │                │                 │                │            │
 │────────────▶│  POST /chat    │                 │                │            │
 │             │───────────────▶│                 │                │            │
 │             │                │  query_catalog  │                │            │
 │             │                │────────────────▶│  get_catalog   │            │
 │             │                │                 │───────────────▶│            │
 │             │                │                 │   list[tier]   │            │
 │             │                │                 │◀───────────────│            │
```

Adjust the participants and arrows per stage. Eight diagrams total (Setup + Stages 0–6). Length target ~30–60 lines each.

- [ ] **Step 4: Verify**

```bash
wc -l docs/03-walkthrough.md
grep -c "^## " docs/03-walkthrough.md
grep -c "^\*\*What the user sees\*\*" docs/03-walkthrough.md
```

Expected: ~400–600 lines, 11 top-level sections (setup + 7 stages + 3 trailing), 7 "What the user sees" blocks (one per stage 0–6).

- [ ] **Step 5: Commit and push**

```bash
git add docs/03-walkthrough.md
git commit -m "$(cat <<'EOF'
docs: add docs/03-walkthrough.md (end-to-end narrative)

Walks through one successful 'make demo' run stage by stage with
ASCII sequence diagrams, code pointers, and the rationale for each
stage. Targets a reader who has finished docs/02-concepts.md and
wants to see how everything fits together before reading code.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 7: Write `docs/05-running.md`

The operational reference: prereqs, configuring, running, verifying, troubleshooting. Most content can be lifted from current `README.md` and `GUIDE.md §7-8` and reorganised. Length target ~300–400 lines.

**Files:**
- Create: `docs/05-running.md`

- [ ] **Step 1: Create the file with this section structure**

```markdown
# Running the Project

> **Audience:** you want to run the demo on your machine. This doc takes you from a clean laptop to seeing the consumer agent buy bandwidth.

## Prerequisites

### Foundry
### Docker and Docker Compose
### Ollama
### uv

## Configuring

### The `.env` file
### Variables that must be set
### Variables with sensible defaults

## Running with Docker (recommended)

### `make up`
### What you should see
### Stopping and cleaning up

## Running locally without Docker

### Five-terminal flow
### Terminal 1 — Anvil
### Terminal 2 — Deploy contracts
### Terminal 3 — Provider agent
### Terminal 4 — Consumer agent
### Terminal 5 — Streamlit UI

## Verifying it works

### `make demo`
### Reading the demo output

## Multi-consumer mode
## Real SDN mode (`make demo-real`)
## Changing the AI model
## Troubleshooting

### Provider unreachable on `:8002`
### Deployer hangs / contract deploy fails
### `ollama pull` fails or times out
### Anvil port `:8545` already in use
### "Consumer agent not running on :8001"
### Wallet has zero ETH
### `make demo-real` reports wrong Mbps
### LLM picks the wrong tier
```

- [ ] **Step 2: Source content from existing docs**

Lift, deduplicate, and refresh from these specific places:

- **Prerequisites** — current `README.md:66-95` (sections 1–4). Add an "**install verification**" command per tool (`forge --version`, `docker compose version`, `ollama --version`, `uv --version`).
- **Configuring** — read `.env.example` and document every variable in it. Group "must set" (`*_PRIVATE_KEY`, `DEPLOYER_PRIVATE_KEY`, `PROVIDER_ADDRESS`) vs "has default" (`OLLAMA_MODEL`, `SDN_MOCK`).
- **Running with Docker** — current `README.md:98-121`.
- **Running locally without Docker** — current `README.md:122-148`. The five-terminal flow is correct; copy the commands verbatim then add a sentence under each explaining what that terminal does.
- **`make demo`** — current `README.md:159-180`.
- **Multi-consumer mode** — current `README.md:167-180`.
- **Real SDN mode** — current `README.md:181-220`.
- **Changing the AI model** — current `README.md:280-295`.
- **Troubleshooting** — current `README.md:296-311` plus add three from `GUIDE.md §8` if covered there. Each entry: symptom → cause → fix in three short paragraphs.

- [ ] **Step 3: Verify**

```bash
wc -l docs/05-running.md
grep -c "^## " docs/05-running.md
grep -c "^### " docs/05-running.md
```

Expected: 300+ lines, 9 top-level sections, ~25 sub-sections.

- [ ] **Step 4: Commit and push**

```bash
git add docs/05-running.md
git commit -m "$(cat <<'EOF'
docs: add docs/05-running.md (install, run, troubleshoot)

Consolidates the operational content from README.md and GUIDE.md
into one focused doc covering every prerequisite (with verification
commands), the .env, both run modes (Docker + local), make demo,
multi-consumer, real SDN with ContainerLab, model swapping, and
a structured troubleshooting section.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 8: Write `docs/06-modifying.md`

Safe-change guide for contributors. Content can be lifted from `CODEBASE_REFERENCE.md §12` (now `docs/04-architecture.md §12`) but expanded from a checklist to a guide.

**Files:**
- Create: `docs/06-modifying.md`

- [ ] **Step 1: Create the file with this section structure**

```markdown
# Making Safe Changes

> **Audience:** you've decided to change something. This doc tells you what's risky, what's safe, and what to test after each kind of change.

## High-sensitivity files

### Smart contracts (`contracts/src/`)
### A2A executor (`provider/agent_executor.py`)
### Slot pool (`shared/slot_pool.py`)
### MCP servers (`consumer/mcp_server.py`, `provider/mcp_server.py`)
### LangGraph nodes (`consumer/graph.py`)

## Tightly coupled pairs

### Solidity ABI ↔ Python ABI files
### MCP tool signature ↔ both servers
### Agent Card schema ↔ A2A SDK version
### Slot inventory file ↔ `provider/catalog.py`
### Docker entrypoint ↔ `consumer/app.py` / `provider/app.py`

## Test matrix: what to run after each change

| If you change... | Then run... | And manually verify... |
|---|---|---|

## Safe areas (edit freely)
```

- [ ] **Step 2: Required content per high-sensitivity entry**

Each `### High-sensitivity files / X` subsection has three short paragraphs:

```markdown
**Why it's sensitive.** One paragraph naming the failure modes
(e.g., a contract change requires redeploying and updating ABIs;
agent_executor handles the trust boundary between agents).

**What you must check after editing.** Bullet list of concrete checks.

**What is reversible vs. irreversible.** A two-sentence note.
```

Required facts per file:

- **Smart contracts:** any change requires rebuilding ABIs (`forge build`), redeploying (`make contracts` or `make down-clean && make up`), and re-running tests. Storage layout changes are irreversible on a deployed chain — but Anvil resets every `make up` so this is a non-issue here. Verify that the Python `shared/abi/*.json` files match the new ABIs.
- **A2A executor:** this is the trust boundary; an authorisation bug here defeats the whole credential check. Always run `tests/test_agent_executor.py`. Adding new task kinds requires updating both the executor's switch and the consumer side that initiates them.
- **Slot pool:** file-locked shared state; race conditions surface as duplicate allocations. Always run `tests/test_slot_pool.py`. Don't add code paths that mutate `provider/inventory.txt` outside `SlotPool`.
- **MCP servers:** the LLM only sees what's exposed here; adding a tool changes the agent's capability surface. Always run `tests/test_consumer_mcp.py` and `tests/test_provider_mcp.py`. Keep tool descriptions short — they go into the LLM context window on every call.
- **LangGraph nodes:** changing a node changes the workflow; node order is enforced by the graph definition, not by the LLM. Run `tests/test_consumer_graph.py`. Adding a new node requires updating the routing functions too.

- [ ] **Step 3: Required content for the test matrix**

Fill the table with these rows (in order):

| If you change... | Then run... | And manually verify... |
|---|---|---|
| Solidity in `contracts/src/*.sol` | `cd contracts && forge build && forge test`; `make down-clean && make up`; `make demo` | new ABI in `shared/abi/*.json` matches; demo completes |
| `provider/agent_executor.py` | `uv run pytest tests/test_agent_executor.py -v` | `make demo` (full path including activation) |
| `shared/slot_pool.py` | `uv run pytest tests/test_slot_pool.py -v` | `make demo` twice — second run shouldn't double-book |
| `consumer/mcp_server.py` or `provider/mcp_server.py` | `uv run pytest tests/test_consumer_mcp.py tests/test_provider_mcp.py -v` | open `:8002/mcp/list_tools` and confirm the new tool surfaces |
| `consumer/graph.py` | `uv run pytest tests/test_consumer_graph.py -v` | `make demo` |
| `provider/catalog.py` or `provider/inventory.txt` | `uv run pytest tests/test_catalog.py tests/test_slot_pool.py -v` | `make demo` |
| LLM system prompt only | nothing automated | `make demo`, plus eyeball-check the consumer's tier choice |
| README, docs, comments | nothing | open the doc, read it cold |
| Streamlit UI (`consumer/ui.py`) | nothing automated | open `:8501`, click through |
| Docker entrypoints / compose | `docker compose config && docker compose build` | `make up && make demo` |
| `.env.example` | nothing | compare against `docker-compose.yml` env keys |

- [ ] **Step 4: Required safe-areas content**

List these as places you can edit freely:
- All Markdown files in `docs/` (no code depends on them)
- The Streamlit UI text (`consumer/ui.py` strings, except those used as API keys)
- LLM prompts inside `consumer/graph.py` nodes, *as long as you re-run* the consumer-graph tests
- `OLLAMA_MODEL` env var (any model that supports tool calling)
- Anything inside `tests/` (you're improving tests, not breaking code)

- [ ] **Step 5: Verify**

```bash
wc -l docs/06-modifying.md
grep -c "^## " docs/06-modifying.md
grep -c "^### " docs/06-modifying.md
```

Expected: ~200–300 lines, 4 top-level sections, ~10 subsections.

- [ ] **Step 6: Commit and push**

```bash
git add docs/06-modifying.md
git commit -m "$(cat <<'EOF'
docs: add docs/06-modifying.md (safe-change guide)

Documents the high-sensitivity files, tightly coupled pairs, a
change → test matrix mapping every kind of edit to the commands
that verify it, and the safe-to-edit areas.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 9: Write `docs/01-introduction.md` and Rewrite `README.md`, Delete `GUIDE.md`

The introduction is the entry into the docs. The README becomes a short landing page. `GUIDE.md` is removed because its content has now been redistributed across `01`, `02`, `03`, `05`.

**Files:**
- Create: `docs/01-introduction.md`
- Modify: `README.md` (substantial rewrite)
- Delete: `GUIDE.md`

- [ ] **Step 1: Create `docs/01-introduction.md`**

Path: `docs/01-introduction.md`. Length target: ~150–200 lines.

```markdown
# Introduction

## What this project is

Two AI agents — a **buyer** and a **seller** — autonomously negotiate, pay for, and activate a network bandwidth service. The buyer is driven by a local LLM (Ollama). The seller manages an inventory of bandwidth slots. They communicate through a published protocol (A2A), use a smart-contract escrow (running on a local Ethereum chain) to make the trade trust-minimised, and deliver the service through a software-defined-networking (SDN) layer that enforces the bandwidth cap.

The whole system runs on a single laptop. No real money, no real internet bandwidth — but every component (the contracts, the agents, the protocols, the SDN rules) is real code, doing what it would do in production.

## Why it exists

It's the working proof-of-concept that backs the paper *"Autonomous Agent-to-Agent Network Service Provisioning via Smart-Contract Escrow and Tokenized Authorization"* (see `paper/`). The paper argues that future AI agents will trade services with each other and need a payment-and-credential mechanism that doesn't trust either side. This repo demonstrates one such mechanism end-to-end.

## Who this documentation is for

Three reader profiles:

### A. Curious newcomer
You've heard "AI agent" and "blockchain" but you don't write code, or you write code but in a different domain. You want to understand what this project does and how, without slogging through it.

**Read in this order:** README.md → 01-introduction.md (this doc) → 02-concepts.md → 03-walkthrough.md. Stop there. You'll have a solid mental model.

### B. Developer
You want to read or modify the code.

**Read in this order:** README.md → 03-walkthrough.md (skim) → 04-architecture.md → 06-modifying.md. Use 02-concepts.md as a glossary when you hit unfamiliar terms.

### C. Researcher / paper reader
You're checking whether the paper's claims map to working code.

**Read in this order:** README.md → 03-walkthrough.md → 04-architecture.md → paper-alignment.md. The last one specifically tracks where the paper and the code diverge.

## What you'll learn from the docs

- How an LLM running on your laptop can autonomously buy a service from another program.
- Why the project uses **two** different agent protocols (MCP and A2A) and how they fit together.
- How a smart-contract escrow makes a trade *atomic*: the buyer never pays without getting the credential, and the seller never delivers without getting paid.
- What an NFT looks like when it's used as a service credential rather than a collectible.
- How a software-defined network actually enforces the bandwidth cap once the credential is presented.

## Glossary (one-liners)

- **MCP** — the protocol an agent uses to call its *own* tools.
- **A2A** — the protocol agents use to talk to *each other*.
- **Smart contract** — code that runs on a blockchain; here, an escrow that holds money until the trade completes.
- **NFT** — a non-fungible token; here, the buyer's "service ticket".
- **Atomic swap** — money and ticket change hands in one indivisible operation; either both happen or neither does.
- **SDN** — software-defined networking; programmable network rules.
- **Anvil** — a local fake Ethereum chain (no real money, no real chain).

For full explanations, see [`02-concepts.md`](02-concepts.md).
```

- [ ] **Step 2: Rewrite `README.md`**

Replace the entire content of `README.md` with the following. Length target: ~120–160 lines.

```markdown
# Bandwidth Agent Simulation

> Two AI agents negotiate and pay for internet bandwidth — entirely on-chain, running on your laptop.

A working proof-of-concept where a **Consumer AI** and a **Provider AI** interact using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), the [A2A](https://github.com/google/agent-to-agent) protocol, and an Ethereum smart-contract escrow. Settles a real trade (no real money, no real bandwidth — local Anvil chain, mock or real SDN).

This README is a landing page. The full documentation lives in [`docs/`](docs/).

---

## Quickstart

```bash
# 1. Install prereqs (see docs/05-running.md for details):
#    Foundry, Docker, Ollama, uv

# 2. Copy the example env file
cp .env.example .env

# 3. Bring everything up
make up

# 4. Open the UI
xdg-open http://localhost:8501   # or just open it in your browser

# 5. Try the scripted demo (no browser needed)
make demo
```

If `make demo` reports an active service with a `tokenId`, the whole stack works.

To stop everything: `make down` (or `make down-clean` to wipe state too).

---

## Where to read next

| If you want to... | Read |
|---|---|
| Understand what this is and why it exists | [`docs/01-introduction.md`](docs/01-introduction.md) |
| Learn the words used in everything else | [`docs/02-concepts.md`](docs/02-concepts.md) |
| See a successful run, stage by stage | [`docs/03-walkthrough.md`](docs/03-walkthrough.md) |
| Read or modify the code | [`docs/04-architecture.md`](docs/04-architecture.md) |
| Get it running on your machine | [`docs/05-running.md`](docs/05-running.md) |
| Change something safely | [`docs/06-modifying.md`](docs/06-modifying.md) |
| Understand how the code maps to the paper | [`docs/paper-alignment.md`](docs/paper-alignment.md) |

If you've never seen this project before: read those docs in the order listed.

---

## Repo layout

```
.
├── consumer/         # Buyer agent: FastAPI + Ollama + MCP client + A2A client
├── provider/         # Seller agent: FastAPI + MCP server + A2A executor + SDN tools
├── shared/           # Cross-agent code: A2A message types, ABIs, slot pool
├── contracts/        # Solidity contracts (BandwidthEscrow + BandwidthNFT) + Foundry scripts
├── tests/            # Pytest suite covering all of the above
├── docs/             # This documentation set
└── paper/            # Companion research paper (separate git repo)
```

---

## Tech at a glance

- **Python 3.13** with `uv` for environment management
- **FastAPI** for the agent HTTP servers, **Streamlit** for the UI
- **FastMCP** for the MCP servers, **a2a-sdk** for inter-agent calls
- **Ollama** running `qwen3:4b` locally (swappable; see `docs/05-running.md`)
- **Solidity 0.8.x** + **Foundry/Anvil** for the smart-contract layer
- **`tc tbf`** + **gNMI** for SDN bandwidth enforcement (mock by default; real path uses [`srl-gnmi-bandwidth-poc`](https://github.com/musel25/srl-gnmi-bandwidth-poc))

---

## Status

Active prototype on the `feat/mcp-a2a` branch. Companion to a research paper currently in progress (see `paper/`).
```

- [ ] **Step 3: Delete `GUIDE.md`**

```bash
git rm GUIDE.md
```

- [ ] **Step 4: Verify cross-doc links resolve**

```bash
for f in docs/01-introduction.md README.md; do
  echo "--- $f ---"
  grep -oE '\[`?[^]]+`?\]\(([^)]+)\)' "$f"
done
```

Manually confirm each linked path exists. They should be: `docs/01-introduction.md`, `docs/02-concepts.md`, ..., `docs/06-modifying.md`, `docs/paper-alignment.md`.

```bash
ls docs/01-introduction.md docs/02-concepts.md docs/03-walkthrough.md docs/04-architecture.md docs/05-running.md docs/06-modifying.md docs/paper-alignment.md
```

Expected: all seven files exist.

```bash
ls GUIDE.md CODEBASE_REFERENCE.md app.py consumer_agent.py provider_server.py 2>&1
```

Expected: all "No such file or directory".

- [ ] **Step 5: Commit and push**

```bash
git add docs/01-introduction.md README.md
git commit -m "$(cat <<'EOF'
docs: add docs/01-introduction.md, rewrite README.md, delete GUIDE.md

Adds the docs entry point with three reader-profile reading paths.
Rewrites README.md as a short (~150 line) landing page with a
quickstart and a 'where to read next' map. Deletes GUIDE.md whose
content has been redistributed across 01, 02, 03, and 05.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 10: Add Module Docstrings to `consumer/`, `provider/`, `shared/`

The three package `__init__.py` files are currently empty. Add a brief module docstring to each so IDE hover and `help()` are useful.

**Files:**
- Modify: `consumer/__init__.py`
- Modify: `provider/__init__.py`
- Modify: `shared/__init__.py`

- [ ] **Step 1: Write `consumer/__init__.py`**

Replace the empty file content with:

```python
"""
Consumer agent — the buyer side of the bandwidth trade.

This package implements the consumer AI agent: a FastAPI app that
hosts a local MCP server, drives a LangGraph state machine over a
local Ollama LLM, and talks to the provider over A2A.

Entry point:
    consumer.app:app  (uvicorn; port 8001)

Key modules:
    app           — FastAPI app and /chat endpoint
    graph         — LangGraph state machine (browse → quote → lock → settle → present → summary)
    mcp_server    — In-process MCP server exposing tools to the LLM
    a2a_client    — A2A SDK client wrapping calls to the provider
    agent_card    — Builds the published Agent Card

See docs/04-architecture.md for the full picture.
"""
```

- [ ] **Step 2: Write `provider/__init__.py`**

Replace the empty file content with:

```python
"""
Provider agent — the seller side of the bandwidth trade.

This package implements the provider AI agent: a FastAPI app that
hosts an MCP server, an A2A executor, an on-chain event listener,
and SDN activation tools.

Entry point:
    provider.app:app  (uvicorn; port 8002)

Key modules:
    app              — FastAPI app, MCP mount, A2A mount, Agent Card route
    agent_executor   — A2A task handler (quote / activate); the trust boundary
    mcp_server       — MCP server: catalog, quote, mint, verify, allocate
    catalog          — Slot inventory and pricing
    expiry           — Background task: AgreementRequested listener + slot expiry sweep

See docs/04-architecture.md for the full picture.
"""
```

- [ ] **Step 3: Write `shared/__init__.py`**

Replace the empty file content with:

```python
"""
Shared code used by both consumer and provider.

This package holds cross-agent definitions that must stay in sync:
A2A message envelopes, Solidity ABIs, and the file-locked slot pool.

Key modules:
    a2a_messages   — Pydantic models for A2A request/response payloads
    contracts      — Web3 contract loaders and helpers
    slot_pool      — File-locked inventory used by the provider for slot allocation

ABIs are stored as JSON under shared/abi/.

See docs/04-architecture.md for the full picture.
"""
```

- [ ] **Step 4: Verify imports and docstrings load**

```bash
uv run python -c "import consumer, provider, shared; print(consumer.__doc__[:60]); print(provider.__doc__[:60]); print(shared.__doc__[:60])"
```

Expected: three lines printing the first 60 chars of each docstring (no `None`s, no import errors).

```bash
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit and push**

```bash
git add consumer/__init__.py provider/__init__.py shared/__init__.py
git commit -m "$(cat <<'EOF'
docs: add module docstrings to consumer/, provider/, shared/

Each package's __init__.py now states the package's responsibility,
its entry point, and its key modules, with a pointer to
docs/04-architecture.md for details. Makes IDE hover and help()
immediately useful.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Task 11: Final Verification

End-to-end checks before declaring done. No commit; user-facing report only.

- [ ] **Step 1: Confirm all dead/legacy content is gone**

```bash
git ls-files | grep -E '^(app\.py|consumer_agent\.py|provider_server\.py|catalog\.txt|agreements\.json|GUIDE\.md|CODEBASE_REFERENCE\.md|diagnosis\.md)$'
```

Expected: zero output.

- [ ] **Step 2: Confirm all seven docs exist with non-trivial content**

```bash
for f in docs/01-introduction.md docs/02-concepts.md docs/03-walkthrough.md \
         docs/04-architecture.md docs/05-running.md docs/06-modifying.md \
         docs/paper-alignment.md; do
  test -f "$f" && wc -l "$f" || echo "MISSING: $f"
done
```

Expected: all seven exist; line counts roughly:
- `01-introduction.md`: 100–200
- `02-concepts.md`: 600–900
- `03-walkthrough.md`: 400–700
- `04-architecture.md`: 500–650
- `05-running.md`: 300–450
- `06-modifying.md`: 200–350
- `paper-alignment.md`: ~500 (untouched migration)

- [ ] **Step 3: Confirm README is short**

```bash
wc -l README.md
```

Expected: under 200 lines.

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest -q
```

Expected: same pass count as the pre-flight check, no new failures.

- [ ] **Step 5: Confirm Docker images still build**

```bash
docker compose build provider-agent consumer-agent 2>&1 | tail -20
```

Expected: both end with `naming to docker.io/...` (success). No `ERROR` lines.

- [ ] **Step 6: Cross-doc link sanity**

```bash
grep -roE '\]\(([^)]+\.md)\)' docs/ README.md | \
  sed -E 's/.*\]\(([^)]+)\).*/\1/' | sort -u
```

Manually verify each path is a real file relative to the document containing it. (Anchors like `#section-name` may also appear; ignore those.)

- [ ] **Step 7: User-facing demo confirmation**

The assistant cannot run `make demo` (needs the user's local Ollama + Anvil). Report to the user:

> Cleanup complete. Please run `make up && make demo` and confirm the demo still completes end-to-end. If it does, this plan is done.

---

## Self-Review

**Spec coverage:** every numbered section of the spec maps to a task:
- Spec §3.1 README → Task 9 Step 2
- Spec §3.2 introduction → Task 9 Step 1
- Spec §3.3 concepts → Task 5
- Spec §3.4 walkthrough → Task 6
- Spec §3.5 architecture → Task 4
- Spec §3.6 running → Task 7
- Spec §3.7 modifying → Task 8
- Spec §3.8 paper-alignment → Task 3
- Spec §4 module docstrings → Task 10
- Spec §5.1 file removals → Tasks 1, 4, 9
- Spec §5.2 gitignore → Task 2
- Spec §5.3 pyproject → Task 2
- Spec §6 execution order → Tasks 1–10 in the same order
- Spec §7 verification → Task 11
- Spec §9 success criteria → Task 11 steps 1–6 plus the user-facing step 7

No gaps.

**Placeholder scan:** no "TBD", "TODO", "fill in details", "appropriate error handling" patterns. Each doc-writing task has either complete content (Task 9, Task 10) or an explicit outline + per-section content requirements + length target (Tasks 5, 6, 7, 8, the architecture port in Task 4).

**Type/name consistency:** file paths used identically across tasks (`docs/04-architecture.md`, `docs/02-concepts.md`, etc.). Module names match (`consumer.app:app`, `provider.app:app`). Test paths match the actual `tests/` directory.
