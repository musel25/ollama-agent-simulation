# Repo Cleanup and Documentation Restructure — Design

**Status:** Approved 2026-05-03
**Goal:** Make the repository clean, minimal, and fully documented for a reader who arrives with zero prior knowledge.

---

## 1. Problem

The repo has accumulated three classes of clutter that make it hard to onboard, maintain, or reason about:

1. **Dead code at the root.** `app.py`, `consumer_agent.py`, `provider_server.py`, `catalog.txt`, `agreements.json` are a pre-MCP prototype. Nothing in the active code path imports them; current entry points are `consumer.app:app`, `provider.app:app`, and `consumer/ui.py`. Both `CODEBASE_REFERENCE.md §1/§11` and `diagnosis.md §6` already declare them dead.
2. **Hygiene gaps.** `.claude/`, `.pytest_cache/`, `.venv/` are not in `.gitignore`. `pyproject.toml` still ships the `uv init` placeholder description. `diagnosis.md` is untracked at the root.
3. **Documentation overlap and drift.** Three large top-level docs — `README.md` (316 lines), `GUIDE.md` (1152 lines), `CODEBASE_REFERENCE.md` (635 lines) — independently describe the same architecture, file tree, and concepts. They drift apart with every change. None of them targets a true beginner without making knowledge assumptions.

