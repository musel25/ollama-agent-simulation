# Making Safe Changes

> **Audience:** you've decided to change something. This doc tells you what's risky, what's safe, and what to test after each kind of change.

---

## High-sensitivity files

### Smart contracts (`contracts/src/`)

**Why it's sensitive.** Every field in `BandwidthEscrow.sol` and `BandwidthNFT.sol` has a
corresponding ABI fragment that Python's web3.py uses to encode and decode on-chain calls. A
function signature change, a new parameter, or a renamed event silently breaks the Python side
— the ABI mismatch only surfaces at runtime, often deep inside a transaction that's already been
broadcast. Changing the `Agreement` struct's storage layout on a *deployed* chain is irreversible;
the stored slots are now garbage.

**What you must check after editing.**

- Run `cd contracts && forge build` — compilation failure catches syntax and import errors.
- Run `forge test` inside `contracts/` — unit tests cover the state machine transitions.
- Run `make down-clean && make up` to redeploy a fresh Anvil chain and re-run the deploy script.
- Verify that `shared/abi/BandwidthEscrow.json` and `shared/abi/BandwidthNFT.json` reflect the
  new ABIs. The easiest path: `cp contracts/out/BandwidthEscrow.sol/BandwidthEscrow.json shared/abi/BandwidthEscrow.json` (and equivalent for the NFT).
- Run `make demo` end-to-end to confirm all on-chain calls still succeed.

**Reversible vs. irreversible.** A deployment on Anvil is always reversible because `make up`
resets the chain from scratch. A storage layout change deployed to a real persistent chain
(Sepolia, mainnet) is irreversible without a migration proxy — that concern does not apply here,
but keep it in mind before pointing this code at a live network.

---

### A2A executor (`provider/agent_executor.py`)

**Why it's sensitive.** This file is the trust boundary of the whole system. It is the only
place that routes inbound A2A messages to on-chain or MCP actions. An authorisation bug here
— for example, calling `_handle_activate` without first verifying the credential — defeats the
entire signature-and-ownership check. The executor currently handles three action kinds:
`get_catalog`, `request_quote`, and `activate`. The routing is an explicit `if/elif` block;
there is no reflection or auto-discovery.

**What you must check after editing.**

- Run `uv run pytest tests/test_agent_executor.py -v`.
- If you add a new action kind, update the `if/elif` block in `execute()` *and* update the
  consumer side (`consumer/a2a_client.py` and the relevant `consumer/graph.py` node) that
  constructs the request dict.
- After any logic change, run `make demo` and walk the full path including the `activate` step.

**Reversible vs. irreversible.** Logic changes are fully reversible via git. An authorisation
regression that ships to a production deployment can result in credential misuse before you
notice — the consequence is operational, not on-chain state, so a rollback redeploy fixes it.

---

### Slot pool (`shared/slot_pool.py`)

**Why it's sensitive.** `SlotPool` is file-backed shared state: `provider/inventory.txt` is
read and written by both the API process and potentially background expiry jobs. Every
read-modify-write uses `fcntl.LOCK_EX` to prevent concurrent modifications, but any new code
path that touches the JSONL rows without going through `SlotPool` methods bypasses the lock and
can produce duplicate allocations or silently drop a release. Race conditions here manifest as
two consumers sharing the same `(pe, subinterface)` slot.

**What you must check after editing.**

- Run `uv run pytest tests/test_slot_pool.py -v`.
- Never mutate `provider/inventory.txt` outside the `SlotPool` class methods (`reserve`,
  `release`, `lookup`, `tiers`, `expired_agreement_ids`).
- Run `make demo` twice in quick succession — the second run should obtain a different
  slot, not re-use the one still held by the first run's agreement.

**Reversible vs. irreversible.** Code changes are reversible. If `inventory.txt` is corrupted
by a buggy write, you can restore it from the git-tracked copy. Do not add `inventory.txt` to
`.gitignore`; it is intentionally tracked so a corrupted runtime state can be diagnosed.

---

### MCP servers (`consumer/mcp_server.py`, `provider/mcp_server.py`)

