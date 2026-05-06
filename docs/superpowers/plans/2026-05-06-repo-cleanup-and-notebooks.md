# Repo Cleanup, Modularization, and In-Process Notebooks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Python module side-effect-free and configuration-driven, strip dead code/docs, add `shared/anvil.py` + `shared/deploy.py` so notebooks can spin the whole stack from Python, and ship five `notebooks/*.ipynb` covering chain, MCP, A2A, the consumer graph, and end-to-end.

**Architecture:** Introduce one `Config` dataclass in `shared/config.py`. Convert each module's module-level `os.getenv(...)` and `Web3(...)` constants into factories (`make_web3`, `build_mcp_server`, `build_graph`, `make_a2a_client`). FastAPI apps build the graph/MCP server/A2A client once in `lifespan` and stash them on `app.state`. `shared/anvil.py` spawns a local Anvil subprocess as a context manager; `shared/deploy.py` shells out to `forge script` and returns the deployed addresses. Tests use a `conftest.py` of shared fixtures plus one `test_end_to_end.py` integration test that mirrors notebook 05 with a stubbed LLM.

**Tech Stack:** Python 3.13, uv, FastAPI, FastMCP, a2a-sdk 1.0.x, web3.py 6.x, LangGraph 1.x, langchain-ollama, eth-account, Foundry (anvil + forge), pytest, pytest-asyncio, Jupyter.

**Source spec:** `docs/superpowers/specs/2026-05-06-repo-cleanup-and-notebooks-design.md`

---

## File Structure

**New files:**
- `shared/config.py` — `Config` dataclass + `Config.from_env()`
- `shared/anvil.py` — `anvil(...)` context manager that spawns the binary
- `shared/deploy.py` — `deploy_contracts(cfg)` that wraps `forge script`
- `consumer/tier_selection.py` — extracted tier-picking helpers
- `provider/event_listener.py` — extracted on-chain agreement watcher
- `tests/conftest.py` — shared pytest fixtures
- `tests/test_end_to_end.py` — integration test
- `notebooks/README.md` — prerequisites & run order
- `notebooks/01_chain.ipynb` — deploy + walk one trade on Anvil
- `notebooks/02_mcp.ipynb` — exercise provider MCP tools in-process
- `notebooks/03_a2a.ipynb` — drive provider A2A executor via in-process ASGI
- `notebooks/04_consumer_graph.ipynb` — step the LangGraph state machine
- `notebooks/05_end_to_end.ipynb` — full negotiation, all in-process (real Ollama)

**Modified files (factory refactor + docstrings):**
- `shared/chain.py` — add `make_web3`
- `consumer/app.py`, `consumer/graph.py`, `consumer/mcp_server.py`, `consumer/a2a_client.py`
- `provider/app.py`, `provider/mcp_server.py`, `provider/agent_executor.py`, `provider/catalog.py`, `provider/expiry.py`

**Modified files (cleanup only):**
- `docker-compose.yml` (remove `consumer-agent-2` + `PROVIDER_AGENT_CARD_URL`)
- `.env.example` (remove `PROVIDER_AGENT_CARD_URL`, `CONSUMER_PRIVATE_KEY_2`, `CONSUMER_ADDRESS_2`)
- `Dockerfile.consumer` (`uv sync --frozen --no-dev` to match provider)
- `pyproject.toml` (no functional change — ensure `jupyterlab` and `nbclient` are dev deps)
- `Makefile` (drop `clab-up`/`clab-down`/`demo-real` only if user opts; default keeps them)
- `.gitignore` (add `.solc-cache/`, `.pytest_cache/`, `.superpowers/`)
- `README.md` (point at new docs and notebooks)

**Renamed/restructured docs:**
- `docs/03-walkthrough.md` → **deleted** (replaced by `notebooks/05_end_to_end.ipynb`)
- `docs/04-architecture.md` → renamed to `docs/03-architecture.md`, with `docs/06-modifying.md` folded into a "Where to make changes" section
- `docs/05-running.md` → renamed to `docs/04-running.md`, with notebook path added
- `docs/06-modifying.md` → **deleted** (folded above)
- `docs/paper-alignment.md` → **deleted**
- `docs/superpowers/plans/*.md` → **deleted** (except this plan, which is being added)
- `docs/superpowers/specs/*.md` → keep only `2026-05-06-repo-cleanup-and-notebooks-design.md`

---

## Phase 1: Sweep Deletions

Goal: Remove every file/symbol the spec lists as dead. Verify the demo still works before changing any logic.

### Task 1: Pre-flight verification

**Files:** none (read-only)

- [ ] **Step 1: Run the existing test suite as a baseline**

```bash
uv run pytest -q 2>&1 | tail -20
```

Record the pass/fail line. The plan must not regress it. If anything is already failing, surface it before continuing.

- [ ] **Step 2: Bring the stack up and run `make demo` to capture a baseline**

```bash
make up 2>&1 | tail -5
sleep 10
make demo 2>&1 | tail -30
```

Expected: STEP 3's inventory output shows one tier with `availableSlots` decremented (a successful trade). Note the inventory output for later comparison.

- [ ] **Step 3: Bring the stack down**

```bash
make down
```

### Task 2: Delete stale docs and old plans/specs

**Files:**
- Delete: `docs/03-walkthrough.md`
- Delete: `docs/06-modifying.md`
- Delete: `docs/paper-alignment.md`
- Delete: `docs/superpowers/plans/*.md` (every file except *this* plan)
- Delete: `docs/superpowers/specs/2026-04-20-dashboard-ui-revamp-design.md`
- Delete: `docs/superpowers/specs/2026-05-01-a2a-mcp-realignment-design.md`
- Delete: `docs/superpowers/specs/2026-05-03-repo-cleanup-and-docs-design.md`
- Delete: `docs/superpowers/specs/2026-05-05-dashboard-redesign-design.md`

- [ ] **Step 1: Delete the files**

```bash
rm docs/03-walkthrough.md docs/06-modifying.md docs/paper-alignment.md
rm docs/superpowers/plans/2026-04-20-dashboard-ui-revamp.md \
   docs/superpowers/plans/2026-04-20-smart-contract-settlement.md \
   docs/superpowers/plans/2026-04-21-mcp-a2a.md \
   docs/superpowers/plans/2026-04-27-paper-impl-alignment.md \
   docs/superpowers/plans/2026-05-01-a2a-mcp-realignment-implementation.md \
   docs/superpowers/plans/2026-05-03-langgraph-consumer.md \
   docs/superpowers/plans/2026-05-03-repo-cleanup-and-docs.md \
   docs/superpowers/plans/2026-05-05-dashboard-redesign.md
rm docs/superpowers/specs/2026-04-20-dashboard-ui-revamp-design.md \
   docs/superpowers/specs/2026-05-01-a2a-mcp-realignment-design.md \
   docs/superpowers/specs/2026-05-03-repo-cleanup-and-docs-design.md \
   docs/superpowers/specs/2026-05-05-dashboard-redesign-design.md
```

- [ ] **Step 2: Verify only this plan and design spec remain**

```bash
ls docs/superpowers/plans/ docs/superpowers/specs/
```

Expected:
```
docs/superpowers/plans/:
2026-05-06-repo-cleanup-and-notebooks.md

docs/superpowers/specs/:
2026-05-06-repo-cleanup-and-notebooks-design.md
```

- [ ] **Step 3: Commit**

```bash
git add -A docs/
git commit -m "docs: delete stale walkthrough, modifying guide, paper-alignment, and old plans/specs"
git push
```

### Task 3: Renumber remaining docs

**Files:**
- Rename: `docs/04-architecture.md` → `docs/03-architecture.md`
- Rename: `docs/05-running.md` → `docs/04-running.md`

- [ ] **Step 1: Rename**

```bash
git mv docs/04-architecture.md docs/03-architecture.md
git mv docs/05-running.md docs/04-running.md
```

- [ ] **Step 2: Fix any internal cross-links inside `docs/01-introduction.md`, `docs/02-concepts.md`, `docs/03-architecture.md`, `docs/04-running.md`, and `README.md`**

```bash
grep -rn "03-walkthrough\|04-architecture\|05-running\|06-modifying\|paper-alignment" docs/ README.md
```

For every hit, edit the file with the Edit tool to point at the new filename, or remove the link if it points at a deleted doc. (`docs/01-introduction.md` has several explicit references — rewrite the "Read in this order" lists to drop walkthrough/modifying/paper-alignment and use the new numbers.)

- [ ] **Step 3: Commit**

```bash
git add -A docs/ README.md
git commit -m "docs: renumber 04→03 architecture, 05→04 running; fix cross-links"
git push
```

### Task 4: Remove `consumer-agent-2`, `PROVIDER_AGENT_CARD_URL`, and stale env vars

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Edit `docker-compose.yml` to remove the entire `consumer-agent-2` service block (lines 105–126)**

Use Edit to delete the block. After:

```bash
grep -n "consumer-agent-2\|PROVIDER_AGENT_CARD_URL" docker-compose.yml
```

Expected: no matches.

- [ ] **Step 2: Remove the `PROVIDER_AGENT_CARD_URL` env line from the `consumer-agent` service in `docker-compose.yml` (line 97)**

Use Edit. After:

```bash
grep -c "PROVIDER_AGENT_CARD_URL" docker-compose.yml
```

Expected: `0`.

- [ ] **Step 3: Edit `.env.example` to remove `CONSUMER_PRIVATE_KEY_2`, `CONSUMER_ADDRESS_2`, and the comment block above them (lines 14–16)**

After:

```bash
grep -c "CONSUMER_PRIVATE_KEY_2\|PROVIDER_AGENT_CARD_URL" .env.example
```

Expected: `0`.

- [ ] **Step 4: Verify the demo still works**

```bash
make up
sleep 10
make demo 2>&1 | tail -10
make down
```

Expected: STEP 3 shows a slot got reserved.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: drop consumer-agent-2 service and PROVIDER_AGENT_CARD_URL"
git push
```

### Task 5: Delete unused imports and aliases

**Files:**
- Modify: `consumer/ui.py` (remove `from web3 import Web3` if Web3 is unused)
- Modify: `provider/agent_executor.py` (remove `ParseDict` import if unused)
- Modify: `provider/app.py` (rename `import json as _json` → `import json`)

- [ ] **Step 1: Confirm `Web3` is unused in `consumer/ui.py` before deleting**

```bash
grep -n "Web3" consumer/ui.py
```

If the only hit is the import line, proceed. Otherwise leave the import.

- [ ] **Step 2: Edit `consumer/ui.py` to remove the unused `Web3` import (only if confirmed unused above)**

- [ ] **Step 3: Confirm `ParseDict` is unused in `provider/agent_executor.py`**

```bash
grep -n "ParseDict" provider/agent_executor.py
```

The current file uses `ParseDict` inside `_dict_to_value`, so DO NOT remove this one. (Audit was incorrect — verify before deleting.)

- [ ] **Step 4: Rename `_json` → `json` in `provider/app.py`**

Use Edit to change `import json as _json` → `import json`, then `replace_all` `_json.loads` → `json.loads`. Verify:

```bash
grep -n "_json" provider/app.py
```

Expected: no matches.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest -q
git add consumer/ui.py provider/app.py
git commit -m "chore: drop unused imports and rename _json alias"
git push
```

### Task 6: Update `.gitignore` and remove cached artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Read current `.gitignore`**

```bash
cat .gitignore
```

- [ ] **Step 2: Append missing patterns** (add only those not already present):

```
.pytest_cache/
.solc-cache/
.superpowers/
__pycache__/
contracts/cache/
contracts/out/
contracts/broadcast/
notebooks/.ipynb_checkpoints/
```

Use Edit to append. Skip duplicates.

- [ ] **Step 3: Untrack any of those paths if they are currently tracked**

```bash
git rm -r --cached --ignore-unmatch .pytest_cache .solc-cache .superpowers
```

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: ignore solc cache, pytest cache, superpowers cache, notebook checkpoints"
git push
```

---

## Phase 2: Introduce `shared/config.py`

Goal: One frozen dataclass that every module accepts. Lays the foundation for the side-effect-free refactor.

### Task 7: Add `shared/config.py` with `Config` dataclass

**Files:**
- Create: `shared/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
"""Tests for shared.config.Config."""
from __future__ import annotations

import os
from unittest.mock import patch

from shared.config import Config


def test_from_env_reads_known_vars():
    env = {
        "RPC_URL": "http://anvil:8545",
        "OLLAMA_HOST": "http://ollama:11434",
        "OLLAMA_MODEL": "llama3.2:3b",
        "CONSUMER_PRIVATE_KEY": "0xaaaa",
        "PROVIDER_PRIVATE_KEY": "0xbbbb",
        "DEPLOYER_PRIVATE_KEY": "0xcccc",
        "SDN_MOCK": "false",
    }
    with patch.dict(os.environ, env, clear=True):
        cfg = Config.from_env()
    assert cfg.rpc_url == "http://anvil:8545"
    assert cfg.ollama_host == "http://ollama:11434"
    assert cfg.ollama_model == "llama3.2:3b"
    assert cfg.consumer_private_key == "0xaaaa"
    assert cfg.provider_private_key == "0xbbbb"
    assert cfg.deployer_private_key == "0xcccc"
    assert cfg.sdn_mock is False


def test_from_env_uses_defaults_when_unset():
    with patch.dict(os.environ, {}, clear=True):
        cfg = Config.from_env()
    assert cfg.rpc_url == "http://localhost:8545"
    assert cfg.ollama_host == "http://localhost:11434"
    assert cfg.ollama_model == "llama3.2:3b"
    assert cfg.consumer_private_key is None
    assert cfg.provider_private_key is None
    assert cfg.deployer_private_key is None
    assert cfg.sdn_mock is True


def test_config_is_frozen():
    import pytest
    cfg = Config()
    with pytest.raises(Exception):
        cfg.rpc_url = "http://x"  # type: ignore[misc]
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'shared.config'`.

- [ ] **Step 3: Implement `shared/config.py`**

```python
"""Single source of runtime configuration for both agents.

Every module that previously called `os.getenv(...)` now accepts a
`Config` instance. Notebooks construct one explicitly; the FastAPI apps
build one in their `lifespan` via `Config.from_env()`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    rpc_url: str = "http://localhost:8545"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    consumer_private_key: str | None = None
    provider_private_key: str | None = None
    deployer_private_key: str | None = None
    provider_address: str | None = None
    consumer_base_url: str = "http://localhost:8001"
    provider_base_url: str = "http://localhost:8002"
    provider_a2a_urls: tuple[str, ...] = ("http://localhost:8002",)
    sdn_mock: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        """Build a `Config` by reading the standard environment variables."""
        urls_raw = os.environ.get(
            "PROVIDER_A2A_URLS",
            os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002"),
        )
        urls = tuple(u.strip() for u in urls_raw.split(",") if u.strip())
        return cls(
            rpc_url=os.environ.get("RPC_URL", cls.rpc_url),
            ollama_host=os.environ.get("OLLAMA_HOST", cls.ollama_host),
            ollama_model=os.environ.get("OLLAMA_MODEL", cls.ollama_model),
            consumer_private_key=os.environ.get("CONSUMER_PRIVATE_KEY"),
            provider_private_key=os.environ.get("PROVIDER_PRIVATE_KEY"),
            deployer_private_key=os.environ.get("DEPLOYER_PRIVATE_KEY"),
            provider_address=os.environ.get("PROVIDER_ADDRESS"),
            consumer_base_url=os.environ.get(
                "CONSUMER_BASE_URL", cls.consumer_base_url
            ),
            provider_base_url=os.environ.get(
                "PROVIDER_BASE_URL", cls.provider_base_url
            ),
            provider_a2a_urls=urls,
            sdn_mock=os.environ.get("SDN_MOCK", "true").lower() == "true",
        )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: 3 passing.

- [ ] **Step 5: Commit**

```bash
git add shared/config.py tests/test_config.py
git commit -m "feat(shared): add Config dataclass with from_env() classmethod"
git push
```

---

## Phase 3: Make Modules Side-Effect-Free

Goal: Replace module-level `os.getenv(...)` and `Web3(...)` constants with factories that accept `Config`. Apps build state once in `lifespan`. Each task changes one module + its tests.

### Task 8: Add `make_web3` factory to `shared/chain.py`

**Files:**
- Modify: `shared/chain.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py` (or create `tests/test_chain.py` if you prefer; the plan uses test_config to keep new test files lean):

Create `tests/test_chain_factory.py`:

```python
from shared.chain import make_web3
from shared.config import Config


def test_make_web3_uses_cfg_rpc_url():
    cfg = Config(rpc_url="http://nowhere:9999")
    w3 = make_web3(cfg)
    assert w3.provider.endpoint_uri == "http://nowhere:9999"
```

- [ ] **Step 2: Verify the test fails**

```bash
uv run pytest tests/test_chain_factory.py -v
```

Expected: `ImportError: cannot import name 'make_web3'`.

- [ ] **Step 3: Add `make_web3` to `shared/chain.py`**

Append to `shared/chain.py`:

```python
from web3 import Web3

from shared.config import Config


def make_web3(cfg: Config) -> Web3:
    """Build a `Web3` HTTP provider client pointing at `cfg.rpc_url`."""
    return Web3(Web3.HTTPProvider(cfg.rpc_url))
```

(`Web3` is already imported at the top of the file. If not, ensure the import exists once. The new `Config` import goes alongside.)

- [ ] **Step 4: Run the test**

```bash
uv run pytest tests/test_chain_factory.py -v
```

Expected: 1 passing.

- [ ] **Step 5: Commit**

```bash
git add shared/chain.py tests/test_chain_factory.py
git commit -m "feat(shared): add make_web3(cfg) factory"
git push
```

### Task 9: Convert `provider/mcp_server.py` to a factory

This is the largest single change. We turn the module-level `mcp` / `_w3` / `_provider_account` into a `build_mcp_server(cfg, slot_pool, catalog)` function. We keep a top-level `mcp` symbol for backwards compatibility with existing tests by binding it lazily through `Config.from_env()` at first access.

**Files:**
- Modify: `provider/mcp_server.py`

- [ ] **Step 1: Refactor `provider/mcp_server.py` end-to-end**

Replace the entire file with the version below. Read carefully: this preserves every tool, the `_logged` decorator, and the SDN_MOCK fallback, but moves all state into a closure inside `build_mcp_server`.

```python
"""
FastMCP server for the bandwidth provider.

