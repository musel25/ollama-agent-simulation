# A2A + per-agent MCP + real SDN realignment — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the implementation in line with the paper's claim that A2A is the inter-agent protocol and MCP is the intra-agent tool-invocation protocol. Each agent owns its own MCP server. Activation calls real SDN (gNMI + tc) via the brother repo. Multi-agent ready.

**Architecture:** Consumer LLM ↔ in-memory FastMCP `Client` ↔ `consumer/mcp_server.py`; tools that talk to a provider use `a2a-sdk` underneath. Provider exposes an A2A server (Starlette routes from `a2a-sdk`) mounted on FastAPI; an `AgentExecutor` routes inbound A2A messages to provider's own MCP via in-memory client. Activation = consumer A2A `message/send` with `{action:"activate", token_id, nonce, signature}` → executor verifies → calls `srl_bandwidth.allocate_bandwidth`. The separate `:8003` gateway is deleted; gateway role is folded into A2A.

**Tech Stack:** `a2a-sdk` (Google Agent2Agent reference SDK), `fastmcp` (in-memory MCP transport), `pygnmi` (via `srl_bandwidth` package), `web3.py`, `eth_account`, FastAPI, Starlette, pytest + pytest-asyncio, Foundry/Anvil, ContainerLab + Nokia SR Linux (host-side).

**Spec:** `docs/superpowers/specs/2026-05-01-a2a-mcp-realignment-design.md`

---

## File map

### Brother repo (`~/Github/srl-gnmi-bandwidth-poc`)

| File | Action | Responsibility |
|---|---|---|
| `src/` → `srl_bandwidth/` | **Rename** | Real Python package name so `pip install git+...` works. |
| `src/__init__.py` | **Move** | Becomes `srl_bandwidth/__init__.py`. |
| `src/bandwidth.py` etc. | **Move** | Update internal imports `from src.X` → `from srl_bandwidth.X`. |
| `pyproject.toml` | **Modify** | `[project] name = "srl-bandwidth"`; add `[tool.hatch.build.targets.wheel] packages = ["srl_bandwidth"]`. |
| `README.md`, `CLAUDE.md` | **Modify** | Update example commands (`uv run python -m srl_bandwidth.demo`). |

### This repo (`~/Github/ollama-agent-simulation`)

| File | Action | Responsibility |
|---|---|---|
| `pyproject.toml` | **Modify** | `uv add a2a-sdk srl-bandwidth`. |
| `shared/slot_pool.py` | **Create** | `(pe, subinterface, ce)` slot reservation per tier; fcntl-locked file. |
| `shared/a2a_messages.py` | **Create** | Pydantic models for A2A `data` payloads. |
| `provider/inventory.txt` | **Modify** | New JSONL with `slots` array per tier. |
| `provider/catalog.py` | **Modify** | Rescale catalog (50/100/500 → 2/5/8 Mbps). Use `slot_pool` for availability. |
| `provider/mcp_server.py` | **Modify** | Add 5 tools: `mint_credential`, `complete_swap`, `verify_credential_ownership`, `allocate_bandwidth`, `revoke_bandwidth`, `verify_bandwidth`. |
| `provider/agent_card.py` | **Create** | `a2a.types.AgentCard` builder. |
| `provider/agent_executor.py` | **Create** | `BandwidthProviderExecutor(AgentExecutor)` — routes A2A messages to MCP. |
| `provider/app.py` | **Modify** | Mount a2a-sdk routes; replace static AGENT_CARD; event listener uses in-memory MCP client. |
| `provider/gateway.py` | **Delete** | Gateway role moves into agent_executor. |
| `consumer/mcp_server.py` | **Create** | FastMCP server with 7 tools (3 A2A-bound + 4 local). |
| `consumer/a2a_client.py` | **Create** | Wrapper around `a2a-sdk` client. |
| `consumer/agent_card.py` | **Create** | `a2a.types.AgentCard` for the consumer. |
| `consumer/app.py` | **Modify** | LLM loop wires `Client(consumer_mcp)`; system prompt updated. |
| `consumer/mcp_client.py` | **Delete** | Cross-network MCP is gone. |
| `Dockerfile.provider` | **Modify** | Drop gateway.py from CMD; mount docker socket. |
| `docker-compose.yml` | **Modify** | Drop `:8003`, parameterize for multi-agent, add `consumer-agent-2`. |
| `Makefile` | **Modify** | New `clab-up`, `clab-down`, `demo-real` targets. |
| `.env.example` | **Modify** | Add `CONSUMER_PRIVATE_KEY_2`, `PROVIDER_A2A_URLS`, `SDN_MOCK`. |
| `tests/test_slot_pool.py` | **Create** | Unit tests for `shared/slot_pool.py`. |
| `tests/test_provider_mcp.py` | **Create** | In-memory MCP tests for provider tools. |
| `tests/test_consumer_mcp.py` | **Create** | In-memory MCP tests for consumer tools. (Renames `tests/test_mcp_client.py`.) |
| `tests/test_agent_executor.py` | **Create** | A2A executor tests via in-process Starlette client. |
| `tests/test_catalog.py` | **Modify** | Update for rescaled values + slot pool semantics. |

---

## Phase 0 — Brother repo prep

> Worked in `~/Github/srl-gnmi-bandwidth-poc`, branch `main`. The repo is small; one commit is fine.

### Task 1: Rename `src/` to `srl_bandwidth/`

**Files (in brother repo):**
- Rename: `src/` → `srl_bandwidth/`
- Modify: `srl_bandwidth/bandwidth.py`, `srl_bandwidth/demo.py`, `srl_bandwidth/mcp_server.py` (internal imports)
- Modify: `pyproject.toml`
- Modify: `README.md`, `CLAUDE.md` (run-command examples)
- Modify: `.claude/settings.json` (if it references `src.mcp_server`)

- [ ] **Step 1: Move directory using git**

```bash
cd ~/Github/srl-gnmi-bandwidth-poc
git mv src srl_bandwidth
```

- [ ] **Step 2: Update internal imports**

In `srl_bandwidth/mcp_server.py`, change:

```python
from src.bandwidth import (
    allocate_bandwidth as _allocate,
    revoke_bandwidth as _revoke,
    verify_bandwidth as _verify,
)
from src.models import ServiceRequest
```

to:

```python
from srl_bandwidth.bandwidth import (
    allocate_bandwidth as _allocate,
    revoke_bandwidth as _revoke,
    verify_bandwidth as _verify,
)
from srl_bandwidth.models import ServiceRequest
```

In `srl_bandwidth/bandwidth.py`, change:

```python
from src.models import ServiceRequest
```

to:

```python
from srl_bandwidth.models import ServiceRequest
```

In `srl_bandwidth/demo.py`, change every `from src.` → `from srl_bandwidth.`.