**Why it's sensitive.** The LLM only sees the tools registered with `@mcp.tool()`. Adding,
removing, or renaming a tool changes the agent's capability surface — and the tool's docstring
goes into the context window on every single invocation. A verbose description inflates token
usage and may push important prior context out of the window. The consumer MCP server also
holds an in-process `quote_cache` dict; code that bypasses this cache will cause `lock_payment`
to fail with "no cached quote".

**What you must check after editing.**

- Run `uv run pytest tests/test_consumer_mcp.py tests/test_provider_mcp.py -v`.
- For **consumer** changes: re-run `tests/test_consumer_graph.py` — the LangGraph nodes import
  consumer MCP tools directly, so a missing tool surfaces as a Python `ImportError` or
  `AttributeError` there. For **provider** changes: run `make demo` end-to-end and confirm the
  catalog/quote/activate paths still work; a removed provider tool surfaces as an MCP
  `tools/call` error from the consumer.
- Keep tool docstrings short and specific — one sentence that tells the LLM *what* the tool
  does, not *how* it is implemented.

**Reversible vs. irreversible.** All changes here are code-only and fully reversible. However,
removing a tool that `consumer/graph.py` calls by name will break the graph at runtime, not at
import time — the error only surfaces when that node executes.

---

### LangGraph nodes (`consumer/graph.py`)

**Why it's sensitive.** The state machine's edge order is enforced by the graph definition in
`build_graph()`, not by the LLM. Changing a node's inputs or outputs can silently corrupt the
`WorkflowState` dict that flows between nodes. Adding a new node without wiring its
conditional edges means it is either unreachable or the graph fails to compile. The LLM is only
called in `pick_tier_node` and `summary_node`; all other nodes are deterministic Python.

**What you must check after editing.**

- Run `uv run pytest tests/test_consumer_graph.py -v`.
- If you add a new node, update `build_graph()` with both `add_node` and the appropriate
  `add_conditional_edges` or `add_edge` call. Failing to wire edges causes a
  `langgraph.errors.InvalidUpdateError` at compile time.
- Run `make demo` to verify the full six-stage workflow completes.

**Reversible vs. irreversible.** All graph changes are code-only and reversible. A broken
graph compilation raises immediately on startup, so a broken build cannot silently accumulate
on-chain state.

---

## Tightly coupled pairs

### Solidity ABI ↔ Python ABI files

**What's coupled.** `contracts/src/BandwidthEscrow.sol` and `contracts/src/BandwidthNFT.sol`
compile to ABI JSON artifacts. `shared/abi/BandwidthEscrow.json` and
`shared/abi/BandwidthNFT.json` are the copies Python reads via `shared/contracts.py`. They must
stay in sync.

**Symptom of forgetting.** `web3.py` raises `ABIFunctionNotFound` or encodes arguments with
the wrong selector, causing transaction reverts. The error surfaces on the first on-chain call,
not at import time.

**Where to update both.** After `forge build`, the fresh ABIs land in
`contracts/out/BandwidthEscrow.sol/BandwidthEscrow.json` (and equivalent for the NFT). Copy
them to `shared/abi/` before running any Python tests.

---

### MCP tool signature ↔ both servers

**What's coupled.** If you rename or re-parameterise a tool in `provider/mcp_server.py`, the
call site in `provider/agent_executor.py` (which calls tools by string name) must be updated.
Likewise, if a tool exposed by `provider/mcp_server.py` is renamed, `consumer/mcp_server.py`
(which calls the provider via A2A) and `consumer/graph.py` (which calls consumer MCP tools by
name) must be updated together.

**Symptom of forgetting.** A `ToolNotFoundError` or a Python `TypeError` about unexpected
keyword arguments. The error only occurs when the affected graph node runs.

**Where to update both.** Search for the old tool name as a string literal across
`provider/agent_executor.py`, `consumer/mcp_server.py`, and `consumer/graph.py` before
committing.

---

### Agent Card schema ↔ A2A SDK version

**What's coupled.** `consumer/agent_card.py` and `provider/agent_card.py` construct A2A
`AgentCard` objects whose field names are tied to the `a2a-sdk` version pinned in
`pyproject.toml`. Bumping the SDK can rename or remove fields.

**Symptom of forgetting.** An `AttributeError` or `TypeError` at service startup when the
agent card is constructed, before any request is handled.