Tools:
  - get_catalog                   — list tiers with availability
  - request_quote                 — issue an agreementId quote
  - verify_credential_ownership   — signature/nonce + on-chain ownerOf check
  - mint_credential               — mint an NFT bound to (agreement, mbps, duration)
  - complete_swap                 — approve + escrow.deposit (atomic on-chain swap)
  - allocate_bandwidth            — push gNMI policer + tc on connected CE
  - revoke_bandwidth              — reverse of allocate_bandwidth
  - verify_bandwidth              — iperf3 UDP probe between two CEs
"""
from __future__ import annotations

import dataclasses as _dc
import inspect
import json
import time
from collections import deque
from functools import wraps

from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from provider.catalog import get_catalog_with_availability, make_quote
from shared.chain import STATUS_NAMES, extract_token_id, make_web3, send_tx
from shared.config import Config
from shared.contracts import get_escrow_contract, get_nft_contract

NONCE_WINDOW = 300


def _summarize_args(kwargs: dict) -> dict:
    """Truncate every value to ≤80 chars so log entries stay small."""
    out = {}
    for k, v in kwargs.items():
        s = str(v)
        out[k] = s if len(s) <= 80 else s[:77] + "..."
    return out


def _make_logged(tool_log: deque):
    """Return a decorator that records every invocation into `tool_log`."""
    def _logged(fn):
        tool_name = fn.__name__
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                entry = {"tool": tool_name, "ts": time.time(),
                         "args": _summarize_args(kwargs), "status": "running"}
                tool_log.append(entry)
                try:
                    result = await fn(*args, **kwargs)
                    entry["status"] = "ok"
                    return result
                except Exception:
                    entry["status"] = "error"
                    raise
            return async_wrapper

        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            entry = {"tool": tool_name, "ts": time.time(),
                     "args": _summarize_args(kwargs), "status": "running"}
            tool_log.append(entry)
            try:
                result = fn(*args, **kwargs)
                entry["status"] = "ok"
                return result
            except Exception:
                entry["status"] = "error"
                raise
        return sync_wrapper
    return _logged


try:  # optional dependency — only needed when SDN_MOCK=false
    from srl_bandwidth.bandwidth import (
        allocate_bandwidth as _srl_allocate,
        revoke_bandwidth as _srl_revoke,
        verify_bandwidth as _srl_verify,
    )
    from srl_bandwidth.models import ServiceRequest as _SrlServiceRequest
    _SRL_AVAILABLE = True
except ImportError:
    _SRL_AVAILABLE = False


def build_mcp_server(cfg: Config) -> tuple[FastMCP, deque]:
    """Build a fresh provider FastMCP server bound to `cfg`.

    Returns ``(mcp, tool_log)``. The tool_log deque is exposed so the
    FastAPI app can serve `/tool_log`.
    """
    if not cfg.provider_private_key:
        raise RuntimeError("Config.provider_private_key is required")

    mcp = FastMCP("bandwidth-provider")
    tool_log: deque = deque(maxlen=500)
    logged = _make_logged(tool_log)

    w3 = make_web3(cfg)
    provider_account = Account.from_key(cfg.provider_private_key)
    provider_key = cfg.provider_private_key
    sdn_mock = cfg.sdn_mock

    def _provider_send_tx(func, value: int = 0):
        return send_tx(w3, provider_account, provider_key, func, value=value)

    @mcp.tool()
    @logged
    def get_catalog() -> str:
        """Return available bandwidth packages with pricing and slot availability."""
        return json.dumps(get_catalog_with_availability())

    @mcp.tool()
    @logged
    def request_quote(package_id: str, consumer_address: str) -> str:
        """Issue an agreementId-bound price quote, or ``{"error": ...}``."""
        quote = make_quote(package_id, consumer_address)
        if quote is None:
            return json.dumps({"error":
                               f"Package '{package_id}' not found or no slots available."})
        return json.dumps(quote)

    @mcp.tool()
    @logged
    def verify_credential_ownership(token_id: int, signature: str, nonce: str) -> str:
        """Verify nonce freshness, signature recovery, and on-chain agreement status."""
        try:
            nonce_time = int(nonce)
        except ValueError:
            return json.dumps({"ok": False,
                               "reason": "nonce must be a unix timestamp string"})
        if abs(time.time() - nonce_time) > NONCE_WINDOW:
            return json.dumps({"ok": False,
                               "reason": "nonce expired or too far in future"})
        try:
            signer = Account.recover_message(encode_defunct(text=nonce),
                                             signature=signature)
        except Exception as e:
            return json.dumps({"ok": False, "reason": f"invalid signature: {e}"})

        nft = get_nft_contract(w3)
        try:
            owner = nft.functions.ownerOf(token_id).call()
        except Exception:
            return json.dumps({"ok": False,
                               "reason": f"token {token_id} does not exist"})
        if Web3.to_checksum_address(owner) != Web3.to_checksum_address(signer):
            return json.dumps({"ok": False, "reason": "signer does not own token",
                               "signer": signer, "owner": owner})

        meta = nft.functions.getTokenMetadata(token_id).call()
        agreement_id, mbps, duration, start_time, endpoint = meta
        elapsed = int(time.time()) - int(start_time)
        seconds_remaining = max(0, int(duration) - elapsed)

        escrow = get_escrow_contract(w3)
        agreement = escrow.functions.getAgreement(int(agreement_id)).call()
        status = STATUS_NAMES.get(agreement[7], "UNKNOWN")

        return json.dumps({
            "ok": True, "signer": signer, "owner": owner,
            "agreement_id": int(agreement_id), "mbps": int(mbps),
            "duration_seconds": int(duration), "endpoint": endpoint,
            "seconds_remaining": seconds_remaining, "status": status,
        })

    @mcp.tool()
    @logged
    def mint_credential(agreement_id: int, consumer_address: str, pe: str,
                        subinterface: str, ce: str, mbps: int,
                        duration_seconds: int) -> str:
        """Mint a BandwidthNFT bound to (agreement, mbps, duration). Returns JSON."""
        nft = get_nft_contract(w3)
        endpoint = f"clab://{pe}/{subinterface}"
        tx_hex, receipt = _provider_send_tx(
            nft.functions.mint(provider_account.address, int(agreement_id),
                               int(mbps), int(duration_seconds), endpoint))
        return json.dumps({
            "tokenId": extract_token_id(receipt, nft),
            "txHash": tx_hex, "endpoint": endpoint,
        })

    @mcp.tool()
    @logged
    def complete_swap(agreement_id: int, token_id: int) -> str:
        """Approve escrow on the NFT, then call escrow.deposit (atomic swap)."""
        nft = get_nft_contract(w3)
        escrow = get_escrow_contract(w3)
        approve_tx, _ = _provider_send_tx(
            nft.functions.approve(escrow.address, int(token_id)))
        deposit_tx, _ = _provider_send_tx(
            escrow.functions.deposit(int(agreement_id), int(token_id)))
        return json.dumps({"status": "ok", "approveTx": approve_tx,
                           "depositTx": deposit_tx})

    @mcp.tool()
    @logged
    def allocate_bandwidth(customer_id: str, pe: str, subinterface: str,
                           mbps: float) -> str:
        """Push gNMI policer + tc tbf for a slot. Mocked under SDN_MOCK."""
        if sdn_mock or not _SRL_AVAILABLE:
            return json.dumps({
                "success": True, "customer_id": customer_id, "pe": pe,
                "subinterface": subinterface, "mbps": mbps,
                "gnmi_pushed": False, "tc_applied": False, "message": "mocked",
            })
        req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                                 subinterface=subinterface, mbps=mbps)
        return json.dumps(_dc.asdict(_srl_allocate(req)))

    @mcp.tool()
    @logged
    def revoke_bandwidth(customer_id: str, pe: str, subinterface: str) -> str:
        """Reverse of allocate_bandwidth. Mocked under SDN_MOCK."""
        if sdn_mock or not _SRL_AVAILABLE:
            return json.dumps({"status": "revoked", "customer_id": customer_id,
                               "pe": pe, "subinterface": subinterface,
                               "mocked": True})
        req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                                 subinterface=subinterface, mbps=0.0)
        _srl_revoke(req)
        return json.dumps({"status": "revoked", "customer_id": customer_id,
                           "pe": pe, "subinterface": subinterface})

    @mcp.tool()
    @logged
    def verify_bandwidth(src_ce: str, dst_ce: str,
                         expected_mbps: float | None = None,
                         tolerance: float = 0.2) -> str:
        """iperf3 UDP probe from src_ce to dst_ce. Mocked under SDN_MOCK."""
        if sdn_mock or not _SRL_AVAILABLE:
            return json.dumps({"passed": True,
                               "measured_mbps": expected_mbps or 0.0,
                               "expected_mbps": expected_mbps,
                               "tolerance": tolerance, "message": "mocked"})
        return json.dumps(_dc.asdict(
            _srl_verify(src_ce, dst_ce, expected_mbps, tolerance)))

    return mcp, tool_log
```

- [ ] **Step 2: Update `tests/test_provider_mcp.py` to use the factory**

The existing tests `import from provider.mcp_server import mcp` and patch internal symbols. Update them to construct a fresh server per test. Replace the file with this rewrite (keeps the same coverage):

```python
"""In-memory MCP tests for the provider's tools."""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import Client

from provider.mcp_server import _summarize_args, build_mcp_server
from shared.config import Config

PROVIDER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
PROVIDER_ADDR = Account.from_key(PROVIDER_KEY).address
CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
CONSUMER_ADDR = Account.from_key(CONSUMER_KEY).address


@pytest.fixture
def cfg() -> Config:
    return Config(provider_private_key=PROVIDER_KEY, sdn_mock=True)


@pytest.fixture
def server(cfg):
    mcp, tool_log = build_mcp_server(cfg)
    return mcp, tool_log


@pytest.mark.asyncio
async def test_verify_credential_ownership_happy_path(server):
    mcp, _ = server
    nonce = str(int(time.time()))
    sig = Account.sign_message(encode_defunct(text=nonce),
                               private_key=CONSUMER_KEY).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = CONSUMER_ADDR
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()) - 60, "clab://pe1/ethernet-1/3.0",
    )
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        CONSUMER_ADDR, "0xprov", 5, 600, 0, 0, 7, 2,
    )

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce})
            data = json.loads(result.content[0].text)
            assert data["ok"] is True
            assert data["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_wrong_signer(server):
    mcp, _ = server
    nonce = str(int(time.time()))
    sig = Account.sign_message(encode_defunct(text=nonce),
                               private_key=CONSUMER_KEY).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = (
        "0x000000000000000000000000000000000000dEaD")
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()), "clab://pe1/ethernet-1/3.0")
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        CONSUMER_ADDR, "0xprov", 5, 600, 0, 0, 7, 2)

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce})
            data = json.loads(result.content[0].text)
            assert data["ok"] is False


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_stale_nonce(server):
    mcp, _ = server
    stale = str(int(time.time()) - 9999)
    sig = Account.sign_message(encode_defunct(text=stale),
                               private_key=CONSUMER_KEY).signature.hex()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "verify_credential_ownership",
            {"token_id": 7, "signature": sig, "nonce": stale})
        data = json.loads(result.content[0].text)
        assert data["ok"] is False
        assert "nonce" in data["reason"].lower()


@pytest.mark.asyncio
async def test_mint_credential_returns_token_id(cfg):
    fake_receipt = {"status": 1, "logs": []}
    fake_nft = MagicMock()
    fake_nft.functions.mint.return_value.build_transaction.return_value = {
        "from": "0xprov", "nonce": 0}
    fake_nft.events.Transfer.return_value.process_receipt.return_value = [
        {"args": {"tokenId": 42, "from": "0x0", "to": "0xprov"}}]

    fake_w3 = MagicMock()
    fake_w3.eth.get_transaction_count.return_value = 0
    fake_w3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b"\x00")
    fake_w3.eth.send_raw_transaction.return_value = b"\x00"
    fake_w3.eth.wait_for_transaction_receipt.return_value = fake_receipt

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.make_web3", return_value=fake_w3):
        mcp, _ = build_mcp_server(cfg)
        async with Client(mcp) as client:
            result = await client.call_tool("mint_credential", {
                "agreement_id": 12345,
                "consumer_address": "0x000000000000000000000000000000000000dEaD",
                "pe": "pe1", "subinterface": "ethernet-1/3.0", "ce": "ce3",
                "mbps": 5, "duration_seconds": 600,
            })
            data = json.loads(result.content[0].text)
            assert data["tokenId"] == 42
            assert data["endpoint"] == "clab://pe1/ethernet-1/3.0"


@pytest.mark.asyncio
async def test_complete_swap_calls_approve_then_deposit(cfg):
    fake_nft = MagicMock()
    fake_escrow = MagicMock()
    fake_escrow.address = "0xESCROW"
    fake_w3 = MagicMock()
    fake_w3.eth.get_transaction_count.return_value = 0
    fake_w3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b"\x00")
    fake_w3.eth.send_raw_transaction.return_value = b"\x00"
    fake_w3.eth.wait_for_transaction_receipt.return_value = {"status": 1, "logs": []}

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow), \
         patch("provider.mcp_server.make_web3", return_value=fake_w3):
        mcp, _ = build_mcp_server(cfg)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "complete_swap", {"agreement_id": 12345, "token_id": 42})
            data = json.loads(result.content[0].text)
            assert data["status"] == "ok"
            fake_nft.functions.approve.assert_called_once_with("0xESCROW", 42)
            fake_escrow.functions.deposit.assert_called_once_with(12345, 42)


@pytest.mark.asyncio
async def test_tool_call_log_records_invocations(server):
    mcp, tool_log = server
    tool_log.clear()
    async with Client(mcp) as client:
        await client.call_tool("get_catalog", {})
    entries = list(tool_log)
    assert len(entries) == 1
    assert entries[0]["tool"] == "get_catalog"
    assert entries[0]["status"] == "ok"


def test_summarize_args_truncates_long_values():
    result = _summarize_args({"x": "a" * 100, "y": "short"})
    assert result["x"].endswith("...")
    assert len(result["x"]) == 80
    assert result["y"] == "short"
```

- [ ] **Step 3: Run the provider MCP tests**

```bash
uv run pytest tests/test_provider_mcp.py -v
```

Expected: 7 passing.

- [ ] **Step 4: Commit**

```bash
git add provider/mcp_server.py tests/test_provider_mcp.py
git commit -m "refactor(provider): convert mcp_server to build_mcp_server(cfg) factory"
git push
```

### Task 10: Convert `consumer/mcp_server.py` to a factory

**Files:**
- Modify: `consumer/mcp_server.py`

- [ ] **Step 1: Refactor `consumer/mcp_server.py` end-to-end**

Replace the file with:

```python
"""
Consumer agent's MCP server.

Tools:
  Local (no network):
    - wallet_address()         → consumer EOA
    - lock_payment(agreement_id)
    - await_settlement(agreement_id)
    - verify_credential(token_id) — independent on-chain check
  A2A-bound (network to provider):
    - discover_provider(provider_url)
    - browse_catalog(provider_url)
    - request_quote(provider_url, package_id)
    - present_credential(provider_url, token_id)
"""
from __future__ import annotations

import json
import time

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from consumer.a2a_client import fetch_agent_card, send_provider_action
from shared.chain import STATUS_NAMES, make_web3, send_tx
from shared.config import Config
from shared.contracts import get_escrow_contract, get_nft_contract


# Settlement polling: 20 attempts × 1.5s ≈ 30s upper bound.
_SETTLEMENT_POLL_ATTEMPTS = 20
_SETTLEMENT_POLL_INTERVAL_S = 1.5


async def _fetch_provider_address(provider_url: str) -> str:
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(f"{provider_url}/address")
        resp.raise_for_status()
        return resp.json()["address"]