In `srl_bandwidth/mcp_server.py`, also remove the `_project_root` sys.path hack (no longer needed once it's a real package — the comment block above the imports should be deleted).

- [ ] **Step 3: Update `pyproject.toml`**

Replace contents with:

```toml
[project]
name = "srl-bandwidth"
version = "0.1.0"
description = "SR Linux gNMI bandwidth allocation PoC — network service activation layer for autonomous agent-to-agent provisioning"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "iperf3>=0.1.11",
    "mcp[cli]>=1.27.0",
    "pygnmi>=0.8.15",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0.3",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["srl_bandwidth"]
```

- [ ] **Step 4: Smoke-test the install locally**

```bash
cd ~/Github/srl-gnmi-bandwidth-poc
uv sync
uv run python -c "from srl_bandwidth.bandwidth import allocate_bandwidth, revoke_bandwidth, verify_bandwidth; from srl_bandwidth.models import ServiceRequest; print('imports ok')"
```

Expected output: `imports ok`. If imports fail, fix the offending file before continuing.

- [ ] **Step 5: Update docs**

In `README.md`, replace every occurrence of:
- `python -m src.demo` → `python -m srl_bandwidth.demo`
- `python -m src.mcp_server` → `python -m srl_bandwidth.mcp_server`
- `mcp dev src/mcp_server.py` → `mcp dev srl_bandwidth/mcp_server.py`

Same in `CLAUDE.md`.

- [ ] **Step 6: Update `.claude/settings.json`**

If it references `src.mcp_server` or `src/mcp_server.py`, replace with the `srl_bandwidth` equivalent. If the file does not exist or doesn't reference these strings, skip.

- [ ] **Step 7: Commit and push**

```bash
cd ~/Github/srl-gnmi-bandwidth-poc
git add -A
git commit -m "$(cat <<'EOF'
refactor: rename src/ to srl_bandwidth/ for installable package

Lets downstream repos pip install via 'srl-bandwidth @ git+...' instead of
needing the source layout. Updates internal imports, pyproject hatch config,
README/CLAUDE.md command examples.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

- [ ] **Step 8: Capture the commit SHA for pinning**

```bash
git rev-parse HEAD
```

Save the printed SHA — it pins the dependency in Task 4.

---

### Task 2: Verify install via Git URL

**Files:** none (smoke test only)

- [ ] **Step 1: Install into a throwaway venv**

```bash
mkdir -p /tmp/srl-install-test && cd /tmp/srl-install-test
uv venv
uv pip install "srl-bandwidth @ git+https://github.com/musel25/srl-gnmi-bandwidth-poc.git@<SHA-FROM-TASK-1-STEP-8>"
```

Replace `<SHA-FROM-TASK-1-STEP-8>` with the actual SHA.

- [ ] **Step 2: Smoke import**

```bash
uv run python -c "from srl_bandwidth.bandwidth import allocate_bandwidth; from srl_bandwidth.models import ServiceRequest; print('install ok')"
```

Expected: `install ok`.

- [ ] **Step 3: Cleanup**

```bash
cd ~ && rm -rf /tmp/srl-install-test
```

No commit — this is a smoke test only.

---

## Phase 1 — Dependencies

> Worked in `~/Github/ollama-agent-simulation`, branch `feat/mcp-a2a`.

### Task 3: Add `a2a-sdk` and `srl-bandwidth`

**Files:**
- Modify: `pyproject.toml`, `uv.lock`

- [ ] **Step 1: Add a2a-sdk**

```bash
cd ~/Github/ollama-agent-simulation
uv add "a2a-sdk>=1.0,<2.0"
```

- [ ] **Step 2: Add srl-bandwidth pinned to the Phase-0 SHA**

```bash
uv add "srl-bandwidth @ git+https://github.com/musel25/srl-gnmi-bandwidth-poc.git@<SHA-FROM-TASK-1-STEP-8>"
```

- [ ] **Step 3: Smoke import**

```bash
uv run python -c "
import a2a
from a2a.types import AgentCard, AgentSkill, AgentCapabilities, AgentInterface
from a2a.server.agent_execution import AgentExecutor
from a2a.server.request_handlers import DefaultRequestHandler
from srl_bandwidth.bandwidth import allocate_bandwidth
print('imports ok')
"
```

Expected: `imports ok`. If any import fails:
- For `a2a.*` — adjust the import path per the installed a2a-sdk version (check `uv run python -c "import a2a; print(a2a.__file__)"` and explore). Update subsequent tasks to match the actual API.
- For `srl_bandwidth.*` — re-run Phase 0 Task 2 to confirm install integrity.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "$(cat <<'EOF'
chore: add a2a-sdk and srl-bandwidth deps

a2a-sdk for inter-agent protocol implementation.
srl-bandwidth (sibling repo) for gNMI + tc SDN activation.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 2 — Provider intra-agent MCP

### Task 4: Slot-pool data structure

**Files:**
- Create: `shared/slot_pool.py`
- Create: `tests/test_slot_pool.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_slot_pool.py`:

```python
import json
import time
from pathlib import Path

import pytest

from shared.slot_pool import SlotPool, Slot


@pytest.fixture
def tmp_inventory(tmp_path: Path) -> Path:
    f = tmp_path / "inventory.txt"
    rows = [
        {"tier": "small", "mbps": 2, "durationSeconds": 600, "slots": [
            {"pe": "pe1", "subinterface": "ethernet-1/2.0", "ce": "ce1",
             "agreementId": None, "expiresAt": None}
        ]},
        {"tier": "medium", "mbps": 5, "durationSeconds": 600, "slots": [
            {"pe": "pe1", "subinterface": "ethernet-1/3.0", "ce": "ce3",
             "agreementId": None, "expiresAt": None}
        ]},
    ]
    with open(f, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return f


def test_available_slots_initial(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    assert pool.available_count("small") == 1
    assert pool.available_count("medium") == 1
    assert pool.available_count("nonexistent") == 0


def test_reserve_binds_slot_to_agreement(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    slot = pool.reserve("small", agreement_id=42, duration_seconds=600)
    assert slot is not None
    assert slot.pe == "pe1"
    assert slot.subinterface == "ethernet-1/2.0"
    assert slot.ce == "ce1"
    assert pool.available_count("small") == 0


def test_reserve_returns_none_when_full(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("small", agreement_id=42, duration_seconds=600)
    second = pool.reserve("small", agreement_id=43, duration_seconds=600)
    assert second is None


def test_release_frees_slot(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("small", agreement_id=42, duration_seconds=600)
    assert pool.available_count("small") == 0
    pool.release(agreement_id=42)
    assert pool.available_count("small") == 1


def test_lookup_returns_slot_for_agreement(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("medium", agreement_id=99, duration_seconds=600)
    slot = pool.lookup(99)
    assert slot is not None
    assert slot.pe == "pe1"
    assert slot.subinterface == "ethernet-1/3.0"
    assert slot.ce == "ce3"


def test_expired_slots_are_reclaimed_on_read(tmp_inventory):
    pool = SlotPool(tmp_inventory)
    pool.reserve("small", agreement_id=42, duration_seconds=1)
    time.sleep(1.5)
    # Re-instantiate: SlotPool is stateless wrt the file
    pool2 = SlotPool(tmp_inventory)
    assert pool2.available_count("small") == 1
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_slot_pool.py -v
```

Expected: ImportError (`shared.slot_pool` doesn't exist).

- [ ] **Step 3: Implement `shared/slot_pool.py`**

```python
"""
SlotPool — file-backed (pe, subinterface, ce) slot reservations per tier.

Inventory file format (JSONL, one row per tier):
{"tier": "small", "mbps": 2, "durationSeconds": 600, "slots": [
    {"pe": "pe1", "subinterface": "ethernet-1/2.0", "ce": "ce1",
     "agreementId": null, "expiresAt": null}
]}

All reads/writes hold fcntl.LOCK_EX. Expired slots (expiresAt < now) are
reclaimed on every read so list-and-write becomes consistent.
"""
from __future__ import annotations

import fcntl
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Slot:
    pe: str
    subinterface: str
    ce: str


class SlotPool:
    def __init__(self, inventory_path: Path | str):
        self.path = Path(inventory_path)

    # ── public api ────────────────────────────────────────────────────────────
    def available_count(self, tier: str) -> int:
        rows = self._read_and_reclaim()
        for row in rows:
            if row["tier"] == tier:
                return sum(1 for s in row["slots"] if s["agreementId"] is None)
        return 0

    def reserve(self, tier: str, agreement_id: int, duration_seconds: int) -> Optional[Slot]:
        with self._open_locked() as f:
            rows = self._read_and_reclaim_locked(f)
            for row in rows:
                if row["tier"] != tier:
                    continue
                for s in row["slots"]:
                    if s["agreementId"] is None:
                        s["agreementId"] = agreement_id
                        s["expiresAt"] = time.time() + duration_seconds
                        self._write_locked(f, rows)
                        return Slot(pe=s["pe"], subinterface=s["subinterface"], ce=s["ce"])
                return None
            return None

    def release(self, agreement_id: int) -> None:
        with self._open_locked() as f:
            rows = self._read_and_reclaim_locked(f)
            for row in rows:
                for s in row["slots"]:
                    if s["agreementId"] == agreement_id:
                        s["agreementId"] = None
                        s["expiresAt"] = None
            self._write_locked(f, rows)

    def lookup(self, agreement_id: int) -> Optional[Slot]:
        rows = self._read_and_reclaim()
        for row in rows:
            for s in row["slots"]:
                if s["agreementId"] == agreement_id:
                    return Slot(pe=s["pe"], subinterface=s["subinterface"], ce=s["ce"])
        return None

    def tiers(self) -> list[dict]:
        """Return list of {tier, mbps, durationSeconds, availableSlots} for catalog use."""
        rows = self._read_and_reclaim()
        return [
            {
                "tier": r["tier"],
                "mbps": r["mbps"],
                "durationSeconds": r["durationSeconds"],
                "availableSlots": sum(1 for s in r["slots"] if s["agreementId"] is None),
            }
            for r in rows
        ]

    # ── internals ─────────────────────────────────────────────────────────────
    def _open_locked(self):
        f = open(self.path, "r+")
        fcntl.flock(f, fcntl.LOCK_EX)
        return _LockedFile(f)

    def _read_and_reclaim(self) -> list[dict]:
        with self._open_locked() as f:
            rows = self._read_and_reclaim_locked(f)
            self._write_locked(f, rows)
            return rows

    def _read_and_reclaim_locked(self, f) -> list[dict]:
        f.handle.seek(0)
        now = time.time()
        rows: list[dict] = []
        for line in f.handle.read().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for s in row.get("slots", []):
                if s.get("expiresAt") is not None and s["expiresAt"] < now:
                    s["agreementId"] = None
                    s["expiresAt"] = None
            rows.append(row)
        return rows

    def _write_locked(self, f, rows: list[dict]) -> None:
        f.handle.seek(0)
        f.handle.truncate()
        for row in rows:
            f.handle.write(json.dumps(row) + "\n")


class _LockedFile:
    def __init__(self, handle):
        self.handle = handle

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
        finally:
            self.handle.close()
        return False
```

- [ ] **Step 4: Run tests, expect pass**

```bash
uv run pytest tests/test_slot_pool.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add shared/slot_pool.py tests/test_slot_pool.py
git commit -m "$(cat <<'EOF'
feat: add SlotPool for (pe, subinterface, ce) reservations

Replaces the simple slot counter in catalog.py with explicit per-slot
binding so the SDN tool knows which subinterface to configure for each
agreement. fcntl-locked file backing; expired slots reclaimed on read.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 5: Migrate inventory.txt and refactor catalog.py to use SlotPool

**Files:**
- Modify: `provider/inventory.txt`
- Modify: `provider/catalog.py`
- Modify: `tests/test_catalog.py`

- [ ] **Step 1: Update tests/test_catalog.py for new schema**

Replace the contents of `tests/test_catalog.py`:

```python
import json
import pytest
from pathlib import Path

from provider.catalog import (
    CATALOG_BY_ID,
    get_catalog_with_availability,
    make_quote,
)


def test_catalog_has_three_tiers():
    catalog = get_catalog_with_availability()
    assert len(catalog) == 3
    tiers = {p["packageId"] for p in catalog}
    assert tiers == {"small", "medium", "large"}


def test_catalog_uses_rescaled_mbps():
    """Mbps values must fit the 1000 PPS cap of the free SR Linux container."""
    catalog = get_catalog_with_availability()
    for p in catalog:
        assert p["mbps"] <= 10, f"{p['packageId']} mbps={p['mbps']} exceeds PPS cap"


def test_catalog_has_required_fields():
    catalog = get_catalog_with_availability()
    for p in catalog:
        assert "packageId" in p
        assert "mbps" in p
        assert "priceWei" in p
        assert "availableSlots" in p
        assert p["availableSlots"] >= 0


def test_catalog_by_id_has_all_tiers():
    assert "small" in CATALOG_BY_ID
    assert "medium" in CATALOG_BY_ID
    assert "large" in CATALOG_BY_ID


def test_make_quote_returns_agreement_data():
    result = make_quote("small", "0x0000000000000000000000000000000000000001")
    assert result is not None
    assert "agreementId" in result
    assert "priceWei" in result
    assert "bandwidthMbps" in result
    assert "durationSeconds" in result
    assert result["priceWei"] > 0


def test_make_quote_unknown_package():
    result = make_quote("nonexistent", "0x0000000000000000000000000000000000000001")
    assert result is None
```

- [ ] **Step 2: Replace `provider/inventory.txt`**

Overwrite the contents:

```bash
cat > provider/inventory.txt <<'EOF'
{"tier": "small", "mbps": 2, "durationSeconds": 600, "slots": [{"pe": "pe1", "subinterface": "ethernet-1/2.0", "ce": "ce1", "agreementId": null, "expiresAt": null}]}
{"tier": "medium", "mbps": 5, "durationSeconds": 600, "slots": [{"pe": "pe1", "subinterface": "ethernet-1/3.0", "ce": "ce3", "agreementId": null, "expiresAt": null}]}
{"tier": "large", "mbps": 8, "durationSeconds": 600, "slots": [{"pe": "pe2", "subinterface": "ethernet-1/2.0", "ce": "ce2", "agreementId": null, "expiresAt": null}]}
EOF
```

- [ ] **Step 3: Rewrite `provider/catalog.py`**

```python
"""
Catalog and quote logic for the provider.

State is split:
- Tier metadata (mbps, price) lives in the in-memory CATALOG dict.
- Slot availability (which subinterface, leased or free) lives in
  inventory.txt via SlotPool.
- Quotes (agreementId → quote params) live in pending_quotes (in-memory).
"""
from __future__ import annotations

import secrets
import time
from pathlib import Path

from web3 import Web3

from shared.slot_pool import SlotPool

CATALOG: list[dict] = [
    {"packageId": "small",  "mbps": 2, "durationSeconds": 600, "priceWei": Web3.to_wei(0.01, "ether")},
    {"packageId": "medium", "mbps": 5, "durationSeconds": 600, "priceWei": Web3.to_wei(0.02, "ether")},
    {"packageId": "large",  "mbps": 8, "durationSeconds": 600, "priceWei": Web3.to_wei(0.08, "ether")},
]
CATALOG_BY_ID: dict[str, dict] = {p["packageId"]: p for p in CATALOG}

INVENTORY_FILE = Path(__file__).parent / "inventory.txt"
QUOTE_TTL = 60

pending_quotes: dict[int, dict] = {}

slot_pool = SlotPool(INVENTORY_FILE)


def get_catalog_with_availability() -> list[dict]:
    avail_by_tier = {t["tier"]: t["availableSlots"] for t in slot_pool.tiers()}
    return [
        {**pkg, "availableSlots": avail_by_tier.get(pkg["packageId"], 0)}
        for pkg in CATALOG
    ]


def cleanup_quotes() -> None:
    now = time.time()
    expired = [k for k, v in pending_quotes.items() if v["expires"] < now]
    for k in expired:
        del pending_quotes[k]


def make_quote(package_id: str, consumer_address: str) -> dict | None:
    pkg = CATALOG_BY_ID.get(package_id)
    if pkg is None:
        return None
    if slot_pool.available_count(package_id) <= 0:
        return None
    agreement_id = int.from_bytes(secrets.token_bytes(16), "big")
    pending_quotes[agreement_id] = {
        "packageId": package_id,
        "consumerAddress": consumer_address,
        "expires": time.time() + QUOTE_TTL,
        "priceWei": pkg["priceWei"],
        "bandwidthMbps": pkg["mbps"],
        "durationSeconds": pkg["durationSeconds"],
    }
    return {
        "agreementId": agreement_id,
        "priceWei": pkg["priceWei"],
        "bandwidthMbps": pkg["mbps"],
        "durationSeconds": pkg["durationSeconds"],
    }
```

Note: this drops the legacy `decrement_inventory`/`rewind_inventory` functions. They're replaced by `slot_pool.reserve` and `slot_pool.release`. We'll wire those into `provider/app.py` in Task 9.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_catalog.py tests/test_slot_pool.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add provider/catalog.py provider/inventory.txt tests/test_catalog.py
git commit -m "$(cat <<'EOF'
refactor: rescale catalog and migrate inventory to SlotPool

Catalog values rescaled to 2/5/8 Mbps to fit the 1000 PPS cap of the
free SR Linux container image. Inventory schema replaced with explicit
(pe, subinterface, ce) per-slot binding via SlotPool.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 6: Provider MCP tool — `verify_credential_ownership`

**Files:**
- Modify: `provider/mcp_server.py`
- Create: `tests/test_provider_mcp.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_provider_mcp.py`:

```python
"""
In-memory MCP tests for the provider's tools.

These tests instantiate the provider's FastMCP server and call its tools
via Client(mcp) — no network involved. Tools that touch web3 are mocked
where the test doesn't need a live chain.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import Client


@pytest.fixture
def consumer_key() -> str:
    return "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"


@pytest.fixture
def consumer_address(consumer_key: str) -> str:
    return Account.from_key(consumer_key).address


@pytest.mark.asyncio
async def test_verify_credential_ownership_happy_path(consumer_key, consumer_address):
    nonce = str(int(time.time()))
    msg = encode_defunct(text=nonce)
    sig = Account.sign_message(msg, private_key=consumer_key).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = consumer_address
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345,           # agreementId
        5,               # bandwidthMbps
        600,             # durationSeconds
        int(time.time()) - 60,   # startTime (60s ago)
        "grpc://provider:8002",  # endpoint
    )
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        consumer_address, "0xprov", 5, 600, 0, 0, 7, 2,  # status=ACTIVE
    )

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce},
            )
            data = json.loads(result.content[0].text)
            assert data["ok"] is True
            assert data["signer"].lower() == consumer_address.lower()
            assert data["status"] == "ACTIVE"
            assert data["mbps"] == 5


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_wrong_signer(consumer_key, consumer_address):
    nonce = str(int(time.time()))
    msg = encode_defunct(text=nonce)
    sig = Account.sign_message(msg, private_key=consumer_key).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = "0xDifferentOwner000000000000000000000DEAD"
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()), "grpc://provider:8002")
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        consumer_address, "0xprov", 5, 600, 0, 0, 7, 2)

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "verify_credential_ownership",
                {"token_id": 7, "signature": sig, "nonce": nonce},
            )
            data = json.loads(result.content[0].text)
            assert data["ok"] is False


@pytest.mark.asyncio
async def test_verify_credential_ownership_rejects_stale_nonce(consumer_key):
    stale_nonce = str(int(time.time()) - 9999)  # well past 300s window
    msg = encode_defunct(text=stale_nonce)
    sig = Account.sign_message(msg, private_key=consumer_key).signature.hex()

    from provider.mcp_server import mcp
    async with Client(mcp) as client:
        result = await client.call_tool(
            "verify_credential_ownership",
            {"token_id": 7, "signature": sig, "nonce": stale_nonce},
        )
        data = json.loads(result.content[0].text)
        assert data["ok"] is False
        assert "nonce" in data["reason"].lower()
```

- [ ] **Step 2: Run test, expect import error / failure**

```bash
uv run pytest tests/test_provider_mcp.py::test_verify_credential_ownership_happy_path -v
```

Expected: ImportError on `provider.mcp_server.get_nft_contract` or AttributeError on tool.

- [ ] **Step 3: Implement the tool**

Modify `provider/mcp_server.py`. Add imports at the top:

```python
import json
import os
import time

from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from provider.catalog import get_catalog_with_availability, make_quote
from shared.contracts import get_escrow_contract, get_nft_contract

NONCE_WINDOW = 300  # seconds, matches deleted gateway

_RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
_w3 = Web3(Web3.HTTPProvider(_RPC_URL))

_STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}

mcp = FastMCP("bandwidth-provider")
```

(Keep the existing `get_catalog` and `request_quote` tools below.)

Append the new tool:

```python
@mcp.tool()
def verify_credential_ownership(token_id: int, signature: str, nonce: str) -> str:
    """
    Verify ownership of a bandwidth credential NFT.

    Checks (in order):
      1. nonce is within ±300 s of now
      2. ECDSA signature recovers to the address that owns tokenId on chain
      3. agreement linked to tokenId is ACTIVE

    Returns JSON:
      {ok: bool, signer, owner, agreement_id, mbps, duration_seconds,
       endpoint, seconds_remaining, status, reason?}
    """
    try:
        nonce_time = int(nonce)
    except ValueError:
        return json.dumps({"ok": False, "reason": "nonce must be a unix timestamp string"})
    if abs(time.time() - nonce_time) > NONCE_WINDOW:
        return json.dumps({"ok": False, "reason": "nonce expired or too far in future"})

    try:
        signer = Account.recover_message(encode_defunct(text=nonce), signature=signature)
    except Exception as e:
        return json.dumps({"ok": False, "reason": f"invalid signature: {e}"})

    nft = get_nft_contract(_w3)
    try:
        owner = nft.functions.ownerOf(token_id).call()
    except Exception:
        return json.dumps({"ok": False, "reason": f"token {token_id} does not exist"})
    if Web3.to_checksum_address(owner) != Web3.to_checksum_address(signer):
        return json.dumps({"ok": False, "reason": "signer does not own token", "signer": signer, "owner": owner})

    meta = nft.functions.getTokenMetadata(token_id).call()
    agreement_id, mbps, duration, start_time, endpoint = meta
    elapsed = int(time.time()) - int(start_time)
    seconds_remaining = max(0, int(duration) - elapsed)

    escrow = get_escrow_contract(_w3)
    agreement = escrow.functions.getAgreement(int(agreement_id)).call()
    status = _STATUS_NAMES.get(agreement[7], "UNKNOWN")

    return json.dumps({
        "ok": True,
        "signer": signer,
        "owner": owner,
        "agreement_id": int(agreement_id),
        "mbps": int(mbps),
        "duration_seconds": int(duration),
        "endpoint": endpoint,
        "seconds_remaining": seconds_remaining,
        "status": status,
    })
```

- [ ] **Step 4: Run all provider MCP tests**

```bash
uv run pytest tests/test_provider_mcp.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add provider/mcp_server.py tests/test_provider_mcp.py
git commit -m "$(cat <<'EOF'
feat(provider): add verify_credential_ownership MCP tool

Migrates the signature/nonce/ownerOf verification logic that lived in
the standalone gateway service into a provider MCP tool. Same semantics
(±300s nonce window, ECDSA recovery, on-chain ownerOf), now invokable
from the AgentExecutor via in-memory MCP.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 7: Provider MCP tool — `mint_credential`

**Files:**
- Modify: `provider/mcp_server.py`
- Modify: `tests/test_provider_mcp.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_provider_mcp.py`:

```python
@pytest.mark.asyncio
async def test_mint_credential_returns_token_id():
    fake_nft = MagicMock()
    # mint() returns a tx, then receipt with Transfer event in logs[].
    transfer_topic_hex = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    fake_receipt = {
        "status": 1,
        "logs": [
            {
                "topics": [
                    type("T", (), {"hex": lambda self: transfer_topic_hex})(),  # topic[0]
                    type("T", (), {"hex": lambda self: "0x0"})(),               # from
                    type("T", (), {"hex": lambda self: "0x1"})(),               # to
                    type("T", (), {"hex": lambda self: "0x000000000000000000000000000000000000000000000000000000000000002a"})(),  # tokenId=42
                ],
            },
        ],
    }
    fake_nft.functions.mint.return_value.build_transaction.return_value = {"from": "0xprov", "nonce": 0}

    fake_w3 = MagicMock()
    fake_w3.eth.get_transaction_count.return_value = 0
    fake_w3.eth.account.sign_transaction.return_value = MagicMock(raw_transaction=b"\x00")
    fake_w3.eth.send_raw_transaction.return_value = b"\x00"
    fake_w3.eth.wait_for_transaction_receipt.return_value = fake_receipt

    with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
         patch("provider.mcp_server._w3", fake_w3), \
         patch("provider.mcp_server._provider_account",
               MagicMock(address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8")), \
         patch("provider.mcp_server._provider_key", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mint_credential",
                {
                    "agreement_id": 12345,
                    "consumer_address": "0xConsumer000000000000000000000000000DEAD",
                    "pe": "pe1",
                    "subinterface": "ethernet-1/3.0",
                    "ce": "ce3",
                    "mbps": 5,
                    "duration_seconds": 600,
                },
            )
            data = json.loads(result.content[0].text)
            assert data["tokenId"] == 42
            assert data["endpoint"] == "grpc://provider:8002"  # placeholder, see implementation
```

- [ ] **Step 2: Run test, expect failure**

```bash
uv run pytest tests/test_provider_mcp.py::test_mint_credential_returns_token_id -v
```

- [ ] **Step 3: Implement the tool**

Add to `provider/mcp_server.py` (above the existing tools or in logical order):

```python
_provider_key = os.environ.get("PROVIDER_PRIVATE_KEY")
_provider_account = Account.from_key(_provider_key) if _provider_key else None

_TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()


def _send_provider_tx(func, value: int = 0):
    if _provider_account is None:
        raise RuntimeError("PROVIDER_PRIVATE_KEY not set")
    tx = func.build_transaction({
        "from": _provider_account.address,
        "nonce": _w3.eth.get_transaction_count(_provider_account.address, "pending"),
        "value": value,
    })
    signed = _w3.eth.account.sign_transaction(tx, _provider_key)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    h = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(h, timeout=60)
    if receipt["status"] != 1:
        raise RuntimeError(f"tx reverted: {h.hex() if hasattr(h, 'hex') else h}")
    return h, receipt


def _extract_token_id(receipt) -> int:
    for entry in receipt["logs"]:
        if entry["topics"][0].hex() == _TRANSFER_TOPIC:
            return int(entry["topics"][3].hex(), 16)
    raise RuntimeError("Transfer event not found in mint receipt")


@mcp.tool()
def mint_credential(
    agreement_id: int,
    consumer_address: str,
    pe: str,
    subinterface: str,
    ce: str,
    mbps: int,
    duration_seconds: int,
) -> str:
    """
    Mint a BandwidthNFT credential bound to (agreement_id, mbps, duration).

    The endpoint embeds (pe, subinterface) so the credential is bound to a
    specific resource slot.

    Returns JSON: {tokenId, txHash, endpoint}.
    """
    nft = get_nft_contract(_w3)
    endpoint = f"clab://{pe}/{subinterface}"
    h, receipt = _send_provider_tx(
        nft.functions.mint(
            _provider_account.address,
            int(agreement_id),
            int(mbps),
            int(duration_seconds),
            endpoint,
        )
    )
    token_id = _extract_token_id(receipt)
    tx_hash = h.hex() if hasattr(h, "hex") else str(h)
    return json.dumps({
        "tokenId": token_id,
        "txHash": tx_hash,
        "endpoint": endpoint,
    })
```

Note the test's expected `endpoint == "grpc://provider:8002"` — update the test to match the actual `f"clab://{pe}/{subinterface}"` format. Edit `tests/test_provider_mcp.py` line containing `assert data["endpoint"] == "grpc://provider:8002"` to:

```python
            assert data["endpoint"] == "clab://pe1/ethernet-1/3.0"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_provider_mcp.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add provider/mcp_server.py tests/test_provider_mcp.py
git commit -m "$(cat <<'EOF'
feat(provider): add mint_credential MCP tool

Mints a BandwidthNFT bound to (agreement_id, mbps, duration). Endpoint
field encodes the (pe, subinterface) slot so the credential is tied to
a specific physical resource. Replaces the inline mint logic in the
event listener (rewired in a later task).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 8: Provider MCP tool — `complete_swap`

**Files:**
- Modify: `provider/mcp_server.py`
- Modify: `tests/test_provider_mcp.py`

- [ ] **Step 1: Failing test**

Append to `tests/test_provider_mcp.py`:

```python
@pytest.mark.asyncio
async def test_complete_swap_calls_approve_then_deposit():
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
         patch("provider.mcp_server._w3", fake_w3), \
         patch("provider.mcp_server._provider_account",
               MagicMock(address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8")), \
         patch("provider.mcp_server._provider_key", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"):
        from provider.mcp_server import mcp
        async with Client(mcp) as client:
            result = await client.call_tool(
                "complete_swap",
                {"agreement_id": 12345, "token_id": 42},
            )
            data = json.loads(result.content[0].text)
            assert data["status"] == "ok"
            assert "approveTx" in data
            assert "depositTx" in data
            fake_nft.functions.approve.assert_called_once_with("0xESCROW", 42)
            fake_escrow.functions.deposit.assert_called_once_with(12345, 42)
```

- [ ] **Step 2: Run, expect failure**

```bash
uv run pytest tests/test_provider_mcp.py::test_complete_swap_calls_approve_then_deposit -v
```

- [ ] **Step 3: Implement**

Add to `provider/mcp_server.py`:

```python
@mcp.tool()
def complete_swap(agreement_id: int, token_id: int) -> str:
    """
    Approve the escrow on the freshly minted NFT, then call escrow.deposit
    to atomically swap NFT→consumer and ETH→provider.

    Returns JSON: {status, approveTx, depositTx}.
    """
    nft = get_nft_contract(_w3)
    escrow = get_escrow_contract(_w3)

    h_approve, _ = _send_provider_tx(nft.functions.approve(escrow.address, int(token_id)))
    h_deposit, _ = _send_provider_tx(escrow.functions.deposit(int(agreement_id), int(token_id)))

    return json.dumps({
        "status": "ok",
        "approveTx": h_approve.hex() if hasattr(h_approve, "hex") else str(h_approve),
        "depositTx": h_deposit.hex() if hasattr(h_deposit, "hex") else str(h_deposit),
    })
```

- [ ] **Step 4: Test**

```bash
uv run pytest tests/test_provider_mcp.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add provider/mcp_server.py tests/test_provider_mcp.py
git commit -m "$(cat <<'EOF'
feat(provider): add complete_swap MCP tool

Wraps approve + deposit into one MCP call. The atomic swap inside
escrow.deposit is unchanged — this just exposes the provider-side
trigger as an in-memory MCP tool the AgentExecutor can call.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 9: Refactor provider `_handle_agreement` to use MCP tools

**Files:**
- Modify: `provider/app.py`

- [ ] **Step 1: Read the current `_handle_agreement` for reference**

```bash
grep -n "_handle_agreement\|_extract_token_id\|_send_tx\|decrement_inventory\|rewind_inventory" provider/app.py
```

You should see the current implementation around lines 76-161.

- [ ] **Step 2: Replace `_handle_agreement` with MCP-driven version**

Open `provider/app.py` and replace the `_handle_agreement` function (and remove the now-unused `_send_tx` helper and `_extract_token_id` helper inside `provider/app.py` — they live in `mcp_server.py` now).

Add this import near the top of `provider/app.py`:

```python
import json as _json
from fastmcp import Client as _MCPClient

from provider.catalog import (
    CATALOG_BY_ID,
    cleanup_quotes,
    get_catalog_with_availability,
    make_quote,
    pending_quotes,
    slot_pool,
)
from provider.mcp_server import mcp
```

Remove (or comment) the old `decrement_inventory`/`rewind_inventory` imports.

Replace `_handle_agreement` body:

```python
async def _handle_agreement(escrow, agreement_id: int, args: dict) -> None:
    cleanup_quotes()
    quote = pending_quotes.get(agreement_id)
    if not quote or time.time() > quote["expires"]:
        log.warning(f"No valid quote for agreementId={agreement_id}, skipping.")
        return

    pkg = CATALOG_BY_ID.get(quote["packageId"])
    if not pkg:
        log.error(f"Unknown packageId in quote for agreementId={agreement_id}")
        return

    ag = escrow.functions.getAgreement(agreement_id).call()
    if ag[2] != pkg["mbps"] or ag[3] != pkg["durationSeconds"] or ag[4] != pkg["priceWei"]:
        log.error(f"Param mismatch for agreementId={agreement_id}")
        return

    slot = slot_pool.reserve(pkg["packageId"], agreement_id, pkg["durationSeconds"])
    if slot is None:
        log.error(f"No slots available for tier={pkg['packageId']}, agreementId={agreement_id}")
        return

    try:
        async with _MCPClient(mcp) as client:
            mint_result = await client.call_tool(
                "mint_credential",
                {
                    "agreement_id": agreement_id,
                    "consumer_address": args["consumer"],
                    "pe": slot.pe,
                    "subinterface": slot.subinterface,
                    "ce": slot.ce,
                    "mbps": pkg["mbps"],
                    "duration_seconds": pkg["durationSeconds"],
                },
            )
            mint_data = _json.loads(mint_result.content[0].text)
            token_id = int(mint_data["tokenId"])
            log.info(f"Minted tokenId={token_id} on slot {slot} for agreementId={agreement_id}")

            await client.call_tool(
                "complete_swap",
                {"agreement_id": agreement_id, "token_id": token_id},
            )
            log.info(f"Swap complete agreementId={agreement_id} tokenId={token_id}")

        del pending_quotes[agreement_id]

    except Exception as e:
        log.error(f"Error in mint/swap flow agreementId={agreement_id}: {e}")
        slot_pool.release(agreement_id)
```

Update the caller `_event_listener` to drop the `nft` argument (no longer needed):

```python
async def _event_listener() -> None:
    escrow = get_escrow_contract(w3)
    log.info("Event listener started, watching AgreementRequested...")
    last_block = w3.eth.block_number

    while True:
        await asyncio.sleep(2)
        try:
            current = w3.eth.block_number
            if current <= last_block:
                continue
            events = escrow.events.AgreementRequested.get_logs(
                fromBlock=last_block + 1, toBlock=current
            )
            last_block = current
            for evt in events:
                args = evt["args"]
                asyncio.create_task(
                    _handle_agreement(escrow, args["agreementId"], args)
                )
        except Exception as e:
            log.error(f"Event listener error: {e}")
```

Remove the now-orphaned `_send_tx`, `_extract_token_id`, and `nft = get_nft_contract(w3)` line at the top of `_event_listener`.

- [ ] **Step 3: Run existing tests + smoke-check imports**

```bash
uv run pytest tests/ -v
uv run python -c "import provider.app; print('imports ok')"
```

Expected: all tests pass, imports clean.

- [ ] **Step 4: Live smoke test (Anvil + provider)**

```bash
make down-clean
make up
sleep 10
docker compose logs provider-agent | tail -40
```

Expected: provider logs `Event listener started, watching AgreementRequested...` with no Python errors.

- [ ] **Step 5: Commit**

```bash
git add provider/app.py
git commit -m "$(cat <<'EOF'
refactor(provider): event listener uses in-memory MCP for mint+swap

_handle_agreement now reserves a slot from SlotPool, calls mint_credential
and complete_swap via Client(mcp) (in-memory FastMCP). One code path for
autonomous and A2A-driven mint/swap. Removes duplicated _send_tx and
_extract_token_id helpers — they live in mcp_server.py now.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 3 — Provider A2A server

### Task 10: A2A message Pydantic models

**Files:**
- Create: `shared/a2a_messages.py`

- [ ] **Step 1: Implement (no failing test — these are passive schemas, validated by usage in subsequent tasks)**

```python
"""
Pydantic models for the structured `data` parts agents exchange over A2A.

The A2A `Message.parts[*].data` field is an arbitrary JSON object. We
constrain its shape with these models so executors can parse safely.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


# ── Requests (consumer → provider) ─────────────────────────────────────────
class BrowseCatalogRequest(BaseModel):
    action: Literal["get_catalog"] = "get_catalog"


class QuoteRequest(BaseModel):
    action: Literal["request_quote"] = "request_quote"
    package_id: str
    consumer_address: str


class ActivateRequest(BaseModel):
    action: Literal["activate"] = "activate"
    token_id: int
    nonce: str          # unix timestamp string
    signature: str      # 0x-prefixed hex


# ── Responses (provider → consumer) ────────────────────────────────────────
class CatalogEntry(BaseModel):
    packageId: str
    mbps: int
    durationSeconds: int
    priceWei: int
    availableSlots: int


class CatalogResponse(BaseModel):
    catalog: list[CatalogEntry]


class QuoteResponse(BaseModel):
    agreementId: str    # str to preserve uint256 across JSON
    priceWei: int
    bandwidthMbps: int
    durationSeconds: int


class ActivateResponse(BaseModel):
    status: Literal["active", "denied"]
    bandwidth_mbps: Optional[int] = None
    seconds_remaining: Optional[int] = None
    endpoint: Optional[str] = None
    reason: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
```

- [ ] **Step 2: Smoke import**

```bash
uv run python -c "from shared.a2a_messages import BrowseCatalogRequest, QuoteRequest, ActivateRequest, CatalogResponse, QuoteResponse, ActivateResponse, ErrorResponse; print('ok')"
```

- [ ] **Step 3: Commit**

```bash
git add shared/a2a_messages.py
git commit -m "$(cat <<'EOF'
feat: add Pydantic schemas for A2A message data parts

Constrains the structured 'data' parts the agents exchange so the
provider's AgentExecutor can deserialize and dispatch safely.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 11: Provider AgentCard

**Files:**
- Create: `provider/agent_card.py`

- [ ] **Step 1: Implement**

```python
"""
Builds the a2a.types.AgentCard for the bandwidth provider agent.
"""
from __future__ import annotations

import os

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

PROVIDER_BASE_URL = os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002")


def build_provider_agent_card() -> AgentCard:
    return AgentCard(
        name="Bandwidth Provider Agent",
        description=(
            "Sells time-bound bandwidth packages via atomic on-chain escrow + "
            "ERC-721 credential. Activates SDN policy (gNMI policer + tc rate-limit) "
            "on credential presentation."
        ),
        version="2.0.0",
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=f"{PROVIDER_BASE_URL}/v1/message/send",
            ),
        ],
        skills=[
            AgentSkill(
                id="get_catalog",
                name="Get Catalog",
                description="Returns available bandwidth tiers with pricing and availability.",
                tags=["bandwidth", "catalog"],
                examples=['{"action": "get_catalog"}'],
            ),
            AgentSkill(
                id="request_quote",
                name="Request Quote",
                description=(
                    "Issues an agreementId-bound price quote for a chosen tier. "
                    "Required input: package_id (small|medium|large), consumer_address."
                ),
                tags=["bandwidth", "quote", "escrow"],
                examples=[
                    '{"action": "request_quote", "package_id": "medium", "consumer_address": "0x..."}'
                ],
            ),
            AgentSkill(
                id="activate",
                name="Activate Service",
                description=(
                    "Verifies NFT credential ownership (signature over nonce + on-chain "
                    "ownerOf check) and triggers SDN allocation for the bound resource slot."
                ),
                tags=["bandwidth", "activation", "sdn"],
                examples=[
                    '{"action": "activate", "token_id": 7, "nonce": "1730000000", "signature": "0x..."}'
                ],
            ),
        ],
    )
```

- [ ] **Step 2: Smoke import**

```bash
uv run python -c "from provider.agent_card import build_provider_agent_card; c = build_provider_agent_card(); print(c.name, len(c.skills))"
```

Expected: `Bandwidth Provider Agent 3`. If any `AgentCard`/`AgentSkill`/`AgentCapabilities`/`AgentInterface` import fails, the installed `a2a-sdk` version's API has shifted. Inspect:

```bash
uv run python -c "import a2a.types; print(dir(a2a.types))"
```

…and adjust the imports + arguments to match what's exported.

- [ ] **Step 3: Commit**

```bash
git add provider/agent_card.py
git commit -m "$(cat <<'EOF'
feat(provider): add AgentCard builder

Replaces the static AGENT_CARD dict with an a2a.types.AgentCard
instance with proper skills, capabilities, and interface declaration.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 12: Provider AgentExecutor (catalog + quote first; activate later)

**Files:**
- Create: `provider/agent_executor.py`

- [ ] **Step 1: Implement**

```python
"""
BandwidthProviderExecutor — bridges A2A messages to the provider's MCP tools.

Inbound: A2A Message with a single `data` Part containing {"action": ...}.
Routes:
  - "get_catalog"      → MCP get_catalog
  - "request_quote"    → MCP request_quote
  - "activate"         → MCP verify_credential_ownership + allocate_bandwidth

Outbound: TaskArtifactUpdateEvent carrying a `data` Part with the JSON response,
followed by a TaskStatusUpdateEvent with TASK_STATE_COMPLETED.
"""
from __future__ import annotations

import json
import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    Artifact,
    Part,
    Task,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from fastmcp import Client as MCPClient

from provider.mcp_server import mcp
from shared.a2a_messages import (
    ActivateRequest,
    BrowseCatalogRequest,
    ErrorResponse,
    QuoteRequest,
)

log = logging.getLogger("provider.executor")


class BandwidthProviderExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        data = self._extract_data_part(context)
        if data is None:
            await self._emit_error(event_queue, context.task_id,
                                    "expected message with a single data part")
            return

        action = data.get("action")
        try:
            if action == "get_catalog":
                BrowseCatalogRequest.model_validate(data)
                await self._handle_catalog(event_queue, context.task_id)
            elif action == "request_quote":
                req = QuoteRequest.model_validate(data)
                await self._handle_quote(event_queue, context.task_id, req)
            elif action == "activate":
                req = ActivateRequest.model_validate(data)
                await self._handle_activate(event_queue, context.task_id, req)
            else:
                await self._emit_error(event_queue, context.task_id,
                                        f"unknown action: {action!r}")
        except Exception as e:
            log.exception("Executor error")
            await self._emit_error(event_queue, context.task_id, str(e))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # Nothing async to cancel — ops are short-lived synchronous-ish chain calls.
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                status=TaskStatus(state=TaskState.TASK_STATE_CANCELED),
            )
        )

    # ── action handlers ───────────────────────────────────────────────────────
    async def _handle_catalog(self, queue: EventQueue, task_id: str) -> None:
        async with MCPClient(mcp) as client:
            result = await client.call_tool("get_catalog", {})
            payload = json.loads(result.content[0].text)
        await self._emit_data(queue, task_id, {"catalog": payload})

    async def _handle_quote(self, queue: EventQueue, task_id: str, req: QuoteRequest) -> None:
        async with MCPClient(mcp) as client:
            result = await client.call_tool("request_quote", {
                "package_id": req.package_id,
                "consumer_address": req.consumer_address,
            })
            data = json.loads(result.content[0].text)
        if "error" in data:
            await self._emit_data(queue, task_id, {"error": data["error"]})
            return
        # Serialize agreementId as string to preserve precision over JSON-RPC.
        await self._emit_data(queue, task_id, {
            "agreementId": str(data["agreementId"]),
            "priceWei": data["priceWei"],
            "bandwidthMbps": data["bandwidthMbps"],
            "durationSeconds": data["durationSeconds"],
        })

    async def _handle_activate(self, queue: EventQueue, task_id: str, req: ActivateRequest) -> None:
        # Stub for Task 13. Returns 'denied' until activation is wired up.
        await self._emit_data(queue, task_id, {"status": "denied",
                                                "reason": "activation not yet implemented"})

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_data_part(context: RequestContext) -> dict | None:
        msg = context.message
        if msg is None or not msg.parts:
            return None
        for part in msg.parts:
            if getattr(part, "data", None) is not None:
                return dict(part.data)
        return None

    async def _emit_data(self, queue: EventQueue, task_id: str, data: dict) -> None:
        await queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                artifact=Artifact(
                    artifact_id="result",
                    parts=[Part(data=data, media_type="application/json")],
                ),
            )
        )
        await queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            )
        )

    async def _emit_error(self, queue: EventQueue, task_id: str, message: str) -> None:
        await queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                artifact=Artifact(
                    artifact_id="error",
                    parts=[Part(data=ErrorResponse(error=message).model_dump(),
                                 media_type="application/json")],
                ),
            )
        )
        await queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                status=TaskStatus(state=TaskState.TASK_STATE_FAILED),
            )
        )
```

- [ ] **Step 2: Smoke import**

```bash
uv run python -c "from provider.agent_executor import BandwidthProviderExecutor; print('ok')"
```

If imports fail because the a2a-sdk version exports different names (e.g., `RequestContext` lives at `a2a.server.request` not `a2a.server.agent_execution`):

```bash
uv run python -c "import a2a; help(a2a)"
uv run python -c "from a2a.server.agent_execution import AgentExecutor; help(AgentExecutor)"
```

Adjust imports to match. Document the actual import path in a comment at the top of the file.

- [ ] **Step 3: Commit**

```bash
git add provider/agent_executor.py
git commit -m "$(cat <<'EOF'
feat(provider): add BandwidthProviderExecutor (catalog + quote)

Bridges inbound A2A messages to provider MCP tools. Activate handler
is stubbed and returns 'denied' until Task 13 wires it up.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 13: Mount A2A routes on provider FastAPI

**Files:**
- Modify: `provider/app.py`

- [ ] **Step 1: Add A2A imports and route mounting**

In `provider/app.py`, add imports near the top:

```python
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    create_agent_card_routes,
    create_jsonrpc_routes,
)
from a2a.server.tasks import InMemoryTaskStore

from provider.agent_card import build_provider_agent_card
from provider.agent_executor import BandwidthProviderExecutor
```

Replace the static `AGENT_CARD` dict with a card builder call. Replace the `/.well-known/agent.json` handler:

```python
_provider_agent_card = build_provider_agent_card()


@app.get("/.well-known/agent-card.json")
def agent_card_canonical() -> dict:
    return _provider_agent_card.model_dump(mode="json", by_alias=True)


@app.get("/.well-known/agent.json")
def agent_card_legacy() -> dict:
    return _provider_agent_card.model_dump(mode="json", by_alias=True)
```

After all the FastAPI route definitions but before `app.mount("/", _mcp_http_app)`, add:

```python
_a2a_handler = DefaultRequestHandler(
    agent_executor=BandwidthProviderExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=_provider_agent_card,
)
for route in create_agent_card_routes(_provider_agent_card):
    app.router.routes.append(route)
for route in create_jsonrpc_routes(_a2a_handler, "/"):
    app.router.routes.append(route)
```

- [ ] **Step 2: Smoke test the running provider**

```bash
make down-clean && make up
sleep 15
curl -sf http://localhost:8002/.well-known/agent-card.json | python3 -m json.tool | head -20
```

Expected: JSON with `name`, `skills` (3 entries), `supported_interfaces`. If the curl returns 404 or HTML, the route registration order is wrong — check that A2A routes are appended **before** `app.mount("/", _mcp_http_app)` (which catches all paths).

- [ ] **Step 3: Test JSON-RPC roundtrip with curl**

```bash
curl -sf -X POST http://localhost:8002/v1/message/send \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "messageId": "m1",
        "role": "ROLE_USER",
        "parts": [{"data": {"action": "get_catalog"}}]
      }
    }
  }' | python3 -m json.tool
```

Expected: a JSON-RPC response containing a Task with an Artifact whose `parts[0].data.catalog` lists three tiers.

If this fails, capture the exact error and revisit the route mounting and the executor's `_emit_data` call. Most common failure: `jsonrpc` route path is `/v1/message/send` vs `/` (depends on what `create_jsonrpc_routes(handler, prefix)` does in your installed version). Adjust `prefix` accordingly.

- [ ] **Step 4: Commit**

```bash
git add provider/app.py
git commit -m "$(cat <<'EOF'
feat(provider): mount a2a-sdk routes on FastAPI

Provider now serves /.well-known/agent-card.json (canonical) and
/.well-known/agent.json (alias) plus the JSON-RPC and REST routes
generated by create_jsonrpc_routes / create_agent_card_routes.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 14: A2A executor unit tests (catalog + quote)

**Files:**
- Create: `tests/test_agent_executor.py`

- [ ] **Step 1: Write tests**

```python
"""
Unit tests for BandwidthProviderExecutor.

Drives the executor directly with a fake EventQueue, no Starlette involved.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from provider.agent_executor import BandwidthProviderExecutor


class FakeQueue:
    def __init__(self):
        self.events = []

    async def enqueue_event(self, event):
        self.events.append(event)


def _make_context(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.parts = [MagicMock(data=data)]
    ctx = MagicMock()
    ctx.message = msg
    ctx.task_id = "task-1"
    return ctx


@pytest.mark.asyncio
async def test_executor_returns_catalog():
    ex = BandwidthProviderExecutor()
    queue = FakeQueue()
    ctx = _make_context({"action": "get_catalog"})

    await ex.execute(ctx, queue)

    # First event: artifact with catalog. Second: status COMPLETED.
    assert len(queue.events) == 2
    artifact_event = queue.events[0]
    payload = artifact_event.artifact.parts[0].data
    assert "catalog" in payload
    assert len(payload["catalog"]) == 3


@pytest.mark.asyncio
async def test_executor_unknown_action_emits_error():
    ex = BandwidthProviderExecutor()
    queue = FakeQueue()
    ctx = _make_context({"action": "no_such_action"})

    await ex.execute(ctx, queue)

    assert len(queue.events) == 2
    err_event = queue.events[0]
    assert "error" in err_event.artifact.parts[0].data
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_agent_executor.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_agent_executor.py
git commit -m "$(cat <<'EOF'
test: unit tests for BandwidthProviderExecutor (catalog + error)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 4 — Drop gateway, fold activation into A2A

### Task 15: Wire `activate` handler in executor

**Files:**
- Modify: `provider/agent_executor.py`
- Modify: `provider/mcp_server.py` (add stubs for allocate/revoke/verify_bandwidth)

- [ ] **Step 1: Add `allocate_bandwidth` / `revoke_bandwidth` / `verify_bandwidth` MCP stubs**

Add to `provider/mcp_server.py`:

```python
import json as _json_local  # avoid shadowing if 'json' is locally rebound

SDN_MOCK = os.environ.get("SDN_MOCK", "true").lower() == "true"

try:
    from srl_bandwidth.bandwidth import (
        allocate_bandwidth as _srl_allocate,
        revoke_bandwidth as _srl_revoke,
        verify_bandwidth as _srl_verify,
    )
    from srl_bandwidth.models import ServiceRequest as _SrlServiceRequest
    _SRL_AVAILABLE = True
except ImportError:
    _SRL_AVAILABLE = False


@mcp.tool()
def allocate_bandwidth(customer_id: str, pe: str, subinterface: str, mbps: float) -> str:
    """
    Push gNMI policer to PE and apply tc tbf on connected CE.

    Honors SDN_MOCK=true (default in CI/dev) — returns a fake-success result
    without touching ContainerLab.

    Returns JSON AllocationResult.
    """
    if SDN_MOCK or not _SRL_AVAILABLE:
        return json.dumps({
            "success": True, "customer_id": customer_id, "pe": pe,
            "subinterface": subinterface, "mbps": mbps,
            "gnmi_pushed": False, "tc_applied": False,
            "message": "mocked",
        })
    import dataclasses as _dc
    req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                             subinterface=subinterface, mbps=mbps)
    return json.dumps(_dc.asdict(_srl_allocate(req)))


@mcp.tool()
def revoke_bandwidth(customer_id: str, pe: str, subinterface: str) -> str:
    """Reverse of allocate_bandwidth."""
    if SDN_MOCK or not _SRL_AVAILABLE:
        return json.dumps({"status": "revoked", "customer_id": customer_id,
                           "pe": pe, "subinterface": subinterface, "mocked": True})
    req = _SrlServiceRequest(customer_id=customer_id, pe=pe,
                             subinterface=subinterface, mbps=0.0)
    _srl_revoke(req)
    return json.dumps({"status": "revoked", "customer_id": customer_id,
                       "pe": pe, "subinterface": subinterface})


@mcp.tool()
def verify_bandwidth(src_ce: str, dst_ce: str,
                     expected_mbps: float | None = None,
                     tolerance: float = 0.2) -> str:
    """iperf3 UDP probe from src_ce to dst_ce."""
    if SDN_MOCK or not _SRL_AVAILABLE:
        return json.dumps({
            "passed": True, "measured_mbps": expected_mbps or 0.0,
            "expected_mbps": expected_mbps, "tolerance": tolerance,
            "message": "mocked",
        })
    import dataclasses as _dc
    return json.dumps(_dc.asdict(_srl_verify(src_ce, dst_ce, expected_mbps, tolerance)))
```

- [ ] **Step 2: Replace the `_handle_activate` stub in `provider/agent_executor.py`**

Add to imports:

```python
from provider.catalog import slot_pool
```

Replace `_handle_activate`:

```python
    async def _handle_activate(self, queue: EventQueue, task_id: str, req: ActivateRequest) -> None:
        async with MCPClient(mcp) as client:
            verify_res = await client.call_tool("verify_credential_ownership", {
                "token_id": req.token_id,
                "signature": req.signature,
                "nonce": req.nonce,
            })
            verify = json.loads(verify_res.content[0].text)
            if not verify.get("ok"):
                await self._emit_data(queue, task_id, {
                    "status": "denied",
                    "reason": verify.get("reason", "verification failed"),
                })
                return
            if verify.get("status") != "ACTIVE":
                await self._emit_data(queue, task_id, {
                    "status": "denied",
                    "reason": f"agreement status is {verify.get('status')}",
                })
                return

            # Look up the slot bound to this agreement.
            slot = slot_pool.lookup(verify["agreement_id"])
            if slot is None:
                await self._emit_data(queue, task_id, {
                    "status": "denied",
                    "reason": "no slot bound to this agreement",
                })
                return

            alloc_res = await client.call_tool("allocate_bandwidth", {
                "customer_id": verify["signer"],
                "pe": slot.pe,
                "subinterface": slot.subinterface,
                "mbps": float(verify["mbps"]),
            })
            alloc = json.loads(alloc_res.content[0].text)
            if not alloc.get("success"):
                await self._emit_data(queue, task_id, {
                    "status": "denied",
                    "reason": f"allocation failed: {alloc.get('message')}",
                })
                return

            await self._emit_data(queue, task_id, {
                "status": "active",
                "bandwidth_mbps": verify["mbps"],
                "seconds_remaining": verify["seconds_remaining"],
                "endpoint": verify["endpoint"],
            })
```

- [ ] **Step 3: Add an executor test for activate happy-path with SDN_MOCK**

Append to `tests/test_agent_executor.py`:

```python
import os
import time
from eth_account import Account
from eth_account.messages import encode_defunct
from unittest.mock import patch


@pytest.mark.asyncio
async def test_executor_activate_happy_path(monkeypatch):
    monkeypatch.setenv("SDN_MOCK", "true")
    consumer_key = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
    consumer_addr = Account.from_key(consumer_key).address
    nonce = str(int(time.time()))
    sig = Account.sign_message(encode_defunct(text=nonce), private_key=consumer_key).signature.hex()

    fake_nft = MagicMock()
    fake_nft.functions.ownerOf.return_value.call.return_value = consumer_addr
    fake_nft.functions.getTokenMetadata.return_value.call.return_value = (
        12345, 5, 600, int(time.time()) - 60, "clab://pe1/ethernet-1/3.0",
    )
    fake_escrow = MagicMock()
    fake_escrow.functions.getAgreement.return_value.call.return_value = (
        consumer_addr, "0xprov", 5, 600, 0, 0, 7, 2,
    )

    # Pre-populate slot_pool with the agreement binding so lookup() finds it.
    from provider.catalog import slot_pool
    slot_pool.reserve("medium", agreement_id=12345, duration_seconds=600)

    try:
        with patch("provider.mcp_server.get_nft_contract", return_value=fake_nft), \
             patch("provider.mcp_server.get_escrow_contract", return_value=fake_escrow):
            ex = BandwidthProviderExecutor()
            queue = FakeQueue()
            ctx = _make_context({
                "action": "activate",
                "token_id": 7,
                "nonce": nonce,
                "signature": sig,
            })
            await ex.execute(ctx, queue)

            payload = queue.events[0].artifact.parts[0].data
            assert payload["status"] == "active"
            assert payload["bandwidth_mbps"] == 5
    finally:
        slot_pool.release(12345)
```

- [ ] **Step 4: Run all tests**

```bash
SDN_MOCK=true uv run pytest tests/ -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add provider/mcp_server.py provider/agent_executor.py tests/test_agent_executor.py
git commit -m "$(cat <<'EOF'
feat(provider): wire activate flow end-to-end via A2A

A2A 'activate' message → verify_credential_ownership →
allocate_bandwidth (SDN_MOCK respected). Adds allocate/revoke/verify
bandwidth MCP tools that delegate to srl_bandwidth when SDN_MOCK=false.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 16: Delete `provider/gateway.py` and drop `:8003`

**Files:**
- Delete: `provider/gateway.py`
- Modify: `Dockerfile.provider`
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Delete gateway**

```bash
git rm provider/gateway.py
```

- [ ] **Step 2: Drop gateway from `Dockerfile.provider`**

Replace the CMD at the end of `Dockerfile.provider`:

```dockerfile
CMD ["uvicorn", "provider.app:app", "--host", "0.0.0.0", "--port", "8002"]
```

- [ ] **Step 3: Drop `:8003` port from `docker-compose.yml`**

Edit the `provider-agent` service block:

```yaml
provider-agent:
  build:
    context: .
    dockerfile: Dockerfile.provider
  depends_on:
    deployer:
      condition: service_completed_successfully
  ports:
    - "8002:8002"
  environment:
    - RPC_URL=http://anvil:8545
    - PROVIDER_PRIVATE_KEY=${PROVIDER_PRIVATE_KEY}
    - SDN_MOCK=${SDN_MOCK:-true}
  volumes:
    - ./contracts/deployments:/app/contracts/deployments:ro
    - ./provider/inventory.txt:/app/provider/inventory.txt
```

Edit the `consumer-agent` service block: remove `GATEWAY_BASE_URL`. The `PROVIDER_MCP_URL` env can also be removed (cross-network MCP is gone after Phase 5). Replace `PROVIDER_BASE_URL` semantics (which used to point at REST + MCP) — keep it pointing at the A2A endpoint.

```yaml
consumer-agent:
  ...
  environment:
    - RPC_URL=http://anvil:8545
    - CONSUMER_PRIVATE_KEY=${CONSUMER_PRIVATE_KEY}
    - PROVIDER_A2A_URLS=http://provider-agent:8002
    - OLLAMA_MODEL=${OLLAMA_MODEL:-qwen3:4b}
    - OLLAMA_HOST=http://ollama:11434
```

(Note: `PROVIDER_A2A_URLS` is the comma-separated multi-provider list. Single value is fine for now.)

- [ ] **Step 4: Update `.env.example`**

Replace the gateway/MCP env vars:

```bash
# Service URLs (change to container names when using Docker)
PROVIDER_A2A_URLS=http://localhost:8002
# (deleted: GATEWAY_BASE_URL, PROVIDER_MCP_URL)

# SDN enforcement: set to false when ContainerLab is deployed
SDN_MOCK=true
```

- [ ] **Step 5: Smoke test full stack**

```bash
make down-clean && make up
sleep 15
curl -sf http://localhost:8002/.well-known/agent-card.json | jq .name
docker compose ps
```

Expected: provider card name printed; no `:8003` port mapped.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
refactor: delete provider/gateway.py and drop :8003

Gateway role moved into the provider's AgentExecutor + verify_credential_
ownership MCP tool. Compose, Dockerfile, .env.example updated. Single
provider port (8002) now serves A2A + agent card + (legacy MCP at /mcp
for transition until Phase 5).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 5 — Consumer intra-agent MCP + A2A client

### Task 17: A2A client wrapper

**Files:**
- Create: `consumer/a2a_client.py`

- [ ] **Step 1: Implement**

```python
"""
Thin wrapper around a2a-sdk's client primitives. Used by consumer MCP
tools that need to talk to a remote provider over A2A.

Design choice: open a fresh client per call. The cost is one resolve +
one HTTP round trip; we do not optimize for high call rates.
"""
from __future__ import annotations

import json
from typing import Any

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.types import Message, Part, Role, SendMessageRequest


async def send_provider_action(provider_url: str, payload: dict) -> dict:
    """
    Send a single A2A message to the provider with `parts[0].data = payload`,
    return the first artifact's data part as a dict.
    """
    async with httpx.AsyncClient(timeout=60.0) as http:
        resolver = A2ACardResolver(httpx_client=http, base_url=provider_url)
        card = await resolver.get_agent_card()
        client = await create_client(agent=card, client_config=ClientConfig(streaming=False))

        msg = Message(
            messageId=_short_id(),
            role=Role.ROLE_USER,
            parts=[Part(data=payload, media_type="application/json")],
        )
        request = SendMessageRequest(message=msg)

        async for chunk in client.send_message(request):
            # The first chunk that carries an artifact is our answer.
            artifacts = getattr(chunk, "artifacts", None)
            if artifacts:
                for art in artifacts:
                    for part in art.parts:
                        data = getattr(part, "data", None)
                        if data is not None:
                            return dict(data)
        raise RuntimeError("provider returned no artifacts")


def _short_id() -> str:
    import secrets
    return secrets.token_hex(8)
```

- [ ] **Step 2: Smoke import**

```bash
uv run python -c "from consumer.a2a_client import send_provider_action; print('ok')"
```

If imports fail (a2a-sdk symbol drift), inspect what's exported:

```bash
uv run python -c "import a2a.client; print(dir(a2a.client))"
uv run python -c "import a2a.types; print([x for x in dir(a2a.types) if 'Message' in x or 'Part' in x])"
```

Adjust `from a2a.client import ...` accordingly.

- [ ] **Step 3: Commit**

```bash
git add consumer/a2a_client.py
git commit -m "$(cat <<'EOF'
feat(consumer): add A2A client wrapper

send_provider_action(url, payload) resolves the agent card, sends a
message/send with the payload as a data part, returns the first
artifact's data. Used internally by consumer MCP tools.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 18: Consumer AgentCard

**Files:**
- Create: `consumer/agent_card.py`

- [ ] **Step 1: Implement**

```python
"""AgentCard for the consumer agent."""
from __future__ import annotations

import os

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

CONSUMER_BASE_URL = os.environ.get("CONSUMER_BASE_URL", "http://localhost:8001")


def build_consumer_agent_card() -> AgentCard:
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
            AgentInterface(
                protocol_binding="JSONRPC",
                url=f"{CONSUMER_BASE_URL}/v1/message/send",
            ),
        ],
        skills=[
            AgentSkill(
                id="purchase_bandwidth",
                name="Purchase Bandwidth",
                description=(
                    "Given a tier or bandwidth requirement, negotiates with a "
                    "provider, settles on chain, and activates the service."
                ),
                tags=["bandwidth", "agent2agent"],
                examples=["I need 5 Mbps for 10 minutes."],
            ),
        ],
    )