**Where to update both.** When bumping `a2a-sdk`, read the SDK changelog, then diff both
`agent_card.py` files against the new `AgentCard` class definition.

---

### Slot inventory file ↔ `provider/catalog.py`

**What's coupled.** `provider/inventory.txt` is JSONL; each line has keys `tier`, `mbps`,
`durationSeconds`, and `slots` (a list of objects with `pe`, `subinterface`, `ce`,
`agreementId`, `expiresAt`). `shared/slot_pool.py` reads this format directly. Adding a column
or changing a key name requires updating the parser in `SlotPool`.

**Symptom of forgetting.** A `KeyError` when `slot_pool.tiers()` or `slot_pool.reserve()` runs,
which bubbles up as an HTTP 500 on the provider's catalog endpoint.

**Where to update both.** Edit `shared/slot_pool.py` first, then update `inventory.txt` (and
the git-tracked copy) to match.

---

### Docker entrypoint ↔ `consumer/app.py` / `provider/app.py`

**What's coupled.** `Dockerfile.consumer` ends with
`CMD ["uvicorn", "consumer.app:app", ...]` and `Dockerfile.provider` with
`CMD ["uvicorn", "provider.app:app", ...]`. These strings name the Python module path and the
FastAPI object. Renaming either the module or the `app` variable breaks the container.

**Symptom of forgetting.** The container exits immediately with
`ModuleNotFoundError: No module named 'consumer.app'` (or similar), visible in
`docker compose logs`.

**Where to update both.** Rename the module or variable in the Python file, then update the
`CMD` in the corresponding Dockerfile in the same commit.

---

## Test matrix: what to run after each change

| If you change... | Then run... | And manually verify... |
|---|---|---|
| Solidity in `contracts/src/*.sol` | `cd contracts && forge build && forge test`; `make down-clean && make up`; `make demo` | New ABI in `shared/abi/*.json` matches; demo completes end-to-end |
| `provider/agent_executor.py` | `uv run pytest tests/test_agent_executor.py -v` | `make demo` (full path including activation) |
| `shared/slot_pool.py` | `uv run pytest tests/test_slot_pool.py -v` | `make demo` twice — second run should not double-book the same slot |
| `consumer/mcp_server.py` | `uv run pytest tests/test_consumer_mcp.py tests/test_consumer_graph.py -v` | `make demo` (the LangGraph nodes import these tools directly; a missing tool fails on graph import) |
| `provider/mcp_server.py` | `uv run pytest tests/test_provider_mcp.py -v` | `make demo` end-to-end; a removed tool surfaces as an MCP `tools/call` error from the consumer |
| `consumer/graph.py` | `uv run pytest tests/test_consumer_graph.py -v` | `make demo` |
| `provider/catalog.py` or `provider/inventory.txt` | `uv run pytest tests/test_catalog.py tests/test_slot_pool.py -v` | `make demo` |
| LLM system prompt only | nothing automated | `make demo`, then eyeball the consumer's tier choice in the logs |
| README, docs, comments | nothing | Open the doc and read it cold |
| Streamlit UI (`consumer/ui.py`) | nothing automated | Open `:8501`, click through the full flow |
| Docker entrypoints / compose | `docker compose config && docker compose build` | `make up && make demo` |
| `.env.example` | nothing | Compare against the `environment:` keys in `docker-compose.yml` |

---

## Safe areas (edit freely)

These files have no downstream code dependencies — a mistake here does not break tests or
runtime behaviour, and no other module reads their content.

- **All Markdown files in `docs/`** — no code imports or parses them.
- **Streamlit UI strings in `consumer/ui.py`** — label text, help strings, and display
  formatting. Do not change the variable names that are used as dictionary keys or API
  arguments.
- **LLM prompts inside `consumer/graph.py` nodes** — the prompt strings passed to `_llm_complete`
  are safe to tune *as long as you re-run* `uv run pytest tests/test_consumer_graph.py -v`
  afterwards to confirm the node still returns a valid `WorkflowState` update.
- **`OLLAMA_MODEL` env var** — swap to any Ollama model that supports tool calling (e.g.
  `llama3.2:1b`, `llama3.2:3b`). No code change required.
- **Anything inside `tests/`** — improving test coverage or fixing test helpers cannot break
  production code. You are editing the verification layer, not the thing being verified.