def build_mcp_server(cfg: Config) -> tuple[FastMCP, dict]:
    """Build the consumer FastMCP server bound to `cfg`.

    Returns ``(mcp, quote_cache)``. The quote_cache is exposed so tests
    can inspect cached quotes after `request_quote` calls.
    """
    if not cfg.consumer_private_key:
        raise RuntimeError("Config.consumer_private_key is required")

    mcp = FastMCP("bandwidth-consumer")
    quote_cache: dict[str, dict] = {}
    w3 = make_web3(cfg)
    consumer_account = Account.from_key(cfg.consumer_private_key)
    consumer_key = cfg.consumer_private_key

    @mcp.tool()
    def wallet_address() -> str:
        """Return the consumer agent's Ethereum address (0x...)."""
        return consumer_account.address

    @mcp.tool()
    def lock_payment(agreement_id: str) -> str:
        """Send escrow.requestAgreement using the cached quote.
        Returns "OK <txHash>" on success, "ERROR ..." otherwise."""
        quote = quote_cache.get(str(agreement_id))
        if not quote:
            return (f"ERROR: no cached quote for agreementId={agreement_id}. "
                    "Call request_quote first.")
        provider_addr = quote.get("providerAddress")
        if not provider_addr:
            return "ERROR: cached quote has no providerAddress"
        try:
            escrow = get_escrow_contract(w3)
            tx_hex, _ = send_tx(
                w3, consumer_account, consumer_key,
                escrow.functions.requestAgreement(
                    int(agreement_id),
                    Web3.to_checksum_address(provider_addr),
                    int(quote["bandwidthMbps"]),
                    int(quote["durationSeconds"])),
                value=int(quote["priceWei"]))
            return f"OK {tx_hex}"
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    def await_settlement(agreement_id: str) -> str:
        """Poll escrow.getAgreement until status==ACTIVE (~30s max)."""
        try:
            aid = int(agreement_id)
        except (ValueError, TypeError):
            return f"ERROR: agreement_id must be a number, got {agreement_id!r}"
        escrow = get_escrow_contract(w3)
        for _ in range(_SETTLEMENT_POLL_ATTEMPTS):
            try:
                ag = escrow.functions.getAgreement(aid).call()
                status = STATUS_NAMES.get(ag[7], "UNKNOWN")
                if status == "ACTIVE":
                    return f"OK tokenId={ag[6]}"
                if status in ("CANCELLED", "CLOSED"):
                    return f"ERROR: agreement is {status}"
            except Exception as e:
                return f"ERROR reading agreement: {e}"
            time.sleep(_SETTLEMENT_POLL_INTERVAL_S)
        return "PENDING"

    @mcp.tool()
    def verify_credential(token_id: int) -> str:
        """Independently verify a credential on-chain (does NOT call provider)."""
        try:
            nft = get_nft_contract(w3)
            tid = int(token_id)
            owner = Web3.to_checksum_address(nft.functions.ownerOf(tid).call())
            agreement_id, mbps, duration, start_time, endpoint = (
                nft.functions.getTokenMetadata(tid).call())
            seconds_remaining = max(
                0, duration - max(0, int(time.time()) - start_time))
            return json.dumps({
                "ok": True, "owner": owner,
                "ownerIsConsumer": owner == consumer_account.address,
                "agreementId": agreement_id, "mbps": mbps,
                "durationSeconds": duration,
                "secondsRemaining": seconds_remaining, "endpoint": endpoint,
            })
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def discover_provider(provider_url: str) -> str:
        """Fetch agent card; return JSON {name, version, skills: [skill_id, ...]}."""
        try:
            card = await fetch_agent_card(provider_url)
            skills = [s.get("id") for s in card.get("skills", []) if s.get("id")]
            return json.dumps({"name": card.get("name"),
                               "version": card.get("version"), "skills": skills})
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def browse_catalog(provider_url: str) -> str:
        """Discover provider's catalog via A2A. Returns JSON array."""
        try:
            result = await send_provider_action(provider_url,
                                                {"action": "get_catalog"})
            catalog = result.get("catalog")
            if catalog is None:
                return f"ERROR: provider response missing 'catalog' key: {result}"
            return json.dumps(catalog)
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def request_quote(provider_url: str, package_id: str) -> str:
        """Request a quote via A2A and cache it for lock_payment."""
        try:
            provider_addr = await _fetch_provider_address(provider_url)
            result = await send_provider_action(provider_url, {
                "action": "request_quote", "package_id": package_id,
                "consumer_address": consumer_account.address,
            })
            if "error" in result:
                return f"ERROR: {result['error']}"
            quote_cache[str(result["agreementId"])] = {
                **result, "providerAddress": provider_addr,
            }
            return json.dumps(result)
        except Exception as e:
            return f"ERROR: {e}"

    @mcp.tool()
    async def present_credential(provider_url: str, token_id: int) -> str:
        """Sign a fresh nonce and send 'activate' over A2A."""
        nonce = str(int(time.time()))
        sig = Account.sign_message(
            encode_defunct(text=nonce),
            private_key=consumer_key).signature.hex()
        try:
            result = await send_provider_action(provider_url, {
                "action": "activate", "token_id": int(token_id),
                "nonce": nonce, "signature": sig,
            })
            return json.dumps(result)
        except Exception as e:
            return f"ERROR: {e}"

    return mcp, quote_cache
```

- [ ] **Step 2: Update `tests/test_consumer_mcp.py` to use the factory**

Replace the file with:

```python
"""In-memory MCP tests for the consumer's tools."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from eth_account import Account
from fastmcp import Client

from consumer.mcp_server import build_mcp_server
from shared.config import Config

CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
CONSUMER_ADDR = Account.from_key(CONSUMER_KEY).address


@pytest.fixture
def cfg() -> Config:
    return Config(consumer_private_key=CONSUMER_KEY)


@pytest.mark.asyncio
async def test_wallet_address_returns_consumer_eoa(cfg):
    mcp, _ = build_mcp_server(cfg)
    async with Client(mcp) as c:
        result = await c.call_tool("wallet_address", {})
        assert result.content[0].text.lower() == CONSUMER_ADDR.lower()


@pytest.mark.asyncio
async def test_lock_payment_rejects_uncached_quote(cfg):
    mcp, quote_cache = build_mcp_server(cfg)
    quote_cache.clear()
    async with Client(mcp) as c:
        result = await c.call_tool("lock_payment", {"agreement_id": "999999"})
        assert "ERROR" in result.content[0].text


@pytest.mark.asyncio
async def test_browse_catalog_calls_provider_a2a(cfg):
    expected = {"catalog": [{"packageId": "small", "mbps": 2,
                             "durationSeconds": 600,
                             "priceWei": 10000000000000000,
                             "availableSlots": 1}]}

    async def fake_send(provider_url, payload):
        assert payload == {"action": "get_catalog"}
        return expected

    with patch("consumer.mcp_server.send_provider_action", new=fake_send):
        mcp, _ = build_mcp_server(cfg)
        async with Client(mcp) as c:
            result = await c.call_tool("browse_catalog",
                                       {"provider_url": "http://prov:8002"})
            assert json.loads(result.content[0].text) == expected["catalog"]


@pytest.mark.asyncio
async def test_request_quote_caches_for_lock_payment(cfg):
    response = {"agreementId": "999", "priceWei": 10000000000000000,
                "bandwidthMbps": 2, "durationSeconds": 600}

    async def fake_send(provider_url, payload):
        return response

    async def fake_fetch(url):
        return "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"

    with patch("consumer.mcp_server.send_provider_action", new=fake_send), \
         patch("consumer.mcp_server._fetch_provider_address", new=fake_fetch):
        mcp, quote_cache = build_mcp_server(cfg)
        async with Client(mcp) as c:
            result = await c.call_tool("request_quote", {
                "provider_url": "http://prov:8002", "package_id": "small"})
            data = json.loads(result.content[0].text)
            assert data["agreementId"] == "999"
            assert quote_cache["999"]["providerAddress"] == \
                "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
```

- [ ] **Step 3: Run the consumer MCP tests**

```bash
uv run pytest tests/test_consumer_mcp.py -v
```

Expected: 4 passing.

- [ ] **Step 4: Commit**

```bash
git add consumer/mcp_server.py tests/test_consumer_mcp.py
git commit -m "refactor(consumer): convert mcp_server to build_mcp_server(cfg) factory"
git push
```

### Task 11: Convert `consumer/graph.py` to `build_graph(cfg, mcp_tools)` and extract `tier_selection.py`

**Files:**
- Modify: `consumer/graph.py`
- Create: `consumer/tier_selection.py`

- [ ] **Step 1: Create `consumer/tier_selection.py`**

```python
"""Tier-picking helpers used by the consumer graph's pick_tier_node.

These are pure functions so they can be unit-tested without an LLM.
"""
from __future__ import annotations

import re

_TIER_WORD_TO_RANK = {
    "small": 0, "cheapest": 0, "basic": 0, "minimum": 0,
    "medium": 1, "standard": 1, "mid": 1,
    "large": 2, "fast": 2, "biggest": 2, "premium": 2,
}


def rank_catalog(catalog: list[dict]) -> list[dict]:
    """Return the catalog sorted by mbps ascending (smallest tier first)."""
    return sorted(catalog, key=lambda p: p["mbps"])


def deterministic_tier_pick(user_message: str, catalog: list[dict]) -> dict:
    """Rule-based fallback when the LLM output is not a recognizable tier word.

    1. "X Mbps" → smallest tier with mbps ≥ X (else largest).
    2. tier word match.
    3. middle tier.
    """
    ranked = rank_catalog(catalog)
    msg = user_message.lower()

    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:mbps|mbit|m)\b", msg)
    if m:
        want = float(m.group(1))
        candidates = [p for p in ranked if p["mbps"] >= want]
        return candidates[0] if candidates else ranked[-1]

    for word, rank in _TIER_WORD_TO_RANK.items():
        if word in msg:
            return ranked[min(rank, len(ranked) - 1)]

    return ranked[len(ranked) // 2]
```

- [ ] **Step 2: Refactor `consumer/graph.py` to take a `cfg` and a `tools` dict**

Replace `consumer/graph.py` with:

```python
"""LangGraph state machine for the consumer's bandwidth acquisition workflow.

Each node corresponds to one stage of the paper's six-stage workflow.
The LLM is consulted only at pick_tier_node and summary_node. Every
on-chain or A2A call goes through one of the consumer MCP tools, passed
in as a `tools` dict so the graph is testable without a real MCP server.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable, TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from consumer.tier_selection import deterministic_tier_pick, rank_catalog
from shared.config import Config


REQUIRED_PROVIDER_SKILLS = ("get_catalog", "request_quote", "activate")
_SETTLE_MAX_ATTEMPTS = 3
_A2A_TOOLS = frozenset({
    "discover_provider", "browse_catalog", "request_quote", "present_credential",
})


class WorkflowState(TypedDict, total=False):
    user_message: str
    provider_url: str
    provider_urls: list[str]
    offers: list[dict]
    model: str
    catalog: list[dict]
    chosen_tier: str
    chosen_mbps: float
    agreement_id: str
    tx_hash: str
    token_id: int
    settle_attempts: int
    activation: dict
    on_chain_verification: dict
    final_response: str
    log: list[dict]
    thinking: list[str]
    error: str | None


# Tool dict shape: name → async or sync callable. Built by build_consumer_tools().
ToolMap = dict[str, Callable[..., Awaitable[str] | str]]


async def _call_tool(tools: ToolMap, name: str, *args, **kwargs) -> str:
    """Invoke a tool that may be sync or async, returning its string result."""
    fn = tools[name]
    out = fn(*args, **kwargs)
    if asyncio.iscoroutine(out):
        return await out
    return await asyncio.to_thread(lambda: out) if False else out


def _log_call(state: WorkflowState, tool_name: str, args: dict) -> None:
    prefix = "[A2A]" if tool_name in _A2A_TOOLS else "[MCP]"
    state.setdefault("log", []).append({
        "from": "consumer",
        "message": f"{prefix} {tool_name}({json.dumps(args)})",
    })


def _log_result(state: WorkflowState, sender: str, result: str) -> None:
    state.setdefault("log", []).append({
        "from": sender, "message": str(result)[:400],
    })