```

- [ ] **Step 2: Commit**

```bash
git add consumer/agent_card.py
git commit -m "$(cat <<'EOF'
feat(consumer): add AgentCard for the consumer agent

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 19: Consumer MCP server — local tools

**Files:**
- Create: `consumer/mcp_server.py`
- Create: `tests/test_consumer_mcp.py`

- [ ] **Step 1: Failing tests for the local tools**

Create `tests/test_consumer_mcp.py`:

```python
"""
In-memory MCP tests for the consumer's local tools.

Local tools (not network-bound) are tested directly. A2A-bound tools
(browse_catalog, request_quote, present_credential) are covered in
test_consumer_mcp_a2a.py once Task 20 is in.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import Client


CONSUMER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
CONSUMER_ADDR = Account.from_key(CONSUMER_KEY).address


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setenv("CONSUMER_PRIVATE_KEY", CONSUMER_KEY)
    monkeypatch.setenv("RPC_URL", "http://localhost:8545")  # may not be reachable; ok


@pytest.mark.asyncio
async def test_wallet_address_returns_consumer_eoa():
    from consumer.mcp_server import mcp
    async with Client(mcp) as c:
        result = await c.call_tool("wallet_address", {})
        assert result.content[0].text.lower() == CONSUMER_ADDR.lower()


@pytest.mark.asyncio
async def test_sign_message_recoverable():
    from consumer.mcp_server import mcp
    async with Client(mcp) as c:
        result = await c.call_tool("sign_message", {"text": "hello"})
        sig = result.content[0].text
        recovered = Account.recover_message(encode_defunct(text="hello"), signature=sig)
        assert recovered.lower() == CONSUMER_ADDR.lower()


@pytest.mark.asyncio
async def test_lock_payment_rejects_uncached_quote():
    from consumer.mcp_server import mcp
    async with Client(mcp) as c:
        result = await c.call_tool("lock_payment", {"agreement_id": "999999"})
        assert "ERROR" in result.content[0].text
```