Out of scope: the `paper/` submodule (left untouched per user decision; it has a missing `.gitmodules` but that's a separate concern).

---

## 2. Goals

- Remove all dead code and runtime scratch files from the tracked tree.
- Replace the three overlapping top-level docs with a multi-file documentation set under `docs/`, structured so each file has one purpose.
- Write the new docs for a reader with **zero prior knowledge** of blockchain, agents, MCP, A2A, Solidity, Python tooling, or SDN — every concept introduced before it's used.
- Keep `README.md` short: one-paragraph what-it-is, quickstart, and a map pointing to `docs/`.
- Verify the working stack still builds and runs after cleanup.

Non-goals: refactoring application code, changing the architecture, adding evaluation harnesses, fixing the `paper/` submodule, addressing the paper↔code discrepancies tracked in `diagnosis.md` (those move into `docs/paper-alignment.md` unchanged).

---

## 3. Target Documentation Structure

```
README.md                          # ~150 lines — entry point + quickstart + roadmap to docs/
docs/
├── 01-introduction.md             # What this is, who it's for, reading order
├── 02-concepts.md                 # Every concept explained from zero
├── 03-walkthrough.md              # End-to-end narrative of a successful run
├── 04-architecture.md             # Technical reference (replaces CODEBASE_REFERENCE.md)
├── 05-running.md                  # Install + run + troubleshoot
├── 06-modifying.md                # How to safely change things
└── paper-alignment.md             # Migrated from root diagnosis.md
```

### 3.1 README.md (~150 lines)

The landing page. Keeps only:
- One-paragraph "what it is" (autonomous agent-to-agent bandwidth purchase, on-chain escrow + NFT, local LLM).
- Three-line quickstart (`cp .env.example .env && make up && open http://localhost:8501`).
- A "Where to read next" section listing each doc in `docs/` with one line about what it covers.
- License / "see also" links.

Removes from current README: the architecture explanation, file structure, prerequisites depth, troubleshooting (all migrated to dedicated docs).

### 3.2 docs/01-introduction.md

Sets context for a reader who has no idea what this is.

Sections:
- **What this project is** — a working prototype showing two AI agents (a buyer and a seller) negotiating and settling a network-bandwidth purchase autonomously, backed by a smart contract.
- **Why it exists** — companion implementation to a research paper on agent-to-agent network service provisioning.
- **Who this documentation is for** — three reader profiles (curious newcomer, developer, researcher) with a recommended reading path for each.
- **What you'll learn by reading the docs** — a checklist (you will understand: what blockchain escrow does here, why MCP and A2A are different, how a single Ollama call leads to an Ethereum transaction).
- **Glossary of one-liners** — pointer into `02-concepts.md` for full explanations.

### 3.3 docs/02-concepts.md

The most critical doc. Explains every concept used in the rest of the project, **in the order a beginner would encounter them**, each in 50–200 words with a concrete tiny example.

Order matters: each concept must be explained before the next concept that depends on it.

Concept list (grouped, but presented as a flat numbered list in the doc):

- **Programming and runtime:** Python, virtual environment, uv, pyproject.toml, FastAPI, Uvicorn, Streamlit, HTTPX, Docker, Docker Compose, environment variable.
- **AI / agents:** LLM, Ollama, prompt, tool calling, agent, model context.
- **Inter-agent protocols:** MCP (Model Context Protocol — agent's local tools), A2A (Agent-to-Agent — between agents), why both are needed and how they differ.
- **Blockchain:** Ethereum, smart contract, Solidity, transaction, gas, private key and signing, nonce (chain), event, RPC, Anvil, Foundry / Forge.
- **Tokens and NFTs:** ERC-721, NFT as a credential, ownership check.
- **Payment and escrow:** escrow, atomic swap, deposit/refund, status state machine (NONE → REQUESTED → ACTIVE).
- **Networking and SDN:** REST API, port, SDN, traffic shaping (`tc tbf`), gNMI, ContainerLab, mock vs real activation.
- **State machines:** what they are and how this project uses three of them simultaneously (Solidity contract, slot pool, agent workflow).

Each concept entry has the same shape: **one-line definition → 2–4 sentences elaboration → "in this project" pointer** to where it shows up.

### 3.4 docs/03-walkthrough.md

A narrative trace of one successful run, written as a story.

Structure:
- **The setup** — services running, what each one is doing while idle.
- **The user's request** — "I need 5 Mbps for 10 minutes" typed in the UI.
- **Stage 1 — Discovery:** consumer browses provider's catalog (with the actual MCP/A2A messages shown).
- **Stage 2 — Quote and lock:** consumer requests a quote, locks payment in escrow.
- **Stage 3 — Credential issuance:** provider listens to the chain event and mints the NFT.
- **Stage 4 — Atomic swap:** the contract atomically pays the provider and delivers the NFT.
- **Stage 5 — Activation:** consumer presents the credential; provider verifies on-chain ownership and applies the SDN rule.
- **Stage 6 — Consumption + expiry:** the user's traffic flows; the slot expires and the credential transitions out of ACTIVE.

Each stage shows: an ASCII sequence diagram, the relevant log lines, and a short reflection on which concepts from `02-concepts.md` are at play.

### 3.5 docs/04-architecture.md

Technical reference for developers. This is a refresh of `CODEBASE_REFERENCE.md` with the legacy-code section deleted and any drift corrected against the current code on `feat/mcp-a2a`.

Sections (preserved from current `CODEBASE_REFERENCE.md`):
- Project identity
- Tech stack summary
- Full directory tree (legacy entries removed)
- Architecture & patterns (A2A inter-agent + per-agent MCP)
- Entry points (provider boot, consumer boot, contract deployment)
- Data models (Solidity structs, Python dataclasses, MCP tool I/O shapes)
- API & interfaces (provider :8002 routes, consumer :8001 routes, MCP tool catalog per agent, contract function signatures)
- State management (provider-side, consumer-side, UI session)
- Dependency map (key imports per file, most-imported modules)
- Configuration & environment (env vars, config files, Docker networking)
- Known quirks & constraints

### 3.6 docs/05-running.md

Operational reference.

Sections:
- **Prerequisites** — Foundry, Docker, Ollama, uv. For each: what it is (one line, with link to `02-concepts.md`), how to install it on Linux/macOS/Windows, how to verify the install.
- **Configuring** — `.env` file, what each variable does, which ones must be set vs which have defaults.
- **Running with Docker** — `make up`, what it brings up, expected boot sequence.
- **Running locally without Docker** — five-terminal flow (anvil, deploy, provider, consumer, UI).
- **Verifying it works** — `make demo`, expected output stage by stage.
- **Multi-consumer mode** — `--profile multi-consumer`, the second consumer at `:8011`.
- **Real SDN mode** — `make demo-real`, ContainerLab prerequisites, the `iperf3` verification.
- **Changing the AI model** — `OLLAMA_MODEL`, model size trade-offs, how to swap.
- **Troubleshooting** — common failures by symptom: provider unreachable, deployer hangs, model pull fails, anvil port collision, contract deployment fails.

### 3.7 docs/06-modifying.md

Safe-change guide for contributors.

Sections:
- **High-sensitivity files** — what changes carry risk and why (contracts, agent_executor, slot_pool).
- **Tightly coupled pairs** — when changing X you must also change Y (e.g., contract ABI ↔ Python ABI files; MCP tool signatures ↔ both servers).
- **What to test after each kind of change** — change matrix: contract change → reset deployments + rerun demo; consumer prompt → rerun demo + spot-check; new MCP tool → unit test + integration test; etc.
- **Safe areas** — places you can edit freely without breaking things (UI text, comments, README, model parameters).

### 3.8 docs/paper-alignment.md

Direct migration of `diagnosis.md`. No content changes in this PR; only the file location moves and any inline references to its old path are updated.

---

## 4. Per-Package Module Docstrings

Each of `consumer/__init__.py`, `provider/__init__.py`, `shared/__init__.py` gets a module docstring (5–15 lines) stating:
- The package's responsibility in one sentence.
- The entry-point module (e.g., `consumer.app` for the FastAPI app).
- A pointer to `docs/04-architecture.md` for the full picture.

This makes IDE hover and `help(package)` immediately useful without making readers leave the code.

---

## 5. Cleanup Actions

### 5.1 Files removed

```
app.py
consumer_agent.py
provider_server.py
catalog.txt
agreements.json
GUIDE.md
CODEBASE_REFERENCE.md
diagnosis.md            # moved to docs/paper-alignment.md, not deleted
```

### 5.2 `.gitignore` additions

```
.claude/
.pytest_cache/
.venv/
```

### 5.3 `pyproject.toml`

Replace `description = "Add your description here"` with a one-line description matching the README opening sentence.

---

## 6. Execution Order

Each step is a separate commit on the current branch (`feat/mcp-a2a`).

1. `chore: remove legacy pre-MCP prototype files` — delete the five legacy files.
2. `chore: tighten gitignore and pyproject metadata` — add the three ignore entries, fix the description.
3. `docs: move diagnosis.md to docs/paper-alignment.md` — single git mv + path-reference fixups.
4. `docs: add docs/04-architecture.md replacing CODEBASE_REFERENCE.md` — port content, fix drift, then `git rm CODEBASE_REFERENCE.md`.
5. `docs: add docs/02-concepts.md` — the concepts primer.
6. `docs: add docs/03-walkthrough.md` — the narrative trace.
7. `docs: add docs/05-running.md` — the install/run reference.
8. `docs: add docs/06-modifying.md` — the safe-change guide.
9. `docs: add docs/01-introduction.md and rewrite README.md` — landing page + intro; then `git rm GUIDE.md`.
10. `docs: add module docstrings to consumer/, provider/, shared/`.

`GUIDE.md` is removed in step 9, *after* its content has been redistributed across the new docs, so no information disappears.

---

## 7. Verification

Performed after step 10, before declaring done:

- `uv run pytest` — must pass with the same set of tests passing as before (zero new failures).
- `docker compose build` — must succeed for both `provider-agent` and `consumer-agent` images.
- A spot-check that `make demo` runs end-to-end. This requires the user's local environment (Ollama, Anvil), so this step is performed by the user; the assistant prepares but does not run it.
- Manual readability pass on each new doc, in reading order, with no other context — does it stand on its own?

---

## 8. Risks and Mitigations

- **Risk:** Some current README content (e.g., a clever troubleshooting note) gets lost in the split.
  - **Mitigation:** Before step 9, every section of the current README, GUIDE, and CODEBASE_REFERENCE is mapped to its destination doc; nothing is dropped without an explicit "redundant" note in the implementation plan.
- **Risk:** Docs drift from code again.
  - **Mitigation:** The split reduces overlap surface; any future architectural change touches at most one or two docs (`04` for code-level, `03` for narrative). README is too short to drift.
- **Risk:** Removing `app.py` etc. breaks an undocumented user workflow (e.g., someone running `streamlit run app.py`).
  - **Mitigation:** Verified zero references in the active stack. The diagnosis doc and codebase reference both already declare these files dead. No mitigation needed beyond the verification already done.
- **Risk:** Long docs are written but not proofread, hurting the very beginner audience they target.
  - **Mitigation:** Each doc gets a final readability pass after writing, against the criterion "could a reader who has never seen this project follow this in order without getting stuck."

---

## 9. Success Criteria

The cleanup is done when:

1. `git ls-files | grep -E '^(app\.py|consumer_agent\.py|provider_server\.py|catalog\.txt|agreements\.json|GUIDE\.md|CODEBASE_REFERENCE\.md|diagnosis\.md)$'` returns nothing.
2. `docs/` contains the seven files listed in §3.
3. `README.md` is under 200 lines.
4. `uv run pytest` and `docker compose build` both succeed.
5. A first-time reader can follow `README → 01 → 02 → 03` and reach the end with a working mental model of the project, without needing to read external resources for the core concepts.