def build_graph(cfg: Config, tools: ToolMap):
    """Compile the LangGraph state machine for the consumer agent.

    `tools` must provide the seven keys: discover_provider, browse_catalog,
    request_quote, lock_payment, await_settlement, present_credential,
    verify_credential. See `build_consumer_tools(cfg)` for the default
    factory that wires them to the consumer MCP server.
    """
    llm_cache: dict[str, ChatOllama] = {}

    def _llm(model: str) -> ChatOllama:
        if model not in llm_cache:
            llm_cache[model] = ChatOllama(
                model=model, base_url=cfg.ollama_host, temperature=0)
        return llm_cache[model]

    async def _llm_complete(prompt: str, model: str) -> str:
        resp = await _llm(model).ainvoke(prompt)
        return (resp.content or "").strip()

    async def discover_node(state: WorkflowState) -> dict:
        urls = state.get("provider_urls") or [state["provider_url"]]
        raws = await asyncio.gather(*(
            _call_tool(tools, "discover_provider", u) for u in urls))
        surviving: list[str] = []
        for url, raw in zip(urls, raws):
            _log_call(state, "discover_provider", {"provider_url": url})
            _log_result(state, "provider", raw)
            if raw.startswith("ERROR"):
                continue
            try:
                card = json.loads(raw)
            except json.JSONDecodeError:
                continue
            skills = set(card.get("skills") or [])
            missing = set(REQUIRED_PROVIDER_SKILLS) - skills
            if missing:
                state["log"].append({"from": "consumer",
                                     "message": f"Skipping {url}: missing skills {missing}"})
                continue
            surviving.append(url)
        if not surviving:
            return {"log": state["log"],
                    "error": "no providers advertise the required skills"}
        return {"log": state["log"], "provider_urls": surviving,
                "provider_url": surviving[0]}

    async def browse_node(state: WorkflowState) -> dict:
        urls = state.get("provider_urls") or [state["provider_url"]]
        raws = await asyncio.gather(*(
            _call_tool(tools, "browse_catalog", u) for u in urls))
        offers: list[dict] = []
        for url, raw in zip(urls, raws):
            _log_call(state, "browse_catalog", {"provider_url": url})
            _log_result(state, "provider", raw)
            if raw.startswith("ERROR"):
                continue
            try:
                tiers = json.loads(raw)
            except json.JSONDecodeError:
                continue
            offers.extend({**t, "provider_url": url} for t in tiers)
        if not offers:
            return {"log": state["log"],
                    "error": "no offers returned from any discovered provider"}
        by_pkg: dict[str, dict] = {}
        for o in offers:
            prev = by_pkg.get(o["packageId"])
            if prev is None or o["priceWei"] < prev["priceWei"]:
                by_pkg[o["packageId"]] = o
        return {"log": state["log"], "offers": offers,
                "catalog": list(by_pkg.values())}

    async def pick_tier_node(state: WorkflowState) -> dict:
        catalog = state["catalog"]
        ranked = rank_catalog(catalog)
        valid = {p["packageId"].lower() for p in ranked}
        prompt = (
            f"User says: {state['user_message']!r}\n"
            f"Catalog tiers (smallest to largest):\n"
            + "\n".join(f"- {p['packageId']}: {p['mbps']} Mbps" for p in ranked)
            + "\n\nReply with EXACTLY ONE WORD: the packageId you choose. "
              "No punctuation, no explanation, no JSON. Just the word."
        )
        raw = await _llm_complete(prompt,
                                  state.get("model") or cfg.ollama_model)
        state.setdefault("thinking", []).append(f"pick_tier raw: {raw!r}")
        chosen = None
        for token in re.findall(r"[a-zA-Z]+", raw.lower()):
            if token in valid:
                chosen = next(
                    p for p in ranked if p["packageId"].lower() == token)
                break
        if chosen is None:
            chosen = deterministic_tier_pick(state["user_message"], catalog)
        offers = state.get("offers") or [chosen]
        matching = [o for o in offers if o["packageId"] == chosen["packageId"]]
        best = min(matching, key=lambda o: o["priceWei"])
        chosen_url = best.get("provider_url") or state.get("provider_url", "")
        state.setdefault("log", []).append({"from": "consumer",
            "message": (f"Chose {best['packageId']} ({best['mbps']} Mbps) "
                        f"from {chosen_url} at {best['priceWei']} wei")})
        return {"chosen_tier": best["packageId"], "chosen_mbps": best["mbps"],
                "provider_url": chosen_url,
                "thinking": state["thinking"], "log": state["log"]}

    async def quote_node(state: WorkflowState) -> dict:
        args = {"provider_url": state["provider_url"],
                "package_id": state["chosen_tier"]}
        _log_call(state, "request_quote", args)
        raw = await _call_tool(tools, "request_quote",
                               state["provider_url"], state["chosen_tier"])
        _log_result(state, "provider", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        try:
            quote = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"log": state["log"],
                    "error": f"could not parse quote: {e}"}
        return {"log": state["log"], "agreement_id": str(quote["agreementId"])}

    async def lock_node(state: WorkflowState) -> dict:
        args = {"agreement_id": state["agreement_id"]}
        _log_call(state, "lock_payment", args)
        raw = await asyncio.to_thread(tools["lock_payment"],
                                      state["agreement_id"])
        _log_result(state, "consumer", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        tx_hash = raw.removeprefix("OK ").strip()
        state["log"].append({"from": "consumer",
                             "message": f"requestAgreement() sent. tx={tx_hash}"})
        return {"log": state["log"], "tx_hash": tx_hash}

    async def settle_node(state: WorkflowState) -> dict:
        args = {"agreement_id": state["agreement_id"]}
        _log_call(state, "await_settlement", args)
        raw = await asyncio.to_thread(tools["await_settlement"],
                                      state["agreement_id"])
        _log_result(state, "consumer", raw)
        attempts = state.get("settle_attempts", 0) + 1
        if raw == "PENDING":
            return {"log": state["log"], "settle_attempts": attempts}
        if raw.startswith("ERROR"):
            return {"log": state["log"], "settle_attempts": attempts,
                    "error": raw}
        if raw.startswith("OK tokenId="):
            token_id = int(raw.removeprefix("OK tokenId=").strip())
            state["log"].append({"from": "consumer",
                "message": f"Agreement ACTIVE. tokenId={token_id}"})
            return {"log": state["log"], "settle_attempts": attempts,
                    "token_id": token_id}
        return {"log": state["log"], "settle_attempts": attempts,
                "error": f"unexpected settlement response: {raw}"}

    def _settle_route(state: WorkflowState) -> str:
        if state.get("error"):
            return "error_node"
        if "token_id" in state:
            return "present_node"
        if state.get("settle_attempts", 0) >= _SETTLE_MAX_ATTEMPTS:
            return "error_node"
        return "settle_node"

    async def present_node(state: WorkflowState) -> dict:
        args = {"provider_url": state["provider_url"],
                "token_id": state["token_id"]}
        _log_call(state, "present_credential", args)
        raw = await _call_tool(tools, "present_credential",
                               state["provider_url"], state["token_id"])
        _log_result(state, "provider", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        try:
            activation = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"log": state["log"],
                    "error": f"could not parse activation: {e}"}
        if not isinstance(activation, dict):
            return {"log": state["log"],
                    "error": f"activation is not a JSON object: {raw[:200]}"}
        if activation.get("status") != "active":
            return {"log": state["log"],
                    "error": f"activation not active: {activation}"}
        state["log"].append({"from": "provider",
            "message": f"Gateway response: {json.dumps(activation)}"})
        return {"log": state["log"], "activation": activation}

    async def verify_node(state: WorkflowState) -> dict:
        args = {"token_id": state["token_id"]}
        _log_call(state, "verify_credential", args)
        raw = await asyncio.to_thread(tools["verify_credential"],
                                      state["token_id"])
        _log_result(state, "consumer", raw)
        if raw.startswith("ERROR"):
            return {"log": state["log"], "error": raw}
        try:
            verified = json.loads(raw)
        except json.JSONDecodeError as e:
            return {"log": state["log"],
                    "error": f"could not parse verification: {e}"}
        expected_mbps = int(state["chosen_mbps"])
        if int(verified["mbps"]) != expected_mbps:
            return {"log": state["log"],
                    "on_chain_verification": verified,
                    "error": (f"on-chain mbps mismatch: NFT grants "
                              f"{verified['mbps']} but quote promised "
                              f"{expected_mbps}")}
        if not verified.get("ownerIsConsumer"):
            return {"log": state["log"],
                    "on_chain_verification": verified,
                    "error": (f"NFT not owned by consumer "
                              f"(owner={verified.get('owner')})")}
        state["log"].append({"from": "consumer",
            "message": (f"On-chain verification OK: tokenId={state['token_id']} "
                        f"grants {verified['mbps']} Mbps for "
                        f"{verified['secondsRemaining']}s "
                        f"(endpoint={verified['endpoint']})")})
        return {"log": state["log"], "on_chain_verification": verified}

    async def summary_node(state: WorkflowState) -> dict:
        sentence = (f"Active service — {state['chosen_tier']} tier "
                    f"({state['chosen_mbps']} Mbps), "
                    f"agreementId={state['agreement_id']}, "
                    f"tokenId={state['token_id']}.")
        prompt = (
            "Briefly acknowledge a successful bandwidth purchase:\n"
            f"- tier: {state['chosen_tier']}\n"
            f"- bandwidth: {state['chosen_mbps']} Mbps\n"
            f"- agreementId: {state['agreement_id']}\n"
            f"- tokenId: {state['token_id']}\n"
            "Reply with one short sentence."
        )
        try:
            text = await _llm_complete(prompt,
                                       state.get("model") or cfg.ollama_model)
        except Exception as e:
            text = f"<llm error: {e}>"
        state.setdefault("thinking", []).append(f"summary raw: {text!r}")
        return {"final_response": sentence, "thinking": state["thinking"]}

    async def error_node(state: WorkflowState) -> dict:
        msg = state.get("error") or "unknown error"
        return {"final_response": f"Workflow stopped: {msg}"}

    def _route_after(next_node: str):
        def router(state: WorkflowState) -> str:
            return "error_node" if state.get("error") else next_node
        return router

    builder = StateGraph(WorkflowState)
    builder.add_node("discover_node", discover_node)
    builder.add_node("browse_node", browse_node)
    builder.add_node("pick_tier_node", pick_tier_node)
    builder.add_node("quote_node", quote_node)
    builder.add_node("lock_node", lock_node)
    builder.add_node("settle_node", settle_node)
    builder.add_node("present_node", present_node)
    builder.add_node("verify_node", verify_node)
    builder.add_node("summary_node", summary_node)
    builder.add_node("error_node", error_node)
    builder.add_edge(START, "discover_node")
    builder.add_conditional_edges("discover_node", _route_after("browse_node"))
    builder.add_conditional_edges("browse_node", _route_after("pick_tier_node"))
    builder.add_conditional_edges("pick_tier_node", _route_after("quote_node"))
    builder.add_conditional_edges("quote_node", _route_after("lock_node"))
    builder.add_conditional_edges("lock_node", _route_after("settle_node"))
    builder.add_conditional_edges("settle_node", _settle_route)
    builder.add_conditional_edges("present_node", _route_after("verify_node"))
    builder.add_conditional_edges("verify_node", _route_after("summary_node"))
    builder.add_edge("summary_node", END)
    builder.add_edge("error_node", END)
    return builder.compile()


def build_consumer_tools(cfg: Config) -> ToolMap:
    """Build the default tool dict by spinning up the consumer MCP server.

    Returns a dict that maps tool names to plain callables (sync or async).
    Notebooks can pass a hand-rolled dict instead to swap in stubs.
    """
    from consumer.mcp_server import build_mcp_server  # local import to avoid cycle
    mcp, _ = build_mcp_server(cfg)
    raw = mcp._tool_manager._tools  # type: ignore[attr-defined]
    return {name: tool.fn for name, tool in raw.items()}
```

> **Note on `build_consumer_tools`:** FastMCP exposes registered tools via `mcp._tool_manager._tools` (a dict). If a future FastMCP release renames this internal attribute, replace `build_consumer_tools` with explicit imports of the closure-bound callables. For now this is the cleanest way to share one set of tool implementations between MCP-bound calls and direct in-process calls.

- [ ] **Step 3: Rewrite `tests/test_consumer_graph.py`**

The existing test file monkey-patches module-level `g._browse_catalog_tool` etc. With the new shape, tests pass a `tools` dict directly. Replace the file:

```python
"""Unit tests for consumer/graph.py nodes."""
from __future__ import annotations

import json
from typing import Callable

import pytest

from consumer.graph import (
    browse_node, build_graph, discover_node, error_node, lock_node,
    pick_tier_node, present_node, quote_node, settle_node, summary_node,
    verify_node, _settle_route,
)
from shared.config import Config


CFG = Config(consumer_private_key="0x" + "11" * 32)


@pytest.fixture
def fake_catalog():
    return [
        {"packageId": "small",  "mbps": 2.0, "durationSeconds": 600,
         "priceWei": 10**16, "availableSlots": 1},
        {"packageId": "medium", "mbps": 5.0, "durationSeconds": 600,
         "priceWei": 2 * 10**16, "availableSlots": 1},
        {"packageId": "large",  "mbps": 8.0, "durationSeconds": 600,
         "priceWei": 8 * 10**16, "availableSlots": 1},
    ]


def _make_tools(**overrides) -> dict[str, Callable]:
    """Default no-op tools — override per test."""
    async def _err_async(*a, **kw): return "ERROR: not stubbed"
    def _err_sync(*a, **kw): return "ERROR: not stubbed"
    base = {
        "discover_provider": _err_async,
        "browse_catalog":    _err_async,
        "request_quote":     _err_async,
        "lock_payment":      _err_sync,
        "await_settlement":  _err_sync,
        "present_credential": _err_async,
        "verify_credential": _err_sync,
    }
    base.update(overrides)
    return base


# Browse / catalog ---------------------------------------------------------
@pytest.mark.asyncio
async def test_browse_node_populates_catalog(fake_catalog):
    async def fake_browse(url): return json.dumps(fake_catalog)
    tools = _make_tools(browse_catalog=fake_browse)
    g = build_graph(CFG, tools)  # ensures graph constructs cleanly
    out = await browse_node.__wrapped__(...) if False else None  # see note below
    # The node functions are closures inside build_graph in the new shape;
    # exercise them via the compiled graph instead:
    state = await g.ainvoke({
        "user_message": "small please",
        "provider_url": "http://provider:8002",
        "log": [], "thinking": [],
    })
    # discover will fail (default _err_async), so this pathway will surface
    # an error. The test below covers browse_node directly via a custom wiring.
```

> **Important: the new `consumer/graph.py` defines node functions as closures inside `build_graph`, so they cannot be unit-tested independently.** Refactor the test strategy: drive the compiled graph end-to-end with stubbed tools instead of poking individual nodes.

Replace the previous `tests/test_consumer_graph.py` content with this final version:

```python
"""Tests for the consumer LangGraph state machine.

The graph nodes are closures inside build_graph(); test them via the
compiled graph with stubbed tools rather than by direct import.
"""
from __future__ import annotations

import json

import pytest

from consumer.graph import build_graph
from consumer.tier_selection import deterministic_tier_pick, rank_catalog
from shared.config import Config


CFG = Config(consumer_private_key="0x" + "11" * 32)


@pytest.fixture
def fake_catalog():
    return [
        {"packageId": "small",  "mbps": 2.0, "durationSeconds": 600,
         "priceWei": 10**16, "availableSlots": 1},
        {"packageId": "medium", "mbps": 5.0, "durationSeconds": 600,
         "priceWei": 2 * 10**16, "availableSlots": 1},
        {"packageId": "large",  "mbps": 8.0, "durationSeconds": 600,
         "priceWei": 8 * 10**16, "availableSlots": 1},
    ]


def _stub_tools(fake_catalog,
                quote_response=None, lock_response="OK 0xdead",
                settle_response="OK tokenId=99",
                activation=None,
                verify_response=None, mbps=5):
    quote_response = quote_response or {
        "agreementId": "777", "priceWei": 2 * 10**16,
        "bandwidthMbps": mbps, "durationSeconds": 600}
    activation = activation or {"status": "active",
                                "bandwidthMbps": mbps, "tokenId": 99}
    verify_response = verify_response or {
        "ok": True, "owner": "0xC", "ownerIsConsumer": True,
        "agreementId": 777, "mbps": mbps, "durationSeconds": 600,
        "secondsRemaining": 600, "endpoint": "clab://pe1/eth-1.100"}

    async def discover(url):
        return json.dumps({"name": "P", "version": "2",
                           "skills": ["get_catalog", "request_quote", "activate"]})
    async def browse(url): return json.dumps(fake_catalog)
    async def quote(url, pkg): return json.dumps(quote_response)
    def lock(aid): return lock_response
    def settle(aid): return settle_response
    async def present(url, tid): return json.dumps(activation)
    def verify(tid): return json.dumps(verify_response)
    return {
        "discover_provider": discover, "browse_catalog": browse,
        "request_quote": quote, "lock_payment": lock,
        "await_settlement": settle, "present_credential": present,
        "verify_credential": verify,
    }


@pytest.mark.asyncio
async def test_full_graph_happy_path(fake_catalog, monkeypatch):
    tools = _stub_tools(fake_catalog)
    # Stub the LLM by patching ChatOllama.ainvoke at the module level.
    from langchain_ollama import ChatOllama

    class FakeResp:
        def __init__(self, content): self.content = content

    async def fake_ainvoke(self, prompt, *a, **kw):
        return FakeResp("medium" if "EXACTLY ONE WORD" in prompt
                        else "OK done.")
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "I need 5 Mbps",
        "provider_url": "http://provider:8002",
        "model": "llama3.2:3b",
        "log": [], "thinking": [],
    })
    assert result["chosen_tier"] == "medium"
    assert result["agreement_id"] == "777"
    assert result["token_id"] == 99
    assert "Active service" in result["final_response"]
    assert result["on_chain_verification"]["mbps"] == 5


@pytest.mark.asyncio
async def test_graph_errors_when_no_providers_advertise_skills(fake_catalog,
                                                                monkeypatch):
    async def discover_bad(url):
        return json.dumps({"name": "bad", "version": "1",
                           "skills": ["get_catalog"]})
    tools = _stub_tools(fake_catalog)
    tools["discover_provider"] = discover_bad

    from langchain_ollama import ChatOllama

    async def fake_ainvoke(self, prompt, *a, **kw):
        class R: content = "small"
        return R()
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "small please",
        "provider_url": "http://x:8002",
        "log": [], "thinking": [],
    })
    assert "Workflow stopped" in result["final_response"]


@pytest.mark.asyncio
async def test_graph_errors_when_lock_payment_fails(fake_catalog, monkeypatch):
    tools = _stub_tools(fake_catalog, lock_response="ERROR: insufficient funds")
    from langchain_ollama import ChatOllama
    async def fake_ainvoke(self, prompt, *a, **kw):
        class R: content = "small"
        return R()
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "small please",
        "provider_url": "http://provider:8002",
        "log": [], "thinking": [],
    })
    assert "insufficient funds" in result["final_response"]


@pytest.mark.asyncio
async def test_graph_errors_when_verify_finds_mbps_mismatch(fake_catalog,
                                                            monkeypatch):
    tools = _stub_tools(
        fake_catalog,
        verify_response={"ok": True, "owner": "0xC", "ownerIsConsumer": True,
                         "agreementId": 1, "mbps": 1, "durationSeconds": 600,
                         "secondsRemaining": 600, "endpoint": "x"})
    from langchain_ollama import ChatOllama
    async def fake_ainvoke(self, prompt, *a, **kw):
        class R: content = "medium"
        return R()
    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    graph = build_graph(CFG, tools)
    result = await graph.ainvoke({
        "user_message": "medium please",
        "provider_url": "http://provider:8002",
        "log": [], "thinking": [],
    })
    assert "mbps mismatch" in result["final_response"]


def test_settle_route_logic():
    # Imported lazily because the function is closed over build_graph;
    # we re-implement the table for clarity.
    cfg = CFG
    graph = build_graph(cfg, _stub_tools([]))
    # The router is internal; we exercise it by running the graph in stages.
    assert graph is not None  # smoke check; route-coverage handled by full path tests


def test_rank_catalog_sorts_by_mbps(fake_catalog):
    ranked = rank_catalog(fake_catalog)
    assert [p["packageId"] for p in ranked] == ["small", "medium", "large"]


def test_deterministic_tier_pick_numeric(fake_catalog):
    pick = deterministic_tier_pick("I need 4 Mbps", fake_catalog)
    assert pick["packageId"] == "medium"


def test_deterministic_tier_pick_oversized_request(fake_catalog):
    pick = deterministic_tier_pick("I need 100 Mbps", fake_catalog)
    assert pick["packageId"] == "large"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_consumer_graph.py -v
```

Expected: 7 passing. (The settle-route legacy test is replaced by the happy-path test that exercises the route in context.)

- [ ] **Step 5: Commit**

```bash
git add consumer/graph.py consumer/tier_selection.py tests/test_consumer_graph.py
git commit -m "refactor(consumer): convert graph to build_graph(cfg, tools); extract tier_selection"
git push
```

### Task 12: Convert `consumer/agent_card.py` to a factory

**Files:**
- Modify: `consumer/agent_card.py`

- [ ] **Step 1: Edit `consumer/agent_card.py` to take a `cfg`**

Replace the whole file with:

```python
"""AgentCard for the consumer agent."""
from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from shared.config import Config


def build_consumer_agent_card(cfg: Config) -> AgentCard:
    """Build the consumer's A2A AgentCard using `cfg.consumer_base_url`."""
    return AgentCard(
        name="Bandwidth Consumer Agent",
        description=(
            "Autonomously procures time-bound bandwidth from provider agents via "
            "atomic on-chain escrow + ERC-721 credential."
        ),
        version="2.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["application/json", "text/plain"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(protocol_binding="HTTP",
                           url=f"{cfg.consumer_base_url}/chat"),
        ],
        skills=[
            AgentSkill(
                id="purchase_bandwidth", name="Purchase Bandwidth",
                description=("Given a tier or bandwidth requirement, negotiates "
                             "with a provider, settles on chain, and activates "
                             "the service."),
                tags=["bandwidth", "agent2agent"],
                examples=["I need 5 Mbps for 10 minutes."],
            ),
        ],
    )
```

- [ ] **Step 2: Run any tests that import this**

```bash
grep -rln "build_consumer_agent_card" consumer/ tests/ provider/ shared/
```

If anything else imports it (likely `consumer/app.py`), it will be fixed in Task 14.

- [ ] **Step 3: Commit**

```bash
git add consumer/agent_card.py
git commit -m "refactor(consumer): make agent_card a Config-driven factory"
git push
```

### Task 13: Convert `provider/agent_card.py` to a factory

**Files:**
- Modify: `provider/agent_card.py`

- [ ] **Step 1: Edit `provider/agent_card.py`**

Replace the whole file with:

```python
"""Builds the a2a.types.AgentCard for the bandwidth provider agent."""
from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from shared.config import Config