- [ ] **Step 2: Run tests, expect import failure**

```bash
uv run pytest tests/test_consumer_mcp.py -v
```

- [ ] **Step 3: Implement local tools**

Create `consumer/mcp_server.py`:

```python
"""
Consumer agent's MCP server.

Tools:
  Local (no network):
    - wallet_address()         → consumer EOA
    - sign_message(text)       → ECDSA hex signature
    - lock_payment(agreement_id)
    - await_settlement(agreement_id, max_attempts)
  A2A-bound (network to provider):
    - browse_catalog(provider_url)
    - request_quote(provider_url, package_id)
    - present_credential(provider_url, token_id)
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct
from fastmcp import FastMCP
from web3 import Web3

from consumer.a2a_client import send_provider_action
from shared.contracts import get_escrow_contract

mcp = FastMCP("bandwidth-consumer")

_RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
_CONSUMER_KEY = os.environ.get("CONSUMER_PRIVATE_KEY")
_w3 = Web3(Web3.HTTPProvider(_RPC_URL))
_consumer_account = Account.from_key(_CONSUMER_KEY) if _CONSUMER_KEY else None

_STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}

# In-process cache for quotes returned by request_quote, used by lock_payment.
quote_cache: dict[str, dict] = {}


def _send_consumer_tx(func, value: int = 0) -> str:
    if _consumer_account is None:
        raise RuntimeError("CONSUMER_PRIVATE_KEY not set")
    tx = func.build_transaction({
        "from": _consumer_account.address,
        "nonce": _w3.eth.get_transaction_count(_consumer_account.address, "pending"),
        "value": value,
    })
    signed = _w3.eth.account.sign_transaction(tx, _CONSUMER_KEY)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    h = _w3.eth.send_raw_transaction(raw)
    receipt = _w3.eth.wait_for_transaction_receipt(h, timeout=60)
    if receipt["status"] != 1:
        raise RuntimeError(f"tx reverted: {h.hex() if hasattr(h, 'hex') else h}")
    return h.hex() if hasattr(h, "hex") else str(h)


# ── Local tools ──────────────────────────────────────────────────────────────
@mcp.tool()
def wallet_address() -> str:
    """Return the consumer agent's Ethereum address (0x...)."""
    if _consumer_account is None:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    return _consumer_account.address


@mcp.tool()
def sign_message(text: str) -> str:
    """Sign an arbitrary text with the consumer's EOA. Returns hex signature."""
    if _consumer_account is None or not _CONSUMER_KEY:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    msg = encode_defunct(text=text)
    return Account.sign_message(msg, private_key=_CONSUMER_KEY).signature.hex()


@mcp.tool()
def lock_payment(agreement_id: str) -> str:
    """
    Send escrow.requestAgreement on chain using the cached quote.
    Returns "OK <txHash>" on success, "ERROR ..." otherwise.
    """
    quote = quote_cache.get(str(agreement_id))
    if not quote:
        return f"ERROR: no cached quote for agreementId={agreement_id}. Call request_quote first."
    try:
        provider_addr = quote.get("providerAddress")
        if not provider_addr:
            return "ERROR: cached quote has no providerAddress"
        escrow = get_escrow_contract(_w3)
        tx = _send_consumer_tx(
            escrow.functions.requestAgreement(
                int(agreement_id),
                Web3.to_checksum_address(provider_addr),
                int(quote["bandwidthMbps"]),
                int(quote["durationSeconds"]),
            ),
            value=int(quote["priceWei"]),
        )
        return f"OK {tx}"
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
def await_settlement(agreement_id: str, max_attempts: int = 8) -> str:
    """
    Poll escrow.getAgreement until status==ACTIVE, max_attempts.
    Returns "OK tokenId=N" or "PENDING".
    """
    try:
        aid = int(agreement_id)
    except (ValueError, TypeError):
        return f"ERROR: agreement_id must be a number, got {agreement_id!r}"
    escrow = get_escrow_contract(_w3)
    for attempt in range(max_attempts):
        try:
            ag = escrow.functions.getAgreement(aid).call()
            status = _STATUS_NAMES.get(ag[7], "UNKNOWN")
            if status == "ACTIVE":
                return f"OK tokenId={ag[6]}"
            if status in ("CANCELLED", "CLOSED"):
                return f"ERROR: agreement is {status}"
        except Exception as e:
            return f"ERROR reading agreement: {e}"
        time.sleep(2)
    return "PENDING"
```

