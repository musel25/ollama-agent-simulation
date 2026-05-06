# Repo Cleanup, Modularization, and In-Process Notebooks — Design

**Date:** 2026-05-06
**Status:** Approved (pending implementation plan)

## Summary

Refactor the repo so every Python module is importable with no side effects, all configuration flows through one `Config` dataclass, and a Jupyter reader can run the entire stack — Anvil chain, MCP server, A2A client, LangGraph agent, end-to-end trade — from in-process notebooks with no Docker. Strip stale docs, dead code, and unused config. Collapse documentation to four living files. Replace the old "walkthrough" doc with a notebook.

## Goals

1. **Side-effect-free imports.** `from consumer.graph import build_graph` must not connect to Anvil, Ollama, or the network.
2. **Single source of config.** One `shared/config.py` dataclass; every module accepts it as a parameter; no scattered `os.getenv` calls.
3. **Notebook parity.** Five `notebooks/*.ipynb` files cover chain, MCP, A2A, consumer graph, and end-to-end — all in-process, no Docker required.
4. **Minimal surface area.** Delete dead code, unused env vars, duplicated services, and redundant docs.
5. **Tight docs.** Four canonical docs (intro, concepts, architecture, running). Walkthrough lives in notebook 05.

## Non-Goals

- Migrating to a `src/` layout. Existing top-level packages (`consumer/`, `provider/`, `shared/`) stay.
- Refactoring the Streamlit UI (`consumer/ui.py`). Out of scope.
- Replacing FastAPI / FastMCP / a2a-sdk / web3 / LangGraph.
- Introducing new abstractions (`SessionState`, `Signer` protocol, `Panel` class).
- Re-pinning dependencies with version ceilings — `uv.lock` is authoritative.

## Deletions

| Path / item | Reason |
|---|---|
| `docs/superpowers/plans/*.md` (all) | Old internal plans; do not reflect current code |
| `docs/superpowers/specs/*.md` (prior, not this one) | Superseded |
| `docs/paper-alignment.md` | Pre-refactor checklist of completed work |
| `docs/03-walkthrough.md` | Replaced by `notebooks/05_end_to_end.ipynb` |
| `docs/06-modifying.md` | Folded into `03-architecture.md` |
| `consumer-agent-2` service in `docker-compose.yml` | Undocumented and unused |
| `PROVIDER_AGENT_CARD_URL` env var | Defined in `.env.example` and `docker-compose.yml` but never read |
| Unused imports: `Web3` (`consumer/ui.py`), `ParseDict` (`provider/agent_executor.py`), `import json as _json` alias (`provider/app.py`) | Dead code |
| Trivial single-assert tests (`test_catalog_has_three_tiers`, `test_catalog_by_id_has_all_tiers`) | Fold into one parametrized smoke test in `tests/test_catalog.py` |

`.solc-cache/`, `.pytest_cache/`, and `.superpowers/` are added to `.gitignore` if not already.

## Architecture

### New modules in `shared/`

**`shared/config.py`** — frozen dataclass `Config` with fields: `rpc_url`, `ollama_host`, `ollama_model`, `consumer_private_key`, `provider_private_key`, `deployer_private_key`, `escrow_address`, `nft_address`, `sdn_mock`. Classmethod `Config.from_env()` reads `os.environ`. All modules that previously called `os.getenv` accept a `Config` parameter instead.

**`shared/anvil.py`** — context manager `anvil(port: int = 8545)` that spawns the `anvil` binary as a subprocess, waits for the JSON-RPC port to accept connections, yields the RPC URL, and terminates the process on exit. Used by notebooks and `tests/test_end_to_end.py`.

**`shared/deploy.py`** — `deploy_contracts(cfg: Config) -> tuple[str, str]` invokes `forge script script/Deploy.s.sol --rpc-url <cfg.rpc_url> --broadcast --private-key <cfg.deployer_private_key>` via subprocess and parses the broadcast JSON to return `(escrow_address, nft_address)`. Replaces the Makefile-only deploy path.

### Modified modules

**`shared/chain.py`** — replace module-level `_w3` with `make_web3(cfg: Config) -> Web3`. Keep `send_tx` and `load_abi` as pure helpers. No state at module scope.

**`consumer/graph.py`** — export `build_graph(cfg, mcp_tools, a2a_client) -> CompiledGraph`. No module-level Ollama client. Tier-picking helpers (`_deterministic_tier_pick`, `_rank_catalog`) move to a new `consumer/tier_selection.py`.

**`consumer/mcp_server.py`** — factory `build_mcp_server(cfg) -> FastMCP`. No module state.

**`consumer/a2a_client.py`** — factory `make_a2a_client(provider_url) -> A2AClient`.

**`consumer/app.py`** — FastAPI `lifespan` builds `Config.from_env()`, the MCP server, the A2A client, and the graph once at startup and stashes them on `app.state`. Endpoints become thin handlers that read from `app.state`.

**`provider/app.py`** — same `lifespan` pattern. The event-listener loop is extracted (see below).

**`provider/event_listener.py`** (NEW) — `async def run(cfg: Config, slot_pool)` contains the agreement-event watcher that currently lives inline in `provider/app.py`. Owns its own retry/log loop.

**`provider/mcp_server.py`** — factory `build_mcp_server(cfg, catalog, slot_pool) -> FastMCP`.

### Unchanged