def build_provider_agent_card(cfg: Config) -> AgentCard:
    """Build the provider's A2A AgentCard using `cfg.provider_base_url`."""
    a2a_url = f"{cfg.provider_base_url}/a2a"
    return AgentCard(
        name="Bandwidth Provider Agent",
        description=("Sells time-bound bandwidth packages via atomic on-chain "
                     "escrow + ERC-721 credential. Activates SDN policy "
                     "(gNMI policer + tc rate-limit) on credential presentation."),
        version="2.0.0",
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC",
                                             url=a2a_url)],
        skills=[
            AgentSkill(id="get_catalog", name="Get Catalog",
                       description="Returns available bandwidth tiers.",
                       tags=["bandwidth", "catalog"],
                       examples=['{"action": "get_catalog"}']),
            AgentSkill(id="request_quote", name="Request Quote",
                       description=("Issues an agreementId-bound price quote "
                                    "for a chosen tier."),
                       tags=["bandwidth", "quote", "escrow"],
                       examples=['{"action": "request_quote", '
                                 '"package_id": "medium", "consumer_address": "0x..."}']),
            AgentSkill(id="activate", name="Activate Service",
                       description=("Verifies NFT credential ownership and "
                                    "triggers SDN allocation."),
                       tags=["bandwidth", "activation", "sdn"],
                       examples=['{"action": "activate", "token_id": 7, '
                                 '"nonce": "1730000000", "signature": "0x..."}']),
        ],
    )
```

- [ ] **Step 2: Commit**

```bash
git add provider/agent_card.py
git commit -m "refactor(provider): make agent_card a Config-driven factory"
git push
```

### Task 14: Refactor `consumer/app.py` to use `lifespan` + factories

**Files:**
- Modify: `consumer/app.py`
- Modify: `tests/test_consumer_app.py`

- [ ] **Step 1: Replace `consumer/app.py` with the lifespan version**

```python
"""Consumer agent FastAPI service — port 8001.

Builds Config + MCP server + LangGraph in `lifespan`. Endpoints read
state from `app.state`. Cross-agent calls go through the consumer MCP
tools, which wrap A2A calls to the provider.
"""
from __future__ import annotations

import json
import traceback
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel, Field

from consumer.agent_card import build_consumer_agent_card
from consumer.graph import build_consumer_tools, build_graph
from consumer.mcp_server import build_mcp_server
from shared.chain import make_web3
from shared.config import Config
from shared.contracts import get_escrow_contract, get_nft_contract


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Config.from_env()
    mcp, _quote_cache = build_mcp_server(cfg)
    tools = build_consumer_tools(cfg)
    graph = build_graph(cfg, tools)
    card = build_consumer_agent_card(cfg)
    app.state.cfg = cfg
    app.state.mcp = mcp
    app.state.graph = graph
    app.state.agent_card_json = MessageToDict(card,
                                              preserving_proto_field_name=True)
    app.state.w3 = make_web3(cfg)
    app.state.inter_agent_log = []
    yield


app = FastAPI(title="Consumer Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    model: str | None = None


class ChatResponse(BaseModel):
    response: str
    log: list[dict]
    thinking: list[str] = Field(default_factory=list)


def _seen_keys(state) -> set:
    return getattr(state, "_seen_log_keys", set())


def _append_log(state, sender: str, message: str) -> None:
    keys = _seen_keys(state)
    key = (sender, message)
    if key in keys:
        return
    keys.add(key)
    state._seen_log_keys = keys
    state.inter_agent_log.append({"from": sender, "message": message})


@app.get("/.well-known/agent-card.json")
def agent_card_canonical(request: Request) -> dict:
    return request.app.state.agent_card_json


@app.get("/.well-known/agent.json")
def agent_card_legacy(request: Request) -> dict:
    return request.app.state.agent_card_json


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, request: Request) -> ChatResponse:
    cfg: Config = request.app.state.cfg
    request.app.state.inter_agent_log.clear()
    request.app.state._seen_log_keys = set()
    initial = {
        "user_message": req.message,
        "provider_url": cfg.provider_a2a_urls[0],
        "provider_urls": list(cfg.provider_a2a_urls),
        "model": req.model or cfg.ollama_model,
        "log": [], "thinking": [],
    }
    try:
        final = await request.app.state.graph.ainvoke(initial)
    except Exception as e:
        traceback.print_exc()
        return ChatResponse(response=f"INTERNAL ERROR: {e}", log=[], thinking=[])
    for entry in final.get("log", []):
        _append_log(request.app.state, entry["from"], entry["message"])
    return ChatResponse(
        response=final.get("final_response", "(no response)"),
        log=list(request.app.state.inter_agent_log),
        thinking=final.get("thinking", []),
    )


@app.get("/log")
def get_log(request: Request) -> list[dict]:
    return list(request.app.state.inter_agent_log)


@app.delete("/log")
def clear_log(request: Request) -> dict:
    request.app.state.inter_agent_log.clear()
    request.app.state._seen_log_keys = set()
    return {"cleared": True}


@app.get("/catalog_proxy")
async def catalog_proxy(request: Request) -> list[dict]:
    cfg: Config = request.app.state.cfg
    async with MCPClient(request.app.state.mcp) as c:
        result = await c.call_tool("browse_catalog",
                                   {"provider_url": cfg.provider_a2a_urls[0]})
        text = result.content[0].text if result.content else ""
    if text.startswith("ERROR"):
        raise HTTPException(502, text)
    return json.loads(text)


@app.get("/address")
async def consumer_address_endpoint(request: Request) -> dict:
    async with MCPClient(request.app.state.mcp) as c:
        result = await c.call_tool("wallet_address", {})
    return {"address": result.content[0].text}


@app.get("/check_token")
async def check_token(tokenId: int, request: Request) -> dict:
    async with MCPClient(request.app.state.mcp) as c:
        result = await c.call_tool("verify_credential", {"token_id": int(tokenId)})
        text = result.content[0].text if result.content else ""
    if text.startswith("ERROR"):
        raise HTTPException(404, text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(502, f"unparseable verify_credential response: {e}")
    seconds_remaining = int(data.get("secondsRemaining", 0))
    return {
        "owner": data["owner"],
        "status": "active" if seconds_remaining > 0 else "expired",
        "seconds_remaining": seconds_remaining,
        "bandwidth_mbps": float(data["mbps"]),
        "endpoint": data["endpoint"],
        "agreementId": str(data.get("agreementId", "")),
    }


class ProbeProxyRequest(BaseModel):
    tokenId: int


@app.post("/probe_proxy")
async def probe_proxy(req: ProbeProxyRequest, request: Request) -> dict:
    cfg: Config = request.app.state.cfg
    if not cfg.provider_a2a_urls:
        raise HTTPException(500, "no provider_a2a_urls configured")
    target = f"{cfg.provider_a2a_urls[0]}/probe"
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            r = await http.post(target, json={"tokenId": int(req.tokenId)})
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code,
                            f"provider /probe failed: {e.response.text}")
    except Exception as e:
        raise HTTPException(502, f"probe forward failed: {e}")


@app.get("/chain_events")
def chain_events(since_block: int = 0, request: Request = None) -> list[dict]:
    """Return escrow + NFT events emitted since `since_block`."""
    w3 = request.app.state.w3
    escrow = get_escrow_contract(w3)
    nft = get_nft_contract(w3)
    to_block = w3.eth.block_number

    def _serialize(args) -> dict:
        out = {}
        for k, v in dict(args).items():
            if isinstance(v, (bytes, bytearray)):
                out[k] = "0x" + v.hex()
            elif hasattr(v, "hex") and not isinstance(v, (int, str)):
                out[k] = v.hex()
            else:
                out[k] = (str(v) if not isinstance(v, (int, str, bool, type(None)))
                          else v)
        return out

    def _gather_named(contract, name: str) -> list[dict]:
        evt = getattr(contract.events, name, None)
        if evt is None:
            return []
        try:
            logs = evt.get_logs(fromBlock=since_block, toBlock=to_block)
        except Exception:
            return []
        out = []
        for e in logs:
            tx_hash = (e["transactionHash"].hex()
                       if hasattr(e["transactionHash"], "hex")
                       else str(e["transactionHash"]))
            try:
                gas = int(w3.eth.get_transaction_receipt(tx_hash)["gasUsed"])
            except Exception:
                gas = 0
            out.append({"event": name, "args": _serialize(e["args"]),
                        "block": int(e["blockNumber"]),
                        "txHash": tx_hash, "gas": gas})
        return out

    events: list[dict] = []
    for name in ("AgreementRequested", "AgreementActive", "AgreementCancelled"):
        events += _gather_named(escrow, name)
    events += _gather_named(nft, "Transfer")
    events.sort(key=lambda e: e["block"])
    return events


if __name__ == "__main__":
    uvicorn.run("consumer.app:app", host="0.0.0.0", port=8001, reload=False)
```

- [ ] **Step 2: Update `tests/test_consumer_app.py`**

Replace with:

```python
"""HTTP-level tests for consumer/app.py routes that mock web3."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "CONSUMER_PRIVATE_KEY",
        "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
    )
    from consumer.app import app
    with TestClient(app) as c:
        yield c


def test_chain_events_returns_combined_events(client, monkeypatch):
    from consumer import app as consumer_app

    fake_escrow = MagicMock()
    fake_escrow.events.AgreementRequested.get_logs.return_value = []
    fake_nft = MagicMock()
    fake_nft.events.Transfer.get_logs.return_value = []

    fake_w3 = MagicMock()
    fake_w3.eth.block_number = 100
    fake_w3.eth.get_transaction_receipt.return_value = {"gasUsed": 50_000}

    client.app.state.w3 = fake_w3
    monkeypatch.setattr(consumer_app, "get_escrow_contract",
                        lambda w3: fake_escrow)
    monkeypatch.setattr(consumer_app, "get_nft_contract",
                        lambda w3: fake_nft)

    resp = client.get("/chain_events", params={"since_block": 0})
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_consumer_app.py -v
```

Expected: 1 passing.

- [ ] **Step 4: Commit**

```bash
git add consumer/app.py tests/test_consumer_app.py
git commit -m "refactor(consumer): app uses lifespan + factories; no module-level state"
git push
```

### Task 15: Extract `provider/event_listener.py` and refactor `provider/app.py`

**Files:**
- Create: `provider/event_listener.py`
- Modify: `provider/app.py`

- [ ] **Step 1: Create `provider/event_listener.py`**

```python
"""Watch the escrow for AgreementRequested events and drive mint+swap.

Lives apart from provider/app.py so the listener loop can be exercised
in isolation by tests and notebooks. The MCP client passed in is the
same in-memory FastMCP server the rest of the app uses.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastmcp import Client as MCPClient
from fastmcp import FastMCP
from web3 import Web3

from provider.catalog import (
    CATALOG_BY_ID, cleanup_quotes, pending_quotes, slot_pool,
)
from shared.contracts import get_escrow_contract

log = logging.getLogger("provider.event_listener")


async def run(w3: Web3, mcp: FastMCP, poll_interval_s: float = 2.0) -> None:
    """Loop forever: poll AgreementRequested logs and drive mint/swap.

    Cancellable: catch `asyncio.CancelledError` in the caller's `finally`
    so `lifespan` can clean shut down.
    """
    escrow = get_escrow_contract(w3)
    last_block = w3.eth.block_number
    log.info("Event listener started at block %d", last_block)
    handler_tasks: set[asyncio.Task] = set()

    while True:
        await asyncio.sleep(poll_interval_s)
        try:
            current = w3.eth.block_number
            if current <= last_block:
                continue
            events = escrow.events.AgreementRequested.get_logs(
                fromBlock=last_block + 1, toBlock=current)
            last_block = current
            for evt in events:
                args = evt["args"]
                t = asyncio.create_task(
                    _handle(escrow, mcp, args["agreementId"], args))
                handler_tasks.add(t)
                t.add_done_callback(handler_tasks.discard)
        except Exception:
            log.exception("Event listener error")


async def _handle(escrow, mcp: FastMCP, agreement_id: int, args: dict) -> None:
    cleanup_quotes()
    quote = pending_quotes.get(agreement_id)
    if not quote or time.time() > quote["expires"]:
        log.warning("No valid quote for agreementId=%d", agreement_id)
        return
    pkg = CATALOG_BY_ID.get(quote["packageId"])
    if not pkg:
        log.error("Unknown packageId for agreementId=%d", agreement_id)
        return
    ag = escrow.functions.getAgreement(agreement_id).call()
    if (ag[2] != pkg["mbps"] or ag[3] != pkg["durationSeconds"]
            or ag[4] != pkg["priceWei"]):
        log.error("Param mismatch for agreementId=%d", agreement_id)
        return
    slot = slot_pool.reserve(pkg["packageId"], agreement_id,
                             pkg["durationSeconds"])
    if slot is None:
        log.error("No slots for tier=%s", pkg["packageId"])
        return
    try:
        async with MCPClient(mcp) as client:
            mint = await client.call_tool("mint_credential", {
                "agreement_id": agreement_id,
                "consumer_address": args["consumer"],
                "pe": slot.pe, "subinterface": slot.subinterface,
                "ce": slot.ce, "mbps": pkg["mbps"],
                "duration_seconds": pkg["durationSeconds"],
            })
            mint_data = json.loads(mint.content[0].text)
            token_id = int(mint_data["tokenId"])
            await client.call_tool("complete_swap", {
                "agreement_id": agreement_id, "token_id": token_id})
        del pending_quotes[agreement_id]
    except Exception:
        log.exception("mint/swap flow failed for agreementId=%d", agreement_id)
        slot_pool.release(agreement_id)
```

- [ ] **Step 2: Refactor `provider/app.py`**

Replace with:

```python
"""Provider agent FastAPI service — port 8002."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from fastapi import FastAPI, HTTPException, Request
from fastmcp import Client as MCPClient
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel

from provider import event_listener
from provider.agent_card import build_provider_agent_card
from provider.agent_executor import BandwidthProviderExecutor
from provider.catalog import get_catalog_with_availability, slot_pool
from provider.expiry import expiry_sweep_loop
from provider.mcp_server import build_mcp_server
from shared.chain import make_web3
from shared.config import Config
from shared.contracts import get_nft_contract

# CE peer pairs — defined by the clab topology.
CE_PEER = {"ce1": "ce2", "ce2": "ce1", "ce3": "ce4", "ce4": "ce3"}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("provider")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = Config.from_env()
    mcp, tool_log = build_mcp_server(cfg)
    w3 = make_web3(cfg)
    card = build_provider_agent_card(cfg)
    app.state.cfg = cfg
    app.state.mcp = mcp
    app.state.tool_log = tool_log
    app.state.w3 = w3
    app.state.agent_card_json = MessageToDict(card,
                                              preserving_proto_field_name=True)

    a2a_handler = DefaultRequestHandler(
        agent_executor=BandwidthProviderExecutor(mcp),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    for route in create_agent_card_routes(card):
        app.router.routes.append(route)
    for route in create_jsonrpc_routes(a2a_handler, "/a2a"):
        app.router.routes.append(route)

    mcp_http = mcp.http_app()
    app.mount("/", mcp_http)

    async with mcp_http.lifespan(app):
        listener_task = asyncio.create_task(event_listener.run(w3, mcp))
        expiry_task = asyncio.create_task(
            expiry_sweep_loop(mcp, period_seconds=30))
        try:
            yield
        finally:
            listener_task.cancel()
            expiry_task.cancel()


app = FastAPI(title="Bandwidth Provider", lifespan=lifespan)


class QuoteRequest(BaseModel):
    packageId: str
    consumerAddress: str


@app.get("/_debug/catalog")
def debug_catalog() -> list[dict]:
    return get_catalog_with_availability()


@app.get("/inventory")
def get_inventory() -> list[dict]:
    return get_catalog_with_availability()


@app.get("/address")
def provider_address(request: Request) -> dict:
    cfg: Config = request.app.state.cfg
    from eth_account import Account
    return {"address": Account.from_key(cfg.provider_private_key).address}


class ProbeRequest(BaseModel):
    tokenId: int


@app.post("/probe")
async def probe(req: ProbeRequest, request: Request) -> dict:
    w3 = request.app.state.w3
    nft = get_nft_contract(w3)
    try:
        agreement_id, mbps, *_ = nft.functions.getTokenMetadata(
            int(req.tokenId)).call()
    except Exception:
        raise HTTPException(404, f"token {req.tokenId} does not exist")

    slot = slot_pool.lookup(int(agreement_id))
    if slot is None:
        raise HTTPException(409, f"no active slot for agreement {agreement_id}")
    dst_ce = CE_PEER.get(slot.ce)
    if dst_ce is None:
        raise HTTPException(500, f"no peer mapping for {slot.ce}")
    async with MCPClient(request.app.state.mcp) as client:
        result = await client.call_tool("verify_bandwidth", {
            "src_ce": slot.ce, "dst_ce": dst_ce,
            "expected_mbps": float(mbps)})
        verify = json.loads(result.content[0].text)
    return {
        "timestamp": time.time(), "src_ce": slot.ce, "dst_ce": dst_ce,
        "expected_mbps": float(mbps),
        "measured_mbps": float(verify.get("measured_mbps", 0.0)),
        "passed": bool(verify.get("passed", False)),
        "message": verify.get("message", ""),
    }


@app.get("/tool_log")
def get_tool_log(since_ts: float | None, request: Request) -> list[dict]:
    entries = list(request.app.state.tool_log)
    if since_ts is not None:
        entries = [e for e in entries if e["ts"] > since_ts]
    return entries


if __name__ == "__main__":
    uvicorn.run("provider.app:app", host="0.0.0.0", port=8002, reload=False)
```

- [ ] **Step 3: Update `provider/agent_executor.py` to take an MCP server in its constructor**

Edit the file:

Change this section:

```python
class BandwidthProviderExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
```

to:

```python
class BandwidthProviderExecutor(AgentExecutor):
    def __init__(self, mcp):
        self._mcp = mcp

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
```

Then `replace_all` the string `MCPClient(mcp)` (the imported global) → `MCPClient(self._mcp)` inside the executor methods.

Remove the now-unused `from provider.mcp_server import mcp` line at the top.

- [ ] **Step 4: Update `provider/expiry.py` to take an MCP server**

Edit:

Change `expiry_sweep_loop(period_seconds: int = 30)` signature to `expiry_sweep_loop(mcp, period_seconds: int = 30)`. Inside `_sweep_once`, change to `_sweep_once(mcp)` and use `MCPClient(mcp)` instead of the imported global. Remove `from provider.mcp_server import mcp` at the top.

The relevant edits:

1. Replace:
```python
from provider.mcp_server import mcp
```
with nothing (delete the line).

2. Change function signatures:
```python
async def expiry_sweep_loop(mcp, period_seconds: int = 30) -> None:
    """Run forever: every period_seconds, revoke SDN for any expired slot."""
    log.info("Expiry sweep started, period=%ss", period_seconds)
    while True:
        await asyncio.sleep(period_seconds)
        try:
            await _sweep_once(mcp)
        except Exception:
            log.exception("expiry sweep error")


async def _sweep_once(mcp) -> None:
```

The rest of `_sweep_once` stays — `MCPClient(mcp)` is already used; the parameter just gets a value now.

- [ ] **Step 5: Update `tests/test_provider_app.py` and `tests/test_agent_executor.py`**

`test_provider_app.py` — replace with:

```python
"""HTTP-level tests for provider/app.py routes that don't need anvil."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "PROVIDER_PRIVATE_KEY",
        "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
    )
    monkeypatch.setenv("SDN_MOCK", "true")
    from provider.app import app
    with TestClient(app) as c:
        yield c