(A2A-bound tools added in Task 20.)

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_consumer_mcp.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add consumer/mcp_server.py tests/test_consumer_mcp.py
git commit -m "$(cat <<'EOF'
feat(consumer): MCP server with local wallet/escrow tools

wallet_address, sign_message, lock_payment, await_settlement.
A2A-bound tools (browse_catalog, request_quote, present_credential)
land in the next task.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 20: Consumer MCP — A2A-bound tools

**Files:**
- Modify: `consumer/mcp_server.py`
- Modify: `tests/test_consumer_mcp.py`

- [ ] **Step 1: Add tests with a fake `send_provider_action`**

Append to `tests/test_consumer_mcp.py`:

```python
@pytest.mark.asyncio
async def test_browse_catalog_calls_provider_a2a():
    expected = {"catalog": [{"packageId": "small", "mbps": 2, "durationSeconds": 600,
                             "priceWei": 10000000000000000, "availableSlots": 1}]}

    async def fake_send(provider_url, payload):
        assert payload == {"action": "get_catalog"}
        return expected

    with patch("consumer.mcp_server.send_provider_action", new=fake_send):
        from consumer.mcp_server import mcp
        async with Client(mcp) as c:
            result = await c.call_tool("browse_catalog",
                                       {"provider_url": "http://prov:8002"})
            data = json.loads(result.content[0].text)
            assert data == expected["catalog"]


@pytest.mark.asyncio
async def test_request_quote_caches_for_lock_payment():
    response = {
        "agreementId": "999",
        "priceWei": 10000000000000000,
        "bandwidthMbps": 2,
        "durationSeconds": 600,
    }

    async def fake_send(provider_url, payload):
        return response

    fake_provider_addr = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    fake_card = MagicMock()
    fake_card.skills = []  # not used; placeholder

    with patch("consumer.mcp_server.send_provider_action", new=fake_send), \
         patch("consumer.mcp_server._fetch_provider_address",
               return_value=fake_provider_addr):
        from consumer.mcp_server import mcp, quote_cache
        quote_cache.clear()
        async with Client(mcp) as c:
            result = await c.call_tool("request_quote", {
                "provider_url": "http://prov:8002",
                "package_id": "small",
            })
            data = json.loads(result.content[0].text)
            assert data["agreementId"] == "999"
            cached = quote_cache["999"]
            assert cached["providerAddress"] == fake_provider_addr
```