- `shared/contracts.py`, `shared/slot_pool.py`, `shared/a2a_messages.py`
- `consumer/agent_card.py`, `consumer/ui.py`
- `provider/agent_card.py`, `provider/agent_executor.py`, `provider/catalog.py`, `provider/expiry.py`
- All `contracts/src/*.sol` and `contracts/script/Deploy.s.sol`

### Comments & docstrings

- Every public function (no leading `_`) gets a one-line docstring stating what it returns or does.
- No narrative WHAT-comments. Keep WHY-comments where the reasoning is non-obvious (e.g. the `fcntl` block in `slot_pool.py`).
- All stale TODOs are removed or converted into GitHub issues if the user wants to keep them.

## Notebooks

Path: `notebooks/`. Every notebook follows **Setup → Build → Run → Inspect → Teardown**, with teardown in a `try/finally`.

| File | In-process components | What it teaches |
|---|---|---|
| `01_chain.ipynb` | Anvil subprocess | Deploy escrow + NFT via `shared.deploy`. Walk one trade: open agreement → settle → mint NFT. Decode events. |
| `02_mcp.ipynb` | Provider's `FastMCP` server (in-memory transport if available, threaded localhost otherwise) | Build the MCP server via `provider.mcp_server.build_mcp_server`. Call each tool directly. Show how a client discovers the tool list. |
| `03_a2a.ipynb` | Provider FastAPI app via `httpx.ASGITransport` (or threaded uvicorn fallback) | Resolve agent card. Send a Message via `a2a-sdk`. Walk executor lifecycle. |
| `04_consumer_graph.ipynb` | Anvil + provider FastAPI in-process + stub LLM | Build the LangGraph state machine via `consumer.graph.build_graph`. Step through nodes with `graph.stream(...)`. Render `graph.get_graph().draw_mermaid()`. |
| `05_end_to_end.ipynb` | All of the above + real Ollama | The same trade as `make demo`, driven from Python end-to-end. |

`notebooks/README.md` lists prerequisites (`anvil` binary in `$PATH`, optional `ollama` running) and the recommended run order.

## Tests

- `tests/conftest.py` (NEW) — shared fixtures: `cfg` (default `Config` for tests), `fake_catalog`, `anvil_chain` (uses `shared.anvil`), `deployed_contracts` (uses `shared.deploy`).
- `tests/test_end_to_end.py` (NEW) — single integration test mirroring notebook 05 with a stubbed LLM. Spawns Anvil, deploys contracts, instantiates both FastAPI apps in-process, runs one negotiation, asserts on-chain state.
- Existing unit tests keep their scope. Trivial single-assert tests are dropped or parametrized.
- LLM is never called in tests (always stubbed).

## Documentation

Final `docs/` tree (existing `04-architecture.md` is renumbered to `03-architecture.md` after `03-walkthrough.md` is deleted; existing `05-running.md` is renumbered to `04-running.md`):

```
docs/
├── 01-introduction.md     # what this is, why, where things live
├── 02-concepts.md         # MCP, A2A, escrow, slot pool — the vocabulary
├── 03-architecture.md     # how components fit; includes "where to make changes"
└── 04-running.md          # Docker path AND notebook path, side by side
```

`README.md` updated to point at the new docs and the notebooks. The pre-existing `docs/superpowers/specs/` directory keeps only this spec.

## Order of Implementation

1. **Sweep deletions** — old docs, plans, specs, dead env vars, dead imports, `consumer-agent-2`. Run `make demo` to confirm nothing broke.
2. **Add `shared/config.py`** and thread it through one module at a time. Run tests after each.
3. **Make modules side-effect-free.** `shared/chain.py` → `provider/*` → `consumer/*`. Convert module-level state to factories.
4. **Extract** `provider/event_listener.py` and `consumer/tier_selection.py`.
5. **Add `shared/anvil.py` and `shared/deploy.py`.**
6. **Update tests** — `conftest.py`, drop trivial tests, add `tests/test_end_to_end.py`.
7. **Rewrite docs** — collapse to four files; update `README.md`.
8. **Write notebooks** — `01` through `05`.
9. **Final verification** — `make demo` works, full test suite passes, all five notebooks run top-to-bottom from a clean clone.

## Risks

- **FastMCP in-memory transport may not exist in the pinned version.** Fallback: notebook 02 spawns the server on a localhost port via `threading` — still in-process, just over loopback.
- **`a2a-sdk` may require a real HTTP transport.** Same fallback: threaded uvicorn on a loopback port for notebook 03.
- **Ollama dependency in notebook 05.** Acceptable — it is the "real" demo notebook and prerequisites are documented. CI never depends on Ollama because tests stub the LLM.
- **`forge` binary required for `shared/deploy.py`.** Documented as a notebook prerequisite alongside `anvil`. (Both come from the same Foundry install.)

## Success Criteria

- `from consumer.graph import build_graph` and equivalents do not open sockets, spawn processes, or read files at import time.
- `grep -r "os.getenv" consumer/ provider/ shared/` returns zero hits outside `shared/config.py`.
- `docs/` contains exactly four `.md` files plus `superpowers/specs/` containing only this spec.
- `notebooks/` contains five executable notebooks; each one runs top-to-bottom on a clean checkout with only `anvil` (and Ollama for `05`) as external dependencies.
- `make demo` still passes.
- `uv run pytest` passes.