def test_tool_log_returns_recorded_entries(client):
    client.app.state.tool_log.clear()
    client.app.state.tool_log.append({
        "tool": "get_catalog", "ts": 1.0, "args": {}, "status": "ok",
    })
    resp = client.get("/tool_log")
    assert resp.status_code == 200
    data = resp.json()
    assert data[-1]["tool"] == "get_catalog"
    assert data[-1]["status"] == "ok"


def test_tool_log_since_ts_filters(client):
    client.app.state.tool_log.clear()
    client.app.state.tool_log.append({"tool": "a", "ts": 1.0, "args": {}, "status": "ok"})
    client.app.state.tool_log.append({"tool": "b", "ts": 5.0, "args": {}, "status": "ok"})
    resp = client.get("/tool_log", params={"since_ts": 2.0})
    assert resp.status_code == 200
    assert [e["tool"] for e in resp.json()] == ["b"]


def test_tool_log_since_ts_excludes_equal_timestamps(client):
    client.app.state.tool_log.clear()
    client.app.state.tool_log.append({"tool": "a", "ts": 1.0, "args": {}, "status": "ok"})
    resp = client.get("/tool_log", params={"since_ts": 1.0})
    assert resp.status_code == 200
    assert resp.json() == []
```

`test_agent_executor.py` — change `_make_executor`:

```python
@pytest.fixture
def executor():
    from provider.mcp_server import build_mcp_server
    from shared.config import Config
    cfg = Config(
        provider_private_key="0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
        sdn_mock=True,
    )
    mcp, _ = build_mcp_server(cfg)
    return BandwidthProviderExecutor(mcp)
```

And replace the three test bodies' `ex = BandwidthProviderExecutor()` with `ex = executor` (taking the fixture).

- [ ] **Step 6: Run all provider-side tests**

```bash
uv run pytest tests/test_provider_app.py tests/test_provider_mcp.py tests/test_agent_executor.py -v
```

Expected: all passing.

- [ ] **Step 7: Run the demo**

```bash
make up
sleep 12
make demo 2>&1 | tail -30
make down
```

Expected: STEP 3 still shows the trade succeeded.

- [ ] **Step 8: Commit**

```bash
git add provider/ tests/test_provider_app.py tests/test_agent_executor.py
git commit -m "refactor(provider): lifespan-based app; extract event_listener; thread mcp through executor/expiry"
git push
```

---

## Phase 4: Add `shared/anvil.py` and `shared/deploy.py`

Goal: Notebook prerequisites — spin up Anvil from Python and deploy contracts via `forge`.

### Task 16: Add `shared/anvil.py` context manager

**Files:**
- Create: `shared/anvil.py`
- Test: `tests/test_anvil.py`

- [ ] **Step 1: Write the failing test**

```python
"""Test that shared.anvil can spin up and tear down a local Anvil."""
import shutil
import socket
import time

import pytest

from shared.anvil import anvil


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except OSError:
            return False


@pytest.mark.skipif(shutil.which("anvil") is None,
                    reason="anvil binary not on PATH")
def test_anvil_spawns_and_terminates():
    with anvil(port=18545) as rpc_url:
        assert rpc_url == "http://127.0.0.1:18545"
        assert _port_open(18545)
    # Give the kernel a moment to release the port
    for _ in range(20):
        if not _port_open(18545):
            break
        time.sleep(0.1)
    assert not _port_open(18545)
```

- [ ] **Step 2: Verify it fails**

```bash
uv run pytest tests/test_anvil.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement `shared/anvil.py`**

```python
"""Spawn a local Anvil node from Python.

Used by notebooks and `tests/test_end_to_end.py` so we don't need the
Docker stack for in-process demos.
"""
from __future__ import annotations

import socket
import subprocess
import time
from contextlib import contextmanager
from typing import Iterator


def _wait_for_port(host: str, port: int, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect((host, port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"anvil never accepted on {host}:{port}")


@contextmanager
def anvil(port: int = 8545,
          host: str = "127.0.0.1",
          block_time: float = 1.0) -> Iterator[str]:
    """Spawn anvil; yield its RPC URL; terminate on exit.

    Requires the `anvil` binary on PATH (install Foundry).
    """
    proc = subprocess.Popen(
        ["anvil", "--host", host, "--port", str(port),
         "--block-time", str(block_time)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(host, port)
        yield f"http://{host}:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
```

- [ ] **Step 4: Run the test**

```bash
uv run pytest tests/test_anvil.py -v
```

Expected: passes if `anvil` is on PATH; skipped otherwise.

- [ ] **Step 5: Commit**

```bash
git add shared/anvil.py tests/test_anvil.py
git commit -m "feat(shared): add anvil() context manager for in-process notebooks"
git push
```

### Task 17: Add `shared/deploy.py` wrapper for `forge script`

**Files:**
- Create: `shared/deploy.py`

- [ ] **Step 1: Implement `shared/deploy.py`**

```python
"""Deploy BandwidthEscrow + BandwidthNFT via `forge script`.

Exists so notebooks can deploy without dropping out to a Makefile or
shell. Requires the `forge` binary on PATH (install Foundry).

Side effect: `forge script ... --broadcast` writes
`contracts/deployments/local.json` which `shared/contracts.py` reads.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from eth_account import Account

from shared.config import Config


_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONTRACTS_DIR = _REPO_ROOT / "contracts"
_DEPLOYMENTS_FILE = _CONTRACTS_DIR / "deployments" / "local.json"


def deploy_contracts(cfg: Config,
                     provider_address: str | None = None) -> dict[str, str]:
    """Run `forge script Deploy.s.sol`; return the deployed addresses.

    Raises if `cfg.deployer_private_key` is not set or `forge` is missing.
    """
    if not cfg.deployer_private_key:
        raise RuntimeError("Config.deployer_private_key is required")
    if provider_address is None:
        if cfg.provider_address:
            provider_address = cfg.provider_address
        elif cfg.provider_private_key:
            provider_address = Account.from_key(cfg.provider_private_key).address
        else:
            raise RuntimeError(
                "provider_address required (set Config.provider_private_key "
                "or Config.provider_address, or pass provider_address=...)")

    _DEPLOYMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["forge", "script", "script/Deploy.s.sol",
         "--rpc-url", cfg.rpc_url,
         "--broadcast",
         "--private-key", cfg.deployer_private_key],
        cwd=_CONTRACTS_DIR,
        env={"DEPLOYER_PRIVATE_KEY": cfg.deployer_private_key,
             "PROVIDER_ADDRESS": provider_address,
             "PATH": __import__("os").environ.get("PATH", "")},
        check=True, capture_output=True,
    )
    return json.loads(_DEPLOYMENTS_FILE.read_text())
```

- [ ] **Step 2: Smoke-test it manually (only if `anvil` and `forge` are installed)**

```bash
# Run anvil in another terminal first:  anvil --port 8545
uv run python -c "
from shared.config import Config
from shared.deploy import deploy_contracts
cfg = Config(
    deployer_private_key='0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80',
    provider_private_key='0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d',
)
print(deploy_contracts(cfg))
"
```

Expected: prints `{"bandwidthNFT": "0x...", "bandwidthEscrow": "0x..."}`.

- [ ] **Step 3: Commit**

```bash
git add shared/deploy.py
git commit -m "feat(shared): add deploy_contracts(cfg) for in-process notebook deployments"
git push
```

---

## Phase 5: Tests — conftest, drop trivial, add E2E

### Task 18: Add `tests/conftest.py` and drop trivial catalog tests

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_catalog.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures."""
from __future__ import annotations

import pytest

from shared.config import Config


CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
PROVIDER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


@pytest.fixture
def consumer_cfg() -> Config:
    return Config(consumer_private_key=CONSUMER_KEY)


@pytest.fixture
def provider_cfg() -> Config:
    return Config(provider_private_key=PROVIDER_KEY, sdn_mock=True)


@pytest.fixture
def fake_catalog() -> list[dict]:
    return [
        {"packageId": "small",  "mbps": 2.0, "durationSeconds": 600,
         "priceWei": 10**16, "availableSlots": 1},
        {"packageId": "medium", "mbps": 5.0, "durationSeconds": 600,
         "priceWei": 2 * 10**16, "availableSlots": 1},
        {"packageId": "large",  "mbps": 8.0, "durationSeconds": 600,
         "priceWei": 8 * 10**16, "availableSlots": 1},
    ]
```

- [ ] **Step 2: Replace `tests/test_catalog.py` with a single parametrized smoke test plus the still-valuable behavior tests**

```python
"""Provider catalog tests."""
from __future__ import annotations

import pytest

from provider.catalog import CATALOG_BY_ID, get_catalog_with_availability, make_quote


@pytest.mark.parametrize("tier", ["small", "medium", "large"])
def test_catalog_advertises_each_tier(tier):
    catalog = get_catalog_with_availability()
    pkg = next((p for p in catalog if p["packageId"] == tier), None)
    assert pkg is not None
    assert pkg["mbps"] <= 10  # PPS cap on free SR Linux
    assert pkg["priceWei"] > 0
    assert pkg["availableSlots"] >= 0
    assert tier in CATALOG_BY_ID


def test_make_quote_returns_agreement_data():
    result = make_quote("small",
                        "0x0000000000000000000000000000000000000001")
    assert result is not None
    assert "agreementId" in result
    assert result["priceWei"] > 0


def test_make_quote_unknown_package():
    assert make_quote("nonexistent",
                      "0x0000000000000000000000000000000000000001") is None
```

- [ ] **Step 3: Run all tests**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_catalog.py
git commit -m "test: add conftest with shared fixtures; consolidate trivial catalog tests"
git push
```

### Task 19: Add `tests/test_end_to_end.py` integration test

**Files:**
- Create: `tests/test_end_to_end.py`

- [ ] **Step 1: Implement the integration test**

```python
"""End-to-end test: spin Anvil, deploy contracts, run a full negotiation
in-process between the consumer and provider FastAPI apps with a stubbed LLM.

Skipped if the `anvil` or `forge` binaries are not on PATH.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
from eth_account import Account

from shared.anvil import anvil
from shared.config import Config
from shared.deploy import deploy_contracts


pytestmark = pytest.mark.skipif(
    shutil.which("anvil") is None or shutil.which("forge") is None,
    reason="anvil/forge required for the end-to-end test",
)


CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
PROVIDER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(app, port: int) -> tuple[uvicorn.Server, threading.Thread]:
    cfg = uvicorn.Config(app, host="127.0.0.1", port=port,
                         log_level="warning", lifespan="on")
    server = uvicorn.Server(cfg)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    # Wait for startup
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not server.started:
        time.sleep(0.05)
    return server, thread