- [ ] **Step 2: Run, expect failure**

```bash
uv run pytest tests/test_consumer_mcp.py::test_browse_catalog_calls_provider_a2a -v
```

- [ ] **Step 3: Implement A2A-bound tools**

Append to `consumer/mcp_server.py`:

```python
import httpx as _httpx


async def _fetch_provider_address(provider_url: str) -> str:
    """
    Look up the provider's EOA. We use a small REST endpoint /address
    on the provider for this — keeping it as REST avoids carrying the
    address through an A2A message we already have to make for the
    quote. Alternative: include providerAddress in the QuoteResponse.
    """
    async with _httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(f"{provider_url}/address")
        resp.raise_for_status()
        return resp.json()["address"]


@mcp.tool()
async def browse_catalog(provider_url: str) -> str:
    """
    Discover provider's catalog via A2A.

    Returns JSON array of {packageId, mbps, durationSeconds, priceWei, availableSlots}.
    """
    try:
        result = await send_provider_action(provider_url, {"action": "get_catalog"})
        catalog = result.get("catalog")
        if catalog is None:
            return f"ERROR: provider response missing 'catalog' key: {result}"
        return json.dumps(catalog)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
async def request_quote(provider_url: str, package_id: str) -> str:
    """
    Request a price quote for a package via A2A. Caches the quote so
    lock_payment can find it. Returns
      {agreementId, priceWei, bandwidthMbps, durationSeconds}.
    """
    if _consumer_account is None:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    try:
        provider_addr = await _fetch_provider_address(provider_url)
        result = await send_provider_action(provider_url, {
            "action": "request_quote",
            "package_id": package_id,
            "consumer_address": _consumer_account.address,
        })
        if "error" in result:
            return f"ERROR: {result['error']}"
        # Cache including provider address for lock_payment.
        quote_cache[str(result["agreementId"])] = {
            **result,
            "providerAddress": provider_addr,
        }
        return json.dumps(result)
    except Exception as e:
        return f"ERROR: {e}"


@mcp.tool()
async def present_credential(provider_url: str, token_id: int) -> str:
    """
    Sign a fresh nonce, send 'activate' over A2A, return service metadata.
    """
    if _consumer_account is None or not _CONSUMER_KEY:
        return "ERROR: CONSUMER_PRIVATE_KEY not set"
    nonce = str(int(time.time()))
    sig = Account.sign_message(encode_defunct(text=nonce),
                                private_key=_CONSUMER_KEY).signature.hex()
    try:
        result = await send_provider_action(provider_url, {
            "action": "activate",
            "token_id": int(token_id),
            "nonce": nonce,
            "signature": sig,
        })
        return json.dumps(result)
    except Exception as e:
        return f"ERROR: {e}"
```