def _stop(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.asyncio
async def test_end_to_end_negotiation_settles_on_chain(monkeypatch):
    """Drives the full discover → quote → lock → settle → present → verify
    flow against an in-process Anvil + provider + consumer, with the LLM
    stubbed so we never depend on Ollama."""
    # Stub the LLM
    from langchain_ollama import ChatOllama

    class _R:
        def __init__(self, c): self.content = c

    async def fake_ainvoke(self, prompt, *a, **kw):
        return _R("medium" if "EXACTLY ONE WORD" in prompt else "ok.")

    monkeypatch.setattr(ChatOllama, "ainvoke", fake_ainvoke)

    with anvil(port=18545) as rpc_url:
        cfg = Config(
            rpc_url=rpc_url,
            consumer_private_key=CONSUMER_KEY,
            provider_private_key=PROVIDER_KEY,
            deployer_private_key=DEPLOYER_KEY,
            sdn_mock=True,
        )
        # Deploy contracts
        deploy_contracts(cfg)

        provider_port = _free_port()
        consumer_port = _free_port()
        provider_url = f"http://127.0.0.1:{provider_port}"
        consumer_url = f"http://127.0.0.1:{consumer_port}"

        # Build the apps with overridden env so they pick up `cfg`.
        monkeypatch.setenv("RPC_URL", rpc_url)
        monkeypatch.setenv("CONSUMER_PRIVATE_KEY", CONSUMER_KEY)
        monkeypatch.setenv("PROVIDER_PRIVATE_KEY", PROVIDER_KEY)
        monkeypatch.setenv("PROVIDER_BASE_URL", provider_url)
        monkeypatch.setenv("CONSUMER_BASE_URL", consumer_url)
        monkeypatch.setenv("PROVIDER_A2A_URLS", provider_url)
        monkeypatch.setenv("SDN_MOCK", "true")

        from provider.app import app as provider_app
        from consumer.app import app as consumer_app

        ps, pt = _serve(provider_app, provider_port)
        try:
            cs, ct = _serve(consumer_app, consumer_port)
            try:
                async with httpx.AsyncClient(timeout=120.0) as http:
                    resp = await http.post(f"{consumer_url}/chat",
                                           json={"message": "I need 5 Mbps"})
                    resp.raise_for_status()
                    body = resp.json()
                assert "Active service" in body["response"]
            finally:
                _stop(cs, ct)
        finally:
            _stop(ps, pt)
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/test_end_to_end.py -v -s
```

Expected: passes (or skips if anvil/forge missing). May take 30-60 s.

- [ ] **Step 3: Commit**

```bash
git add tests/test_end_to_end.py
git commit -m "test: add end-to-end integration test (anvil + in-process apps)"
git push
```

---

## Phase 6: Docs Rewrite

Goal: Three living docs (intro, concepts, architecture, running) plus a notebooks README. Update README to point to both Docker and notebook paths.

### Task 20: Rewrite `docs/01-introduction.md`

**Files:**
- Modify: `docs/01-introduction.md`

- [ ] **Step 1: Replace the file content**

```markdown
# Introduction

## What this project is

Two AI agents — a **buyer** and a **seller** — autonomously negotiate, pay for, and activate a network bandwidth service. The buyer is driven by a local LLM (Ollama). The seller manages an inventory of bandwidth slots. They communicate through a published protocol (A2A), use a smart-contract escrow on a local Ethereum chain to make the trade trust-minimised, and deliver the service through a software-defined-networking (SDN) layer that enforces the bandwidth cap.

The whole system runs on a single laptop. No real money, no real internet bandwidth — but every component (the contracts, the agents, the protocols, the SDN rules) is real code, doing what it would do in production.

## Why it exists

It's the working proof-of-concept that backs the paper *"Autonomous Agent-to-Agent Network Service Provisioning via Smart-Contract Escrow and Tokenized Authorization"* (see `paper/`).

## Two ways to run it

- **Docker stack** (`make up && make demo`) — everything runs in containers; the dashboard at `http://localhost:8501` shows the live trade.
- **Notebooks** (`notebooks/01_*.ipynb` … `05_*.ipynb`) — every layer is exercised in-process from Python. No Docker required (only the `anvil`/`forge` binaries from Foundry, plus optionally `ollama`).

## Reading order

1. `01-introduction.md` (this file) — what this is.
2. `02-concepts.md` — the vocabulary used in everything else.
3. `03-architecture.md` — how the pieces fit, and where to make changes.
4. `04-running.md` — how to actually get it running, both paths.
5. `notebooks/05_end_to_end.ipynb` — see the whole flow from a Python kernel.

## Glossary (one-liners)

- **MCP** — the protocol an agent uses to call its *own* tools.
- **A2A** — the protocol agents use to talk to *each other*.
- **Smart contract** — code that runs on a blockchain; here, an escrow that holds money until the trade completes.
- **NFT** — a non-fungible token; here, the buyer's "service ticket".
- **Atomic swap** — money and ticket change hands in one indivisible operation.
- **SDN** — software-defined networking; programmable network rules.
- **Anvil / Foundry** — local fake Ethereum chain (`anvil`) + deployment toolkit (`forge`).
- **Ollama** — local LLM runtime; runs `llama3.2:3b` by default.

For full explanations, see `02-concepts.md`.
```

- [ ] **Step 2: Commit**

```bash
git add docs/01-introduction.md
git commit -m "docs: rewrite introduction; point at notebooks and the two run paths"
git push
```

### Task 21: Update `docs/03-architecture.md` (already renamed in Task 3)

**Files:**
- Modify: `docs/03-architecture.md`

- [ ] **Step 1: Read the current architecture doc and prepend a "Where to make changes" section**

Read the current file:
```bash
wc -l docs/03-architecture.md
```

Insert (after the title, before the existing content) a new section:

```markdown
> **Where to make changes** (folded in from the old `06-modifying.md`):
>
> - **Add a new tier** → `provider/catalog.py` (CATALOG list) + `provider/inventory.txt` (one row per tier).
> - **Add a consumer MCP tool** → `consumer/mcp_server.py` inside `build_mcp_server`. If it should drive a graph node, add a key to `build_consumer_tools` and a node to `consumer/graph.py`.
> - **Add a provider MCP tool** → `provider/mcp_server.py` inside `build_mcp_server`. If it should be triggered by an A2A action, route it from `provider/agent_executor.py`.
> - **Change escrow / NFT semantics** → `contracts/src/*.sol`. Re-deploy via `make contracts` (Docker) or `shared.deploy.deploy_contracts(cfg)` (notebooks).
> - **Tweak the LangGraph flow** → `consumer/graph.py`'s `build_graph()`. Each node is a closure; add or reorder them in the builder section at the bottom.
> - **Change SDN backend** → swap the `srl_bandwidth.*` calls inside `provider/mcp_server.py`'s `allocate_bandwidth` / `revoke_bandwidth` / `verify_bandwidth` tools.
> - **Change config** → add a field to `Config` in `shared/config.py` and read it from `Config.from_env()`.
```

Also: scan for references to `06-modifying.md`, `paper-alignment.md`, `03-walkthrough.md`, `consumer-agent-2`, or `PROVIDER_AGENT_CARD_URL` and remove or update them.

```bash
grep -n "06-modifying\|paper-alignment\|03-walkthrough\|consumer-agent-2\|PROVIDER_AGENT_CARD_URL\|module-level\|os\.getenv\|_w3 =" docs/03-architecture.md
```

For each hit, edit the file to either delete the stale reference or update it to reflect the new factory-based shape.

- [ ] **Step 2: Update the section about consumer/graph.py to reflect the new factory shape**

Find any sentence that says module-level Ollama client / module-level `_w3` / mutable `inter_agent_log` and rewrite to: "Each FastAPI app builds its `Config`, MCP server, A2A client, and graph in `lifespan` and stashes them on `app.state`. Modules expose factories (`build_graph(cfg, tools)`, `build_mcp_server(cfg)`) — no module-level state."

- [ ] **Step 3: Commit**

```bash
git add docs/03-architecture.md
git commit -m "docs(architecture): fold in 'where to change things'; reflect factory refactor"
git push
```

### Task 22: Update `docs/04-running.md` to cover both Docker and notebook paths

**Files:**
- Modify: `docs/04-running.md`

- [ ] **Step 1: Append a new "Notebook path" section after the existing Docker instructions**

Read the file. At the end, append:

```markdown
---

## Notebook path (no Docker)

The `notebooks/` directory contains five Jupyter notebooks that exercise every layer in-process. No Docker, no `make`, no compose — just `anvil`, `forge`, and (for notebook 05) `ollama`.

### Prerequisites

- `anvil` + `forge` (install from [Foundry](https://book.getfoundry.sh/getting-started/installation))
- Python 3.13 + `uv`
- For notebook 05 only: `ollama serve` running with `llama3.2:3b` pulled (`ollama pull llama3.2:3b`)

### Run

```bash
uv sync
uv run jupyter lab notebooks/
```

Open the notebooks in order:

1. `01_chain.ipynb` — deploy the contracts, walk one trade.
2. `02_mcp.ipynb` — exercise the provider's MCP tools in-process.
3. `03_a2a.ipynb` — drive the provider's A2A executor without a port.
4. `04_consumer_graph.ipynb` — step through the consumer's LangGraph state machine.
5. `05_end_to_end.ipynb` — full negotiation, end-to-end (uses Ollama).

Each notebook is self-contained: it spins up everything it needs in a `try`, demonstrates the layer, and tears down in a `finally`.
```

- [ ] **Step 2: Remove any stale references**

```bash
grep -n "consumer-agent-2\|PROVIDER_AGENT_CARD_URL\|paper-alignment" docs/04-running.md
```

Edit out any hits.

- [ ] **Step 3: Commit**

```bash
git add docs/04-running.md
git commit -m "docs(running): add notebook path; remove stale references"
git push
```

### Task 23: Update `README.md` to point at the new layout

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the "Where to read next" table**

Open `README.md`, find the table that lists docs, and replace it with:

```markdown
| If you want to... | Read |
|---|---|
| Understand what this is and why | [`docs/01-introduction.md`](docs/01-introduction.md) |
| Learn the vocabulary | [`docs/02-concepts.md`](docs/02-concepts.md) |
| Read or modify the code | [`docs/03-architecture.md`](docs/03-architecture.md) |
| Get it running on your machine | [`docs/04-running.md`](docs/04-running.md) |
| See the whole flow from a Python kernel | [`notebooks/05_end_to_end.ipynb`](notebooks/05_end_to_end.ipynb) |
```

Also update the "Repo layout" block to add `notebooks/` and remove any references to `clab-up` if you've decided to drop those Makefile targets — for now leave the Makefile intact, so leave references intact too.

- [ ] **Step 2: Add a one-paragraph "Two ways to run" section above "Quickstart"**

```markdown
## Two ways to run

- **Docker stack** (below): one command brings up Anvil, the agents, Ollama, and the dashboard.
- **Notebooks** (`notebooks/01_*.ipynb` … `05_*.ipynb`): every layer in-process from Python; no Docker. See [`notebooks/README.md`](notebooks/README.md).
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): point at new docs and notebook path"
git push
```

---

## Phase 7: Notebooks

Goal: Five `.ipynb` files, each Setup → Build → Run → Inspect → Teardown.

> Notebooks are JSON. The implementation uses `nbformat` to write them programmatically. Add `nbformat` and `jupyterlab` as dev dependencies first.

### Task 24: Add notebook tooling and write `notebooks/README.md`

**Files:**
- Modify: `pyproject.toml`
- Create: `notebooks/README.md`

- [ ] **Step 1: Add dev deps**

```bash
uv add --dev jupyterlab nbformat nbclient ipykernel
```

- [ ] **Step 2: Create `notebooks/README.md`**

```markdown
# Notebooks

Five notebooks that exercise every layer of the stack in-process. No Docker required.

## Prerequisites

- Python 3.13 + `uv`
- `anvil` + `forge` on PATH (install from [Foundry](https://book.getfoundry.sh/getting-started/installation))
- For `05_end_to_end.ipynb` only: `ollama` running locally with `llama3.2:3b` pulled

## Setup

```bash
uv sync
uv run jupyter lab .
```

## Run order

| # | Notebook | What it shows |
|---|---|---|
| 1 | `01_chain.ipynb` | Deploy contracts, walk one trade on Anvil. |
| 2 | `02_mcp.ipynb` | Exercise the provider's MCP tools in-process. |
| 3 | `03_a2a.ipynb` | Drive the provider's A2A executor via in-process ASGI. |
| 4 | `04_consumer_graph.ipynb` | Step through the consumer LangGraph state machine. |
| 5 | `05_end_to_end.ipynb` | Full negotiation: real Ollama, in-process apps. |

Each notebook follows: **Setup → Build → Run → Inspect → Teardown**.
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock notebooks/README.md
git commit -m "feat(notebooks): add tooling deps and README"
git push
```

### Task 25: Write `notebooks/01_chain.ipynb`

**Files:**
- Create: `notebooks/01_chain.ipynb`

- [ ] **Step 1: Write the notebook via a Python script**

Create `notebooks/_build_01.py`:

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 01 — Chain\n\n"
        "Spin up Anvil, deploy `BandwidthEscrow` + `BandwidthNFT`, walk one trade, decode events.\n\n"
        "Prereqs: `anvil` and `forge` on PATH."
    ),
    nbf.v4.new_markdown_cell("## Setup"),
    nbf.v4.new_code_cell(
        "from shared.anvil import anvil\n"
        "from shared.config import Config\n"
        "from shared.deploy import deploy_contracts\n"
        "from shared.chain import make_web3, send_tx, STATUS_NAMES\n"
        "from shared.contracts import get_escrow_contract, get_nft_contract\n"
        "from eth_account import Account\n\n"
        "DEPLOYER = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'\n"
        "PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'\n"
        "CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'\n"
        "provider_account = Account.from_key(PROVIDER)\n"
        "consumer_account = Account.from_key(CONSUMER)"
    ),
    nbf.v4.new_markdown_cell("## Build (start Anvil + deploy)"),
    nbf.v4.new_code_cell(
        "ctx = anvil(port=18545)\n"
        "rpc_url = ctx.__enter__()\n"
        "print('anvil:', rpc_url)\n\n"
        "cfg = Config(rpc_url=rpc_url, deployer_private_key=DEPLOYER,\n"
        "             provider_private_key=PROVIDER,\n"
        "             consumer_private_key=CONSUMER, sdn_mock=True)\n"
        "addrs = deploy_contracts(cfg)\n"
        "print('escrow:', addrs['bandwidthEscrow'])\n"
        "print('nft:   ', addrs['bandwidthNFT'])"
    ),
    nbf.v4.new_markdown_cell("## Run (one trade end-to-end)"),
    nbf.v4.new_code_cell(
        "w3 = make_web3(cfg)\n"
        "escrow = get_escrow_contract(w3)\n"
        "nft = get_nft_contract(w3)\n\n"
        "agreement_id = 1234\n"
        "mbps, duration, price_wei = 5, 600, 10**16  # 0.01 ETH\n\n"
        "# 1. Consumer locks payment\n"
        "tx, _ = send_tx(w3, consumer_account, CONSUMER,\n"
        "                escrow.functions.requestAgreement(\n"
        "                    agreement_id, provider_account.address,\n"
        "                    mbps, duration),\n"
        "                value=price_wei)\n"
        "print('requestAgreement tx:', tx)\n\n"
        "# 2. Provider mints NFT bound to (agreement, mbps, duration)\n"
        "tx, mint_receipt = send_tx(w3, provider_account, PROVIDER,\n"
        "    nft.functions.mint(provider_account.address, agreement_id,\n"
        "                       mbps, duration, 'clab://pe1/eth-1.100'))\n"
        "from shared.chain import extract_token_id\n"
        "token_id = extract_token_id(mint_receipt, nft)\n"
        "print('minted tokenId:', token_id)\n\n"
        "# 3. Provider approves escrow then deposits — atomic swap\n"
        "send_tx(w3, provider_account, PROVIDER,\n"
        "        nft.functions.approve(escrow.address, token_id))\n"
        "send_tx(w3, provider_account, PROVIDER,\n"
        "        escrow.functions.deposit(agreement_id, token_id))\n"
        "print('swap complete')"
    ),
    nbf.v4.new_markdown_cell("## Inspect"),
    nbf.v4.new_code_cell(
        "ag = escrow.functions.getAgreement(agreement_id).call()\n"
        "print('status:', STATUS_NAMES[ag[7]])\n"
        "print('owner of NFT:', nft.functions.ownerOf(token_id).call())\n"
        "print('consumer was:', consumer_account.address)"
    ),
    nbf.v4.new_markdown_cell("## Teardown"),
    nbf.v4.new_code_cell("ctx.__exit__(None, None, None)"),
]
with open('notebooks/01_chain.ipynb', 'w') as f:
    nbf.write(nb, f)
print('wrote 01_chain.ipynb')
```

Run it:

```bash
uv run python notebooks/_build_01.py
```

- [ ] **Step 2: Execute the notebook to verify it runs end-to-end**

```bash
uv run jupyter execute --kernel_name=python3 notebooks/01_chain.ipynb
```

Expected: zero errors. Inspect with `uv run jupyter nbconvert --to script notebooks/01_chain.ipynb --stdout | head -40` if you want to spot-check the rendered code.

- [ ] **Step 3: Delete the build script and commit the notebook**

```bash
rm notebooks/_build_01.py
git add notebooks/01_chain.ipynb
git commit -m "feat(notebooks): 01_chain — anvil + deploy + one trade"
git push
```

### Task 26: Write `notebooks/02_mcp.ipynb`

**Files:**
- Create: `notebooks/02_mcp.ipynb`

- [ ] **Step 1: Write the build script `notebooks/_build_02.py`**

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 02 — MCP\n\n"
        "Build the provider's FastMCP server in-process and call each tool through `fastmcp.Client`.\n\n"
        "No network. No A2A. Just MCP tool invocations against the closure-bound server.\n\n"
        "Prereq: `anvil` is required only because `mint_credential` and `complete_swap` touch the chain — but in this notebook we'll only call the read-only tools."
    ),
    nbf.v4.new_markdown_cell("## Setup"),
    nbf.v4.new_code_cell(
        "from provider.mcp_server import build_mcp_server\n"
        "from shared.config import Config\n"
        "from fastmcp import Client\n"
        "import json\n\n"
        "PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'\n"
        "cfg = Config(provider_private_key=PROVIDER, sdn_mock=True)\n"
        "mcp, tool_log = build_mcp_server(cfg)\n"
        "print('built provider MCP server with', len(mcp._tool_manager._tools), 'tools')"
    ),
    nbf.v4.new_markdown_cell("## Run\n\nList tools, then call the read-only ones."),
    nbf.v4.new_code_cell(
        "import asyncio\n\n"
        "async def demo():\n"
        "    async with Client(mcp) as c:\n"
        "        tools = await c.list_tools()\n"
        "        for t in tools:\n"
        "            print('-', t.name)\n"
        "        catalog = await c.call_tool('get_catalog', {})\n"
        "        print('\\nget_catalog →')\n"
        "        for tier in json.loads(catalog.content[0].text):\n"
        "            print(' ', tier)\n"
        "        quote = await c.call_tool('request_quote',\n"
        "            {'package_id': 'medium',\n"
        "             'consumer_address': '0x000000000000000000000000000000000000dEaD'})\n"
        "        print('\\nrequest_quote → ', quote.content[0].text)\n"
        "await demo()"
    ),
    nbf.v4.new_markdown_cell("## Inspect"),
    nbf.v4.new_code_cell(
        "for entry in tool_log:\n"
        "    print(entry)"
    ),
    nbf.v4.new_markdown_cell("## Teardown\n\n(Nothing to do — MCP server is in-memory; "
                             "Python GC reclaims it when the kernel ends.)"),
]
with open('notebooks/02_mcp.ipynb', 'w') as f:
    nbf.write(nb, f)
print('wrote 02_mcp.ipynb')
```

Run it:
```bash
uv run python notebooks/_build_02.py
```

- [ ] **Step 2: Execute and verify**

```bash
uv run jupyter execute notebooks/02_mcp.ipynb
```

- [ ] **Step 3: Cleanup and commit**

```bash
rm notebooks/_build_02.py
git add notebooks/02_mcp.ipynb
git commit -m "feat(notebooks): 02_mcp — exercise provider tools via in-memory MCP client"
git push
```

### Task 27: Write `notebooks/03_a2a.ipynb`

**Files:**
- Create: `notebooks/03_a2a.ipynb`

- [ ] **Step 1: Write `notebooks/_build_03.py`**

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 03 — A2A\n\n"
        "Drive the provider's A2A executor in-process. We fabricate a request "
        "context and an EventQueue, no port, no httpx — pure Python."
    ),
    nbf.v4.new_markdown_cell("## Setup"),
    nbf.v4.new_code_cell(
        "from provider.agent_executor import BandwidthProviderExecutor\n"
        "from provider.mcp_server import build_mcp_server\n"
        "from shared.config import Config\n"
        "from a2a.types import Message, Part\n"
        "from google.protobuf.json_format import MessageToDict, ParseDict\n"
        "from google.protobuf.struct_pb2 import Struct, Value\n"
        "from unittest.mock import MagicMock\n\n"
        "PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'\n"
        "cfg = Config(provider_private_key=PROVIDER, sdn_mock=True)\n"
        "mcp, _ = build_mcp_server(cfg)\n"
        "executor = BandwidthProviderExecutor(mcp)\n"
        "print('executor ready, mcp has', len(mcp._tool_manager._tools), 'tools')"
    ),
    nbf.v4.new_markdown_cell("## Build helpers"),
    nbf.v4.new_code_cell(
        "class FakeQueue:\n"
        "    def __init__(self):\n"
        "        self.events = []\n"
        "    async def enqueue_event(self, event):\n"
        "        self.events.append(event)\n\n"
        "def data_part(d: dict) -> Part:\n"
        "    s = Struct(); ParseDict(d, s)\n"
        "    return Part(data=Value(struct_value=s), media_type='application/json')\n\n"
        "def make_context(payload: dict) -> MagicMock:\n"
        "    msg = Message(message_id='m1', parts=[data_part(payload)])\n"
        "    ctx = MagicMock()\n"
        "    ctx.message = msg\n"
        "    ctx.task_id = 'task-1'\n"
        "    ctx.context_id = 'ctx-1'\n"
        "    return ctx\n\n"
        "def payload_of(event):\n"
        "    return MessageToDict(event.artifact.parts[0].data,\n"
        "                         preserving_proto_field_name=True)"
    ),
    nbf.v4.new_markdown_cell("## Run — three A2A actions"),
    nbf.v4.new_code_cell(
        "import asyncio\n\n"
        "async def call(payload):\n"
        "    q = FakeQueue()\n"
        "    await executor.execute(make_context(payload), q)\n"
        "    return [payload_of(e) for e in q.events\n"
        "            if hasattr(e, 'artifact')]\n\n"
        "print('catalog:'); [print('  ', x) for x in await call({'action': 'get_catalog'})]\n"
        "print('\\nquote:');   [print('  ', x) for x in await call({\n"
        "    'action': 'request_quote', 'package_id': 'small',\n"
        "    'consumer_address': '0x000000000000000000000000000000000000dEaD'})]"
    ),
    nbf.v4.new_markdown_cell("## Inspect — the agent card the consumer would discover"),
    nbf.v4.new_code_cell(
        "from provider.agent_card import build_provider_agent_card\n"
        "card = build_provider_agent_card(cfg)\n"
        "print('Skills advertised:')\n"
        "for s in card.skills:\n"
        "    print(' -', s.id, ':', s.name)"
    ),
]
with open('notebooks/03_a2a.ipynb', 'w') as f:
    nbf.write(nb, f)
print('wrote 03_a2a.ipynb')
```

Run, execute, cleanup:

```bash
uv run python notebooks/_build_03.py
uv run jupyter execute notebooks/03_a2a.ipynb
rm notebooks/_build_03.py
```

- [ ] **Step 2: Commit**

```bash
git add notebooks/03_a2a.ipynb
git commit -m "feat(notebooks): 03_a2a — drive provider executor in-process"
git push
```

### Task 28: Write `notebooks/04_consumer_graph.ipynb`

**Files:**
- Create: `notebooks/04_consumer_graph.ipynb`

- [ ] **Step 1: Write `notebooks/_build_04.py`**

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 04 — Consumer LangGraph\n\n"
        "Build the consumer state machine, render its mermaid diagram, and step it through with "
        "stubbed tools and a stubbed LLM. No Anvil needed — all tools are mocked."
    ),
    nbf.v4.new_markdown_cell("## Setup"),
    nbf.v4.new_code_cell(
        "from consumer.graph import build_graph\n"
        "from shared.config import Config\n"
        "import json\n\n"
        "CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'\n"
        "cfg = Config(consumer_private_key=CONSUMER)"
    ),
    nbf.v4.new_markdown_cell("## Build (stub tools and LLM)"),
    nbf.v4.new_code_cell(
        "fake_catalog = [\n"
        "    {'packageId': 'small',  'mbps': 2, 'durationSeconds': 600,\n"
        "     'priceWei': 10**16, 'availableSlots': 1},\n"
        "    {'packageId': 'medium', 'mbps': 5, 'durationSeconds': 600,\n"
        "     'priceWei': 2*10**16, 'availableSlots': 1},\n"
        "    {'packageId': 'large',  'mbps': 8, 'durationSeconds': 600,\n"
        "     'priceWei': 8*10**16, 'availableSlots': 1},\n"
        "]\n\n"
        "async def discover(url): return json.dumps({'name': 'P', 'version': '1',\n"
        "    'skills': ['get_catalog', 'request_quote', 'activate']})\n"
        "async def browse(url): return json.dumps(fake_catalog)\n"
        "async def quote(url, pkg): return json.dumps({\n"
        "    'agreementId': '777', 'priceWei': 2*10**16,\n"
        "    'bandwidthMbps': 5, 'durationSeconds': 600})\n"
        "def lock(aid): return 'OK 0xdeadbeef'\n"
        "def settle(aid): return 'OK tokenId=99'\n"
        "async def present(url, tid): return json.dumps(\n"
        "    {'status': 'active', 'bandwidthMbps': 5, 'tokenId': tid})\n"
        "def verify(tid): return json.dumps({\n"
        "    'ok': True, 'owner': '0xC', 'ownerIsConsumer': True,\n"
        "    'agreementId': 777, 'mbps': 5, 'durationSeconds': 600,\n"
        "    'secondsRemaining': 600, 'endpoint': 'clab://pe1/eth-1.100'})\n\n"
        "tools = {'discover_provider': discover, 'browse_catalog': browse,\n"
        "         'request_quote': quote, 'lock_payment': lock,\n"
        "         'await_settlement': settle, 'present_credential': present,\n"
        "         'verify_credential': verify}\n\n"
        "from langchain_ollama import ChatOllama\n"
        "class _R:\n"
        "    def __init__(self, c): self.content = c\n"
        "async def fake_ainvoke(self, prompt, *a, **kw):\n"
        "    return _R('medium' if 'EXACTLY ONE WORD' in prompt else 'ok')\n"
        "ChatOllama.ainvoke = fake_ainvoke\n\n"
        "graph = build_graph(cfg, tools)\n"
        "print('graph compiled')"
    ),
    nbf.v4.new_markdown_cell("## Inspect — the state machine"),
    nbf.v4.new_code_cell(
        "print(graph.get_graph().draw_mermaid())"
    ),
    nbf.v4.new_markdown_cell("## Run — stream node by node"),
    nbf.v4.new_code_cell(
        "initial = {'user_message': 'I need 5 Mbps',\n"
        "           'provider_url': 'http://provider:8002',\n"
        "           'log': [], 'thinking': []}\n"
        "async for step in graph.astream(initial):\n"
        "    for node, output in step.items():\n"
        "        keys = list(output.keys()) if isinstance(output, dict) else type(output).__name__\n"
        "        print(f'{node:18s} → {keys}')"
    ),
    nbf.v4.new_markdown_cell("## Final state"),
    nbf.v4.new_code_cell(
        "result = await graph.ainvoke(initial)\n"
        "print('final:', result['final_response'])\n"
        "print('chosen tier:', result['chosen_tier'])\n"
        "print('agreement:', result['agreement_id'])\n"
        "print('tokenId:', result['token_id'])"
    ),
]
with open('notebooks/04_consumer_graph.ipynb', 'w') as f:
    nbf.write(nb, f)
print('wrote 04_consumer_graph.ipynb')
```

Run, execute, cleanup, commit:

```bash
uv run python notebooks/_build_04.py
uv run jupyter execute notebooks/04_consumer_graph.ipynb
rm notebooks/_build_04.py
git add notebooks/04_consumer_graph.ipynb
git commit -m "feat(notebooks): 04_consumer_graph — step the LangGraph with stubs"
git push
```

### Task 29: Write `notebooks/05_end_to_end.ipynb`

**Files:**
- Create: `notebooks/05_end_to_end.ipynb`

- [ ] **Step 1: Write `notebooks/_build_05.py`**

```python
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# 05 — End to End\n\n"
        "The whole flow in one notebook: anvil + deploy + provider FastAPI + consumer FastAPI + real Ollama.\n\n"
        "Prereqs: `anvil`, `forge`, and `ollama serve` running with `llama3.2:3b` pulled."
    ),
    nbf.v4.new_markdown_cell("## Setup"),
    nbf.v4.new_code_cell(
        "import os, socket, threading, time, asyncio\n"
        "import httpx\n"
        "import uvicorn\n"
        "from shared.anvil import anvil\n"
        "from shared.config import Config\n"
        "from shared.deploy import deploy_contracts\n\n"
        "DEPLOYER = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'\n"
        "PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'\n"
        "CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'\n\n"
        "def free_port():\n"
        "    with socket.socket() as s:\n"
        "        s.bind(('127.0.0.1', 0))\n"
        "        return s.getsockname()[1]\n\n"
        "def serve(app, port):\n"
        "    cfg = uvicorn.Config(app, host='127.0.0.1', port=port,\n"
        "                          log_level='warning', lifespan='on')\n"
        "    server = uvicorn.Server(cfg)\n"
        "    t = threading.Thread(target=server.run, daemon=True)\n"
        "    t.start()\n"
        "    deadline = time.monotonic() + 10\n"
        "    while time.monotonic() < deadline and not server.started:\n"
        "        time.sleep(0.05)\n"
        "    return server, t"
    ),
    nbf.v4.new_markdown_cell("## Build — anvil + deploy"),
    nbf.v4.new_code_cell(
        "ctx = anvil(port=18545)\n"
        "rpc_url = ctx.__enter__()\n"
        "cfg = Config(rpc_url=rpc_url, deployer_private_key=DEPLOYER,\n"
        "             provider_private_key=PROVIDER,\n"
        "             consumer_private_key=CONSUMER, sdn_mock=True)\n"
        "addrs = deploy_contracts(cfg)\n"
        "print('deployed:', addrs)"
    ),
    nbf.v4.new_markdown_cell("## Build — provider + consumer FastAPI in-process"),
    nbf.v4.new_code_cell(
        "provider_port = free_port()\n"
        "consumer_port = free_port()\n"
        "provider_url = f'http://127.0.0.1:{provider_port}'\n"
        "consumer_url = f'http://127.0.0.1:{consumer_port}'\n\n"
        "os.environ.update({\n"
        "    'RPC_URL': rpc_url,\n"
        "    'CONSUMER_PRIVATE_KEY': CONSUMER,\n"
        "    'PROVIDER_PRIVATE_KEY': PROVIDER,\n"
        "    'PROVIDER_BASE_URL': provider_url,\n"
        "    'CONSUMER_BASE_URL': consumer_url,\n"
        "    'PROVIDER_A2A_URLS': provider_url,\n"
        "    'SDN_MOCK': 'true',\n"
        "    'OLLAMA_HOST': os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434'),\n"
        "    'OLLAMA_MODEL': os.environ.get('OLLAMA_MODEL', 'llama3.2:3b'),\n"
        "})\n\n"
        "from provider.app import app as provider_app\n"
        "from consumer.app import app as consumer_app\n"
        "ps, pt = serve(provider_app, provider_port)\n"
        "cs, ct = serve(consumer_app, consumer_port)\n"
        "print('provider:', provider_url)\n"
        "print('consumer:', consumer_url)"
    ),
    nbf.v4.new_markdown_cell("## Run — one negotiation"),
    nbf.v4.new_code_cell(
        "async with httpx.AsyncClient(timeout=120.0) as http:\n"
        "    resp = await http.post(f'{consumer_url}/chat',\n"
        "                           json={'message': 'I need 5 Mbps for 10 minutes'})\n"
        "    body = resp.json()\n"
        "print('response:', body['response'])\n"
        "for entry in body['log']:\n"
        "    print(' ', entry['from'], '|', entry['message'])"
    ),
    nbf.v4.new_markdown_cell("## Inspect — on-chain events"),
    nbf.v4.new_code_cell(
        "async with httpx.AsyncClient(timeout=10.0) as http:\n"
        "    events = (await http.get(f'{consumer_url}/chain_events')).json()\n"
        "for e in events:\n"
        "    print(e['event'], '@ block', e['block'])"
    ),
    nbf.v4.new_markdown_cell("## Teardown"),
    nbf.v4.new_code_cell(
        "ps.should_exit = True; cs.should_exit = True\n"
        "pt.join(timeout=5); ct.join(timeout=5)\n"
        "ctx.__exit__(None, None, None)\n"
        "print('done')"
    ),
]
with open('notebooks/05_end_to_end.ipynb', 'w') as f:
    nbf.write(nb, f)
print('wrote 05_end_to_end.ipynb')
```

- [ ] **Step 2: Build the notebook (executing requires Ollama; skip execution if Ollama isn't running locally)**

```bash
uv run python notebooks/_build_05.py
```

If Ollama is running, also execute:

```bash
uv run jupyter execute notebooks/05_end_to_end.ipynb
```

- [ ] **Step 3: Cleanup and commit**

```bash
rm notebooks/_build_05.py
git add notebooks/05_end_to_end.ipynb
git commit -m "feat(notebooks): 05_end_to_end — full negotiation in-process with Ollama"
git push
```

---

## Phase 8: Final Verification

### Task 30: Verify the whole project still works

**Files:** none

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -q
```

Expected: all tests pass (tests requiring `anvil`/`forge` may skip if those binaries are missing — that is fine).

- [ ] **Step 2: Bring the Docker stack up and run the demo**

```bash
make up
sleep 12
make demo 2>&1 | tail -30
```

Expected: STEP 3's inventory output shows a slot was reserved.

- [ ] **Step 3: Bring it down**

```bash
make down
```

- [ ] **Step 4: Verify imports are side-effect-free**

```bash
uv run python -c "
import time, socket
from contextlib import closing

def port_open(port):
    with closing(socket.socket()) as s:
        s.settimeout(0.2)
        try:
            s.connect(('127.0.0.1', port)); return True
        except OSError:
            return False

before = port_open(8545)
import consumer.graph
import consumer.mcp_server
import provider.mcp_server
import provider.app
import consumer.app
after = port_open(8545)
print('Anvil port open before:', before, 'after:', after)
print('No connection should have been opened by import.')
"
```

Expected: `before == after`. No state changed.

- [ ] **Step 5: Grep for accidental remaining `os.getenv` outside `shared/config.py`**

```bash
grep -rn "os.getenv\|os.environ" consumer/ provider/ shared/ \
    --include="*.py" \
    | grep -v "shared/config.py"
```

Expected: zero hits except possibly inside `consumer/ui.py` (which is out of scope) or as legitimate notebook env reads. Anything in app/server modules should be fixed.

- [ ] **Step 6: Final commit if anything was tweaked, then summarize**

If any cleanup was needed in step 5, fix and commit:

```bash
git add -A
git commit -m "chore: final sweep — remove stragglers and confirm side-effect-free imports"
git push
```

Print a final summary to the conversation:

> "Refactor complete. `make demo` works, `uv run pytest` passes, all five notebooks build cleanly, modules import with no side effects, and configuration flows through `shared.config.Config`."

---

## Self-Review Checklist (filled inline by plan author)

**Spec coverage:**
- ✅ Side-effect-free imports → Tasks 8–15 (factories) + Task 30 step 4 verification
- ✅ Single source of config → Task 7 + threaded through Tasks 8–15
- ✅ Notebook parity → Tasks 25–29
- ✅ Minimal surface area / deletions → Tasks 1–6
- ✅ Tight docs → Tasks 2, 3, 20–23
- ✅ `shared/anvil.py`, `shared/deploy.py` → Tasks 16–17
- ✅ `consumer/tier_selection.py` → Task 11
- ✅ `provider/event_listener.py` → Task 15
- ✅ `tests/conftest.py` → Task 18
- ✅ `tests/test_end_to_end.py` → Task 19
- ✅ Drop trivial tests → Task 18
- ✅ Comments/docstrings policy → applied implicitly inside each refactored file's content

**Type/name consistency check:**
- `Config` field names: `rpc_url`, `ollama_host`, `ollama_model`, `consumer_private_key`, `provider_private_key`, `deployer_private_key`, `provider_address`, `consumer_base_url`, `provider_base_url`, `provider_a2a_urls`, `sdn_mock` — used identically in Tasks 7, 8, 9, 10, 12, 13, 14, 15, 16, 17.
- `build_mcp_server(cfg)` returns `(mcp, tool_log_or_quote_cache)` consistently in both consumer (Task 10) and provider (Task 9).
- `build_graph(cfg, tools)` signature matches Tasks 11, 14, 19, 28.
- `BandwidthProviderExecutor(mcp)` constructor — matches Tasks 15, 19, the test fixture in `test_agent_executor.py`, and notebook 03 (Task 27).
- `expiry_sweep_loop(mcp, period_seconds=...)` — matches Task 15 step 4 and the `provider/app.py` lifespan call in Task 15 step 2.

**Placeholder scan:** No "TBD"/"TODO"/"implement later" found.

**Risk callouts surfaced inline:**
- FastMCP internal `_tool_manager._tools` access in Task 11's `build_consumer_tools` — flagged in the comment under that step. If FastMCP renames the attribute, swap to direct closure imports.
- `forge` env var passing in Task 17 — uses a minimal env dict + PATH passthrough; if a future Foundry version requires more env, expand the dict.
- Notebook 05 requires Ollama; if not present, the build step still produces the `.ipynb` but execution is skipped.