- [ ] **Step 4: Test**

```bash
uv run pytest tests/test_consumer_mcp.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add consumer/mcp_server.py tests/test_consumer_mcp.py
git commit -m "$(cat <<'EOF'
feat(consumer): MCP A2A-bound tools (browse, quote, present)

browse_catalog / request_quote / present_credential — all wrap
send_provider_action under the hood. The LLM never sees A2A directly,
only these high-level verbs.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 21: Refactor `consumer/app.py` to use in-memory MCP

**Files:**
- Modify: `consumer/app.py`
- Delete: `consumer/mcp_client.py`

- [ ] **Step 1: Replace tool dispatch in `consumer/app.py`**

Open `consumer/app.py`. Replace the imports block at the top:

```python
import json
import os
import time
import traceback

import httpx
import ollama
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastmcp import Client as MCPClient
from pydantic import BaseModel, Field

from consumer.agent_card import build_consumer_agent_card
from consumer.mcp_server import mcp as consumer_mcp
```

Drop these (they're replaced):
- `from eth_account import Account`
- `from eth_account.messages import encode_defunct`
- `from web3 import Web3`
- `from consumer.mcp_client import ...`
- `from shared.contracts import ...`
- The module-level `w3`, `consumer_account`, `CONSUMER_ADDRESS`.
- The local helper functions `_send_tx`, `_get_provider_address`, `execute_agreement`, `check_agreement_status`.
- The `LOCAL_TOOL_MAP`, `LOCAL_TOOL_SCHEMAS`.

Add a single helper for converting MCP tools to Ollama format (same idea as the deleted `mcp_tool_to_ollama`):

```python
def _mcp_tool_to_ollama(tool) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }
```

Replace `run_consumer` with:

```python
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:4b")
PROVIDER_A2A_URLS = [u.strip() for u in
                     os.environ.get("PROVIDER_A2A_URLS",
                                    "http://localhost:8002").split(",")
                     if u.strip()]

_consumer_agent_card = build_consumer_agent_card()

inter_agent_log: list[dict] = []
_logged: set[tuple[str, str]] = set()


def _append(sender: str, message: str) -> None:
    key = (sender, message)
    if key in _logged:
        return
    _logged.add(key)
    inter_agent_log.append({"from": sender, "message": message})


def _extract_thinking(content: str) -> tuple[str, list[str]]:
    thoughts: list[str] = []
    visible: list[str] = []
    rem = content
    while "<think>" in rem and "</think>" in rem:
        before, rest = rem.split("<think>", 1)
        thought, rem = rest.split("</think>", 1)
        if before.strip():
            visible.append(before.strip())
        if thought.strip():
            thoughts.append(thought.strip())
    if "</think>" in rem:
        thought, rem = rem.split("</think>", 1)
        if thought.strip():
            thoughts.append(thought.strip())
    if rem.strip():
        visible.append(rem.strip())
    return "\n\n".join(visible), thoughts


SYSTEM_PROMPT_TEMPLATE = """You are a bandwidth procurement agent. Your goal is to get the user an ACTIVE service.

## Available providers
{provider_urls}

## Tools (all via your local MCP — do NOT make HTTP requests directly)

A2A-bound (talk to a provider, you must pass provider_url):
- browse_catalog(provider_url)
- request_quote(provider_url, package_id)
- present_credential(provider_url, token_id)

Local (operate on your own wallet / chain):
- wallet_address()
- sign_message(text)
- lock_payment(agreement_id)
- await_settlement(agreement_id)

## Workflow
1. browse_catalog on the (first) configured provider to see prices/availability.
2. Pick the smallest tier that satisfies the user's request.
3. request_quote to obtain agreementId.
4. lock_payment with the returned agreementId.
5. await_settlement.
6. present_credential with the tokenId.
7. Report what was bought (agreementId, tokenId, mbps).

## Rules
- Pass provider_url as the FIRST argument to browse_catalog / request_quote / present_credential.
- Use your wallet_address() if any tool needs the consumer address.
- Only report the EXACT agreementId and tokenId returned by tools — never invent.
"""


async def run_consumer(user_message: str, model: str = DEFAULT_MODEL) -> tuple[str, list[dict], list[str]]:
    inter_agent_log.clear()
    _logged.clear()
    thinking: list[str] = []

    async with MCPClient(consumer_mcp) as mcp_client:
        tools_raw = await mcp_client.list_tools()
        tool_schemas = [_mcp_tool_to_ollama(t) for t in tools_raw]
        tool_names = {t.name for t in tools_raw}

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            provider_urls="\n".join(f"- {u}" for u in PROVIDER_A2A_URLS),
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ]

        ollama_client = ollama.AsyncClient()

        for _ in range(12):
            try:
                response = await ollama_client.chat(model=model, messages=messages,
                                                     tools=tool_schemas, think=False)
            except Exception as e:
                msg = f"Ollama Error: {e}"
                if "not found" in str(e).lower():
                    msg += f"\n\nMake sure to pull the model first: `ollama pull {model}`"
                return msg, list(inter_agent_log), thinking

            m = response.message
            visible, thought_chunks = _extract_thinking(m.content or "")
            thinking.extend(thought_chunks)
            if m.thinking:
                thinking.append(m.thinking.strip())

            if not m.tool_calls:
                break

            messages.append({"role": "assistant", "content": visible, "tool_calls": m.tool_calls})

            for tc in m.tool_calls:
                tool_name = tc.function.name
                args = tc.function.arguments or {}
                if tool_name not in tool_names:
                    result = f"ERROR: unknown tool '{tool_name}'"
                else:
                    _append("consumer", f"[MCP] {tool_name}({json.dumps(args)})")
                    try:
                        out = await mcp_client.call_tool(tool_name, args)
                        result = out.content[0].text if out.content else ""
                    except Exception as e:
                        result = f"ERROR calling {tool_name}: {e}"
                    _append("provider" if tool_name in
                            {"browse_catalog", "request_quote", "present_credential"}
                            else "consumer", result[:400])
                messages.append({"role": "tool", "tool_name": tool_name, "content": str(result)})
        else:
            return ("Settlement still pending after several retries. The NFT will land "
                     "automatically once the provider processes the event — check back shortly.",
                     list(inter_agent_log), thinking)

        return visible, list(inter_agent_log), thinking
```

Replace the FastAPI section's `/.well-known/agent.json`:

```python
@app.get("/.well-known/agent-card.json")
def agent_card_canonical() -> dict:
    return _consumer_agent_card.model_dump(mode="json", by_alias=True)


@app.get("/.well-known/agent.json")
def agent_card_legacy() -> dict:
    return _consumer_agent_card.model_dump(mode="json", by_alias=True)
```

Drop `/check_token` (it called the deleted gateway), drop `/catalog_proxy` (the consumer no longer has a "proxy" — call browse_catalog via the chat or expose it as its own endpoint if the UI needs it).

If the UI needs `/catalog_proxy` for the catalog card display, replace it with:

```python
@app.get("/catalog_proxy")
async def catalog_proxy() -> list[dict]:
    async with MCPClient(consumer_mcp) as c:
        result = await c.call_tool("browse_catalog",
                                    {"provider_url": PROVIDER_A2A_URLS[0]})
        text = result.content[0].text
    if text.startswith("ERROR"):
        raise HTTPException(502, text)
    return json.loads(text)


@app.get("/address")
async def consumer_address_endpoint() -> dict:
    async with MCPClient(consumer_mcp) as c:
        result = await c.call_tool("wallet_address", {})
    return {"address": result.content[0].text}
```

- [ ] **Step 2: Delete `consumer/mcp_client.py`**

```bash
git rm consumer/mcp_client.py
```

- [ ] **Step 3: Smoke test (offline — no Anvil needed for imports)**

```bash
uv run python -c "import consumer.app; print('imports ok')"
```

- [ ] **Step 4: Live smoke test**

```bash
make down-clean && make up
sleep 30   # ollama pull is slow on first run
curl -sf http://localhost:8001/.well-known/agent-card.json | jq .name
curl -sf http://localhost:8001/catalog_proxy | jq 'length'
```

Expected: consumer card name, catalog with 3 entries.

End-to-end demo:

```bash
SDN_MOCK=true make demo
```

Expected: a successful purchase report with non-zero agreementId and tokenId.

- [ ] **Step 5: Commit**

```bash
git add consumer/app.py
git rm consumer/mcp_client.py
git commit -m "$(cat <<'EOF'
refactor(consumer): LLM loop now uses in-memory MCP + A2A

Drops consumer/mcp_client.py (cross-network MCP is gone). LLM sees
only consumer-local MCP tools; A2A is hidden inside browse_catalog,
request_quote, present_credential. System prompt updated to take a
list of provider URLs.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 6 — Catalog rescale + slot binding (already done in Task 5; this phase verifies + tightens)

> Phase 5 already wired SlotPool + rescaled catalog in Task 5. This phase confirms the slot binding survives a real on-chain purchase and adds revoke-on-expiry.

### Task 22: Add slot revocation on lease expiry

**Files:**
- Create: `provider/expiry.py`
- Modify: `provider/app.py`

- [ ] **Step 1: Implement an asyncio expiry sweep**

Create `provider/expiry.py`:

```python
"""
Periodic sweep that finds slots whose lease has expired and revokes
the SDN allocation, freeing the slot for reuse.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastmcp import Client as MCPClient

from provider.catalog import slot_pool
from provider.mcp_server import mcp

log = logging.getLogger("provider.expiry")


async def expiry_sweep_loop(period_seconds: int = 30) -> None:
    """Run forever: every period_seconds, revoke SDN for any expired slot."""
    log.info("Expiry sweep started, period=%ss", period_seconds)
    while True:
        await asyncio.sleep(period_seconds)
        try:
            await _sweep_once()
        except Exception:
            log.exception("expiry sweep error")


async def _sweep_once() -> None:
    now = time.time()
    # SlotPool reclaims expired entries on read; so we need to capture them
    # *before* the next read clears them. Read raw rows directly.
    import fcntl
    rows = []
    with open(slot_pool.path, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            for line in f.read().splitlines():
                if line.strip():
                    rows.append(json.loads(line))
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    expired: list[tuple[str, str, str, int]] = []
    for row in rows:
        for s in row.get("slots", []):
            if s.get("expiresAt") is not None and s["expiresAt"] < now:
                expired.append((s["pe"], s["subinterface"], s["ce"],
                                s["agreementId"]))

    if not expired:
        return

    async with MCPClient(mcp) as client:
        for pe, subif, ce, aid in expired:
            log.info("revoking expired slot pe=%s sif=%s aid=%s", pe, subif, aid)
            try:
                await client.call_tool("revoke_bandwidth", {
                    "customer_id": "expired",  # informational
                    "pe": pe, "subinterface": subif,
                })
            except Exception:
                log.exception("revoke_bandwidth failed")
            slot_pool.release(int(aid))
```

- [ ] **Step 2: Wire into `provider/app.py` lifespan**

Add import:

```python
from provider.expiry import expiry_sweep_loop
```

Update the lifespan context manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with _mcp_http_app.lifespan(app):
        asyncio.create_task(_event_listener())
        asyncio.create_task(expiry_sweep_loop(period_seconds=30))
        yield
```

- [ ] **Step 3: Smoke test**

```bash
make down-clean && make up
sleep 15
docker compose logs provider-agent | grep "Expiry sweep started"
```

Expected: log line `Expiry sweep started, period=30s`.

- [ ] **Step 4: Commit**

```bash
git add provider/expiry.py provider/app.py
git commit -m "$(cat <<'EOF'
feat(provider): periodic expiry sweep revokes SDN on slot timeout

Every 30s the provider scans the slot pool for expired leases and
calls revoke_bandwidth via in-memory MCP, then releases the slot.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 7 — Real SDN demo

### Task 23: Make targets for ContainerLab

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Add `clab-up` / `clab-down` / `demo-real` targets**

Append to `Makefile`:

```makefile
CLAB_REPO ?= ../srl-gnmi-bandwidth-poc

.PHONY: clab-up clab-down demo-real

clab-up:
	@test -d $(CLAB_REPO) || (echo "ERROR: brother repo not at $(CLAB_REPO)"; exit 1)
	cd $(CLAB_REPO) && bash scripts/deploy.sh
	@echo "Sleeping 60s for SR Linux to boot..."
	@sleep 60
	cd $(CLAB_REPO) && bash scripts/push-config.sh
	@echo "ContainerLab ready."

clab-down:
	cd $(CLAB_REPO) && bash scripts/destroy.sh

demo-real: _check_services
	@echo ""
	@echo "=== Running demo with REAL SDN (SDN_MOCK=false) ==="
	@docker compose stop provider-agent
	@SDN_MOCK=false docker compose up -d provider-agent
	@sleep 5
	@$(MAKE) demo
	@echo ""
	@echo "=== Verifying bandwidth is shaped (medium tier expected ~5 Mbps ce3→ce4) ==="
	@curl -sf -X POST http://localhost:8002/v1/message/send \
		-H "Content-Type: application/json" \
		-d '{"jsonrpc":"2.0","id":"v","method":"message/send","params":{"message":{"messageId":"v1","role":"ROLE_USER","parts":[{"data":{"action":"verify","src_ce":"ce3","dst_ce":"ce4","expected_mbps":5.0}}]}}}' \
		| python3 -m json.tool
```

- [ ] **Step 2: Smoke (no clab needed for the syntax check)**

```bash
make -n clab-up | head -5
```

Expected: prints the commands without error.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "$(cat <<'EOF'
chore(make): add clab-up, clab-down, demo-real targets

clab-up runs the brother repo's deploy + push-config scripts, then
sleeps 60s. demo-real flips SDN_MOCK=false and runs the demo + a
verify_bandwidth probe.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 24: Mount Docker socket in provider container for SDN ops

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Dockerfile.provider`

- [ ] **Step 1: Mount Docker socket + add docker CLI**

Add to `Dockerfile.provider` final stage (before `CMD`):

```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends docker.io \
 && rm -rf /var/lib/apt/lists/*
```

Edit `docker-compose.yml` `provider-agent` service:

```yaml
provider-agent:
  build:
    context: .
    dockerfile: Dockerfile.provider
  depends_on:
    deployer:
      condition: service_completed_successfully
  ports:
    - "8002:8002"
  environment:
    - RPC_URL=http://anvil:8545
    - PROVIDER_PRIVATE_KEY=${PROVIDER_PRIVATE_KEY}
    - SDN_MOCK=${SDN_MOCK:-true}
  volumes:
    - ./contracts/deployments:/app/contracts/deployments:ro
    - ./provider/inventory.txt:/app/provider/inventory.txt
    - /var/run/docker.sock:/var/run/docker.sock
  extra_hosts:
    - "host.docker.internal:host-gateway"
```

- [ ] **Step 2: Smoke test**

```bash
make down-clean && make up
sleep 10
docker compose exec provider-agent docker ps | head -3
```

Expected: docker CLI works inside the provider container, lists running containers (including clab nodes if deployed).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml Dockerfile.provider
git commit -m "$(cat <<'EOF'
chore(infra): mount docker.sock + add docker CLI to provider container

Lets the provider's allocate_bandwidth MCP tool docker-exec into
the brother repo's CE containers for tc tbf application. extra_hosts
host.docker.internal added so pygnmi can resolve clab management IPs.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

### Task 25: README — running the real SDN demo

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Running the real SDN demo" section**

Add a new section to `README.md` (above any existing "Demo" section):

```markdown
## Running the demo with real SDN enforcement

The default `make demo` runs with `SDN_MOCK=true` — `allocate_bandwidth`
returns success without touching any network device.

To run the demo against ContainerLab + Nokia SR Linux + Linux `tc`:

1. Deploy ContainerLab (one-time per session, requires sudo):
   ```bash
   make clab-up      # runs ../srl-gnmi-bandwidth-poc/scripts/deploy.sh + push-config.sh
   ```

2. Run the demo with SDN enforcement enabled:
   ```bash
   make demo-real
   ```

3. Tear down:
   ```bash
   make clab-down
   make down
   ```

ContainerLab's 7-node topology and the slot mapping:

| Tier   | Mbps | PE  | Subinterface     | CE  |
|--------|------|-----|------------------|-----|
| small  | 2    | pe1 | ethernet-1/2.0   | ce1 |
| medium | 5    | pe1 | ethernet-1/3.0   | ce3 |
| large  | 8    | pe2 | ethernet-1/2.0   | ce2 |

After a `medium` purchase you can verify the rate is shaped:
```bash
docker exec clab-bandwidth-poc-ce4 iperf3 -s -1 -p 5201 -J &
docker exec clab-bandwidth-poc-ce3 iperf3 -c 192.168.4.10 -p 5201 -t 5 -u -b 15M -J
```
Expected: receiver `bits_per_second ≈ 5.0e6`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
docs: add 'Running the real SDN demo' section

Documents the make clab-up / demo-real flow, the tier→slot mapping,
and the manual iperf3 verification command.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 8 — Multi-agent stretch

### Task 26: Add `consumer-agent-2` to compose

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add second key to `.env.example`**

Append:

```bash
# account[3] — second consumer EOA for multi-agent demos
CONSUMER_PRIVATE_KEY_2=0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6
CONSUMER_ADDRESS_2=0x90F79bf6EB2c4f870365E785982E1f101E93b906
```

- [ ] **Step 2: Add the service to `docker-compose.yml`**

Add a new service entry (sibling of `consumer-agent`):

```yaml
consumer-agent-2:
  build:
    context: .
    dockerfile: Dockerfile.consumer
  depends_on:
    provider-agent:
      condition: service_started
    ollama-pull-4b:
      condition: service_completed_successfully
  ports:
    - "8011:8001"
  environment:
    - RPC_URL=http://anvil:8545
    - CONSUMER_PRIVATE_KEY=${CONSUMER_PRIVATE_KEY_2}
    - PROVIDER_A2A_URLS=http://provider-agent:8002
    - OLLAMA_MODEL=${OLLAMA_MODEL:-qwen3:4b}
    - OLLAMA_HOST=http://ollama:11434
  volumes:
    - ./contracts/deployments:/app/contracts/deployments:ro
  profiles:
    - multi-consumer
```

The `profiles: [multi-consumer]` keeps it out of the default `make up` flow. Activate with `docker compose --profile multi-consumer up -d`.

- [ ] **Step 3: Smoke test**

```bash
docker compose --profile multi-consumer up -d
sleep 30
curl -sf http://localhost:8001/.well-known/agent-card.json | jq .name
curl -sf http://localhost:8011/.well-known/agent-card.json | jq .name
```

Expected: both cards reachable on different ports.

- [ ] **Step 4: Run two simultaneous purchases (manual)**

```bash
# Terminal 1
curl -X POST http://localhost:8001/chat -H "Content-Type: application/json" \
  -d '{"message":"I need 5 Mbps", "model":"qwen3:4b"}' &

# Terminal 2 (same time)
curl -X POST http://localhost:8011/chat -H "Content-Type: application/json" \
  -d '{"message":"I need 2 Mbps", "model":"qwen3:4b"}' &

wait
```

Expected: both calls return success (different agreementIds, different tokenIds, different slots: medium=ce3, small=ce1).

- [ ] **Step 5: Document the multi-consumer flow in the README**

Append to `README.md` "Running the demo" section:

```markdown
### Two consumers in parallel

```bash
docker compose --profile multi-consumer up -d
# Consumer 1 reachable at http://localhost:8001/chat
# Consumer 2 reachable at http://localhost:8011/chat
```
The two consumers use different EOAs and bind different slots. Try
ordering different tiers from each at the same time to verify the
slot pool's lock-based concurrency is sound.
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(infra): add consumer-agent-2 under multi-consumer compose profile

Demonstrates N-consumer extensibility. Two consumers with distinct
EOAs target the same provider; slot pool's fcntl lock prevents races.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Phase 9 — Final cleanup + sanity

### Task 27: Strip dead code, run full test suite, update CODEBASE_REFERENCE.md

**Files:**
- Modify: `CODEBASE_REFERENCE.md`
- Possibly remove: legacy files at repo root if user opts in (NOT in this plan — kept untouched per spec §1.2)

- [ ] **Step 1: Run full test suite**

```bash
SDN_MOCK=true uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 2: Live end-to-end on Anvil only (no clab)**

```bash
make down-clean && make up
sleep 30
SDN_MOCK=true make demo
```

Expected: a successful purchase end-to-end.

- [ ] **Step 3: Update `CODEBASE_REFERENCE.md`**

The reference document at the repo root is structured. Update these sections to reflect the new architecture:

- §1 PROJECT IDENTITY — replace "MCP cross-network" with "A2A inter-agent + per-agent MCP"; mention SDN integration.
- §3 FULL DIRECTORY TREE — add `consumer/mcp_server.py`, `consumer/a2a_client.py`, `consumer/agent_card.py`, `provider/agent_card.py`, `provider/agent_executor.py`, `provider/expiry.py`, `shared/slot_pool.py`, `shared/a2a_messages.py`. Remove `provider/gateway.py` and `consumer/mcp_client.py`.
- §4 ARCHITECTURE & PATTERNS — replace the diagram with the §4.1 diagram from the spec. Update each "Key pattern" line to match.
- §5 ENTRY POINTS — drop Gateway from the table.
- §7 API & INTERFACES — replace the Gateway table; add A2A endpoints (POST /v1/message/send, GET /v1/tasks/{id}, GET /.well-known/agent-card.json). Replace the consumer endpoint list.
- §11 KNOWN QUIRKS — drop quirks #4 (gateway), keep #5 (MCP per-call connection — applies only to A2A now), update wording.

This is a long edit; reasonable to do as a single commit.

- [ ] **Step 4: Commit**

```bash
git add CODEBASE_REFERENCE.md
git commit -m "$(cat <<'EOF'
docs: refresh CODEBASE_REFERENCE.md for A2A + per-agent MCP

Updates the AI-to-AI assistant map to match the realigned architecture
(A2A inter-agent, per-agent MCP, slot pool, deleted gateway, SDN tools).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push
```

---

## Verification matrix (acceptance check)

These commands map 1:1 to the §15 acceptance criteria in the spec. Run them after Task 27.

| Spec criterion | Command | Expected |
|---|---|---|
| 1. End-to-end with real SDN | `make clab-up && make demo-real` | success message + iperf3 verify near 5 Mbps |
| 2. LLM emits MCP only | `grep -r "PROVIDER_MCP_URL\|provider/mcp_client" consumer/` | empty |
| 3. Provider receives only A2A | `grep -r "8003\|gateway" provider/ docker-compose.yml` | empty (only legacy README mentions OK) |
| 4. Medium tier ≈ 5 Mbps | manual iperf3 ce3→ce4 (Task 25) | 4.0 ≤ measured ≤ 6.0 |
| 5. Slot reclaim on expiry | wait 600s post-purchase, check inventory.txt | slot back to `agreementId: null` |
| 6. Tests green | `SDN_MOCK=true uv run pytest tests/ -v` | all pass |
| 7. Six paper stages map to §6 of spec | manual review | each stage has exact entries in the table |
| 8. Two consumers concurrent | Task 26 step 4 | both succeed |
| 9. Agent card valid | `curl localhost:8002/.well-known/agent-card.json | jq` | valid JSON, name/skills present |
| 10. Gateway file deleted | `git ls-files | grep gateway` | empty |

---

## Self-review

I checked the plan against the spec section by section:

**Spec coverage:**
- §4 Architecture diagram — implemented across Phases 2–5.
- §5 Component-level design — every new file in §5.1 has a creation task.
- §6 Data flow stages 1–6 — Tasks 12, 15 cover stages 1, 2, 5; the on-chain Stages 3 & 4 are covered by Task 9 (event listener using MCP).
- §7 Schemas — Tasks 4, 6, 7, 8, 10, 13, 19, 20.
- §8 ContainerLab — Tasks 23, 24, 25.
- §9 Catalog rescale — Task 5.
- §10 Multi-agent — Task 26.
- §13 Future-work seams — left as comments / out of scope, no task needed.
- §14 Risks — addressed in tasks via `SDN_MOCK` and version pinning.
- §15 Acceptance — covered by the verification matrix.

**Type consistency:**
- `SlotPool.reserve(tier, agreement_id, duration_seconds)` — used in Task 9 with the same arg order. ✓
- `SlotPool.lookup(agreement_id) -> Slot | None` — used in Task 15. ✓
- `Slot.pe / .subinterface / .ce` — used in Task 9, Task 15. ✓
- `pending_quotes` import in Task 9 — exists in Task 5's `provider/catalog.py`. ✓
- `quote_cache: dict[str, dict]` — populated in Task 20 `request_quote`, read in Task 19 `lock_payment`. Keys are stringified `agreementId`. ✓
- `send_provider_action(provider_url, payload) -> dict` — defined in Task 17, called in Task 20. ✓
- `BandwidthProviderExecutor` — defined in Task 12, instantiated in Task 13. ✓
- A2A SDK imports flagged in Task 11 with fallback inspection commands if version drifts.

**Placeholder scan:**
No "TBD", "TODO", or unresolved sections. Where the a2a-sdk API surface is uncertain (Tasks 11, 12, 17), the plan includes a defensive `uv run python -c "import a2a..."` step to verify and lists the signal that triggers a retry — that is concrete recovery guidance, not a placeholder.

---
