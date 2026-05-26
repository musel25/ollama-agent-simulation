# Blockchain Primer Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hands-on, ground-up blockchain & Solidity primer notebook in `notebooks/blockchain_primer/` that drives a local `anvil` chain through `cast`/`forge` and ends with a guided read of the project's `BandwidthEscrow` contract.

**Architecture:** A single generated `01a0_blockchain_primer.ipynb` assembled from per-section Python modules under `notebooks/blockchain_primer/sections/`. A `build_notebook.py` script uses `nbformat` to concatenate section cell lists into the final notebook. Two toy contracts (`Counter.sol`, `HelloWorld.sol`) and a local `foundry.toml` live in the same folder so the primer is self-contained and cannot disturb the production `contracts/` build. The "test gate" for each task is `jupyter nbconvert --execute` exiting 0.

**Tech Stack:** Python (nbformat, subprocess), Jupyter (nbconvert), Foundry (anvil, cast, forge), Solidity 0.8.20.

**Spec:** [docs/superpowers/specs/2026-05-26-blockchain-primer-notebook-design.md](../specs/2026-05-26-blockchain-primer-notebook-design.md)

---

## File Structure

```
notebooks/blockchain_primer/
├── 01a0_blockchain_primer.ipynb   # generated artifact (committed)
├── build_notebook.py              # collects sections → writes .ipynb
├── sections/
│   ├── __init__.py
│   ├── _helpers.py                # md(), code() cell factories
│   ├── s00_setup.py               # imports, anvil startup, run() helper
│   ├── s01_chain.py               # §1 What is a chain
│   ├── s02_accounts.py            # §2 Accounts & keys
│   ├── s03_transactions.py        # §3 A transaction
│   ├── s04_state_history.py       # §4 State vs history
│   ├── s05_deploy.py              # §5 Deploy Counter.sol
│   ├── s06_evm.py                 # §6 send vs call, gas, revert
│   ├── s07_solidity.py            # §7 Solidity syntax via HelloWorld.sol
│   ├── s08_events.py              # §8 Events
│   ├── s09_foundry.py             # §9 Foundry toolkit recap
│   ├── s10_escrow.py              # §10 Reading BandwidthEscrow
│   └── s99_teardown.py            # kill anvil
├── contracts/
│   ├── Counter.sol
│   └── HelloWorld.sol
├── foundry.toml
└── README.md
```

**Responsibilities:**
- `build_notebook.py` — orchestrates: imports each section module, calls `.cells()`, writes the `.ipynb`. Idempotent.
- `sections/_helpers.py` — two factory functions returning nbformat cell dicts. One source of truth for cell construction.
- `sections/sNN_*.py` — each exports `def cells() -> list[dict]`. Pure functions, no side effects.
- `contracts/*.sol` — toy contracts for §5–§8.
- `01a0_blockchain_primer.ipynb` — committed generated artifact so readers can view on GitHub without running the builder.

**Working directory convention:** All commands run from the **repo root** (`/home/musel/Github/ollama-agent-simulation`). The notebook itself executes from `notebooks/blockchain_primer/` (jupyter's default).

---

## Task 1: Scaffold folder + foundry.toml + README

**Files:**
- Create: `notebooks/blockchain_primer/foundry.toml`
- Create: `notebooks/blockchain_primer/README.md`
- Create: `notebooks/blockchain_primer/contracts/.gitkeep`
- Create: `notebooks/blockchain_primer/sections/__init__.py` (empty)

- [ ] **Step 1: Create the folder skeleton**

```bash
mkdir -p notebooks/blockchain_primer/contracts notebooks/blockchain_primer/sections
touch notebooks/blockchain_primer/contracts/.gitkeep notebooks/blockchain_primer/sections/__init__.py
```

- [ ] **Step 2: Write `notebooks/blockchain_primer/foundry.toml`**

```toml
[profile.default]
src = "contracts"
out = "out"
libs = []
solc = "0.8.20"
optimizer = true
optimizer_runs = 200
```

- [ ] **Step 3: Write `notebooks/blockchain_primer/README.md`**

```markdown
# Blockchain Primer

A hands-on, ground-up walkthrough of blockchain accounts, transactions, the EVM, and Solidity — driven by a local `anvil` chain through `cast` and `forge`. Ends with a guided read of `contracts/src/BandwidthEscrow.sol`.

Open **[01a0_blockchain_primer.ipynb](01a0_blockchain_primer.ipynb)** and run top to bottom.

**Requirements:** Foundry (`anvil`, `cast`, `forge`) on `PATH`. Verify with `anvil --version`.

**Regenerating the notebook:** the notebook is assembled from `sections/*.py` by `build_notebook.py`. After editing any section module, run `uv run python notebooks/blockchain_primer/build_notebook.py`.
```

- [ ] **Step 4: Verify foundry config parses**

Run: `cd notebooks/blockchain_primer && forge config --root . > /dev/null && echo OK && cd -`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add notebooks/blockchain_primer
git commit -m "chore(primer): scaffold blockchain_primer folder + foundry config"
```

---

## Task 2: Toy contracts (Counter.sol + HelloWorld.sol) + forge build verifies

**Files:**
- Create: `notebooks/blockchain_primer/contracts/Counter.sol`
- Create: `notebooks/blockchain_primer/contracts/HelloWorld.sol`

- [ ] **Step 1: Write `Counter.sol`**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Tiny contract used to demonstrate deployment and state-changing calls.
contract Counter {
    uint256 public number;

    function increment() external {
        number += 1;
    }

    /// @notice Reverts when count would exceed 5. Used to demonstrate revert behavior.
    function incrementBounded() external {
        require(number < 5, "max reached");
        number += 1;
    }
}
```

- [ ] **Step 2: Write `HelloWorld.sol`**

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Exercises every Solidity feature used by BandwidthEscrow, in miniature.
contract HelloWorld {
    address public owner;
    mapping(address => uint256) public greetings;

    event Greeted(address indexed who, uint256 count);
    error NotOwner();
    error SendSomething();

    constructor() {
        owner = msg.sender;
    }

    function greet() external payable {
        if (msg.value == 0) revert SendSomething();
        greetings[msg.sender] += 1;
        emit Greeted(msg.sender, greetings[msg.sender]);
    }

    function withdraw() external {
        if (msg.sender != owner) revert NotOwner();
        (bool ok, ) = msg.sender.call{value: address(this).balance}("");
        require(ok, "transfer failed");
    }
}
```

- [ ] **Step 3: Build with forge**

Run: `cd notebooks/blockchain_primer && forge build && cd -`
Expected: output contains `Compiler run successful` and creates `notebooks/blockchain_primer/out/`.

- [ ] **Step 4: Add `out/` to gitignore for the primer folder**

Append to `notebooks/blockchain_primer/.gitignore` (create if missing):

```
out/
cache/
broadcast/
```

- [ ] **Step 5: Commit**

```bash
git add notebooks/blockchain_primer/contracts notebooks/blockchain_primer/.gitignore
git commit -m "feat(primer): add Counter and HelloWorld toy contracts"
```

---

## Task 3: Section helpers + builder script + setup section + teardown + first build

**Files:**
- Create: `notebooks/blockchain_primer/sections/_helpers.py`
- Create: `notebooks/blockchain_primer/sections/s00_setup.py`
- Create: `notebooks/blockchain_primer/sections/s99_teardown.py`
- Create: `notebooks/blockchain_primer/build_notebook.py`

- [ ] **Step 1: Write `sections/_helpers.py`**

```python
"""Cell factories. One source of truth for nbformat cell construction."""
from __future__ import annotations
import nbformat


def md(source: str) -> dict:
    return nbformat.v4.new_markdown_cell(source)


def code(source: str) -> dict:
    return nbformat.v4.new_code_cell(source)
```

- [ ] **Step 2: Write `sections/s00_setup.py`**

```python
"""§0 — Notebook setup: imports, run() helper, start anvil.

This section is invisible to the reader as a "section" — its purpose is to
establish the runtime environment used by every later section.
"""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "# 01a0 — Blockchain & smart contracts primer\n"
            "\n"
            "A ground-up, hands-on tour. We drive a real local Ethereum chain "
            "(`anvil`) through `cast` and `forge`, naming each concept after we've "
            "executed it. By the last section you'll be able to read "
            "[BandwidthEscrow.sol](../../contracts/src/BandwidthEscrow.sol) line by line.\n"
            "\n"
            "**Prereq:** `anvil`, `cast`, `forge` on PATH (Foundry installed). "
            "Run cells top to bottom — anvil is started in the next cell and "
            "killed in the very last cell."
        ),
        code(
            "# --- Notebook runtime setup ---------------------------------------\n"
            "import atexit, subprocess, time, shutil, sys, pathlib, json, os\n"
            "\n"
            "PRIMER_DIR = pathlib.Path.cwd().resolve()\n"
            "REPO_ROOT = PRIMER_DIR.parent.parent\n"
            "RPC = 'http://127.0.0.1:8545'\n"
            "\n"
            "def run(cmd, cwd=None, check=True):\n"
            "    \"\"\"Run a shell command, show it, return stdout.\"\"\"\n"
            "    print('$', ' '.join(str(c) for c in cmd))\n"
            "    r = subprocess.run(cmd, cwd=cwd or PRIMER_DIR, capture_output=True, text=True)\n"
            "    if r.stdout: print(r.stdout.rstrip())\n"
            "    if r.returncode != 0:\n"
            "        if r.stderr: print(r.stderr.rstrip(), file=sys.stderr)\n"
            "        if check: raise SystemExit(f'command failed: {cmd}')\n"
            "    return r.stdout.strip()\n"
            "\n"
            "for tool in ('anvil', 'cast', 'forge'):\n"
            "    assert shutil.which(tool), f'{tool} not found on PATH'\n"
            "print('Foundry tools OK')"
        ),
        code(
            "# --- Start anvil --------------------------------------------------\n"
            "_anvil_proc = subprocess.Popen(\n"
            "    ['anvil', '--host', '127.0.0.1', '--port', '8545', '--silent'],\n"
            "    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,\n"
            ")\n"
            "atexit.register(_anvil_proc.terminate)\n"
            "\n"
            "# Wait for RPC to respond.\n"
            "for _ in range(30):\n"
            "    try:\n"
            "        run(['cast', 'block-number', '--rpc-url', RPC], check=True)\n"
            "        break\n"
            "    except SystemExit:\n"
            "        time.sleep(0.2)\n"
            "else:\n"
            "    raise RuntimeError('anvil did not come up')\n"
            "print(f'anvil PID={_anvil_proc.pid}')"
        ),
    ]
```

- [ ] **Step 3: Write `sections/s99_teardown.py`**

```python
"""§99 — Stop anvil and tidy up."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md("## Teardown\n\nKill the anvil process. Re-run this notebook from the top to start fresh."),
        code(
            "_anvil_proc.terminate()\n"
            "_anvil_proc.wait(timeout=5)\n"
            "print('anvil stopped')"
        ),
    ]
```

- [ ] **Step 4: Write `build_notebook.py`**

```python
"""Assemble 01a0_blockchain_primer.ipynb from sections/*.py modules."""
from __future__ import annotations
import importlib, pathlib, nbformat

HERE = pathlib.Path(__file__).parent
NB_PATH = HERE / "01a0_blockchain_primer.ipynb"

SECTION_MODULES = [
    "sections.s00_setup",
    "sections.s01_chain",
    "sections.s02_accounts",
    "sections.s03_transactions",
    "sections.s04_state_history",
    "sections.s05_deploy",
    "sections.s06_evm",
    "sections.s07_solidity",
    "sections.s08_events",
    "sections.s09_foundry",
    "sections.s10_escrow",
    "sections.s99_teardown",
]


def main() -> None:
    import sys
    sys.path.insert(0, str(HERE))
    nb = nbformat.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    cells: list = []
    for mod_name in SECTION_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            # Section not yet implemented — skip during incremental build.
            print(f"skip (missing): {mod_name}")
            continue
        cells.extend(mod.cells())
        print(f"  + {mod_name}: {len(mod.cells())} cells")
    nb.cells = cells
    nbformat.write(nb, NB_PATH)
    print(f"wrote {NB_PATH} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Build the (still-stub) notebook**

Run: `uv run python notebooks/blockchain_primer/build_notebook.py`
Expected: prints `+ sections.s00_setup`, `+ sections.s99_teardown`, several `skip (missing)` lines, and `wrote .../01a0_blockchain_primer.ipynb`.

- [ ] **Step 6: Execute the stub end-to-end (verifies anvil lifecycle works)**

Run:
```bash
uv run jupyter nbconvert --to notebook --execute --inplace \
  notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: exit 0. Open the notebook to confirm anvil started and stopped cleanly.

- [ ] **Step 7: Commit**

```bash
git add notebooks/blockchain_primer/sections notebooks/blockchain_primer/build_notebook.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): notebook builder + setup/teardown sections"
```

---

## Task 4: §1 What is a chain

**Files:**
- Create: `notebooks/blockchain_primer/sections/s01_chain.py`
- Modify (rebuild): `notebooks/blockchain_primer/01a0_blockchain_primer.ipynb`

- [ ] **Step 1: Write `sections/s01_chain.py`**

```python
"""§1 — What is a chain, really."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 1. What is a chain, really\n"
            "\n"
            "You already know the intuition: a blockchain is an append-only "
            "distributed database of transactions. Let's make that concrete.\n"
            "\n"
            "We started `anvil` — a process that pretends to be the entire Ethereum "
            "network. One node, no peers, no proof-of-stake. It exposes the same "
            "JSON-RPC interface mainnet does, on `http://127.0.0.1:8545`.\n"
            "\n"
            "The chain has two things we'll keep separate in our heads:\n"
            "\n"
            "1. **State** — current balances and contract storage (the \"database\").\n"
            "2. **History** — the ordered list of blocks, each containing the "
            "   transactions that produced the next state.\n"
            "\n"
            "Let's poke at both."
        ),
        code(
            "block_number = run(['cast', 'block-number', '--rpc-url', RPC])\n"
            "print(f'\\ncurrent block number: {block_number}')"
        ),
        code(
            "# The block itself. Block 0 is the genesis block — empty, no parent.\n"
            "run(['cast', 'block', '0', '--rpc-url', RPC])"
        ),
        md(
            "Notice the fields: `number`, `timestamp`, `parentHash`, "
            "`stateRoot`, `transactionsRoot`. Each block points to its parent "
            "by hash — that's the \"chain\" part. The `stateRoot` is a Merkle "
            "root summarising the entire state at this block — change one "
            "balance, the root changes, and so does the block hash."
        ),
    ]
```

- [ ] **Step 2: Rebuild the notebook**

Run: `uv run python notebooks/blockchain_primer/build_notebook.py`
Expected: `+ sections.s01_chain: 4 cells`.

- [ ] **Step 3: Execute end-to-end**

Run: `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add notebooks/blockchain_primer/sections/s01_chain.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §1 what is a chain"
```

---

## Task 5: §2 Accounts & keys

**Files:**
- Create: `notebooks/blockchain_primer/sections/s02_accounts.py`

- [ ] **Step 1: Write `sections/s02_accounts.py`**

Anvil's default mnemonic is deterministic. Account 0 is always `0xf39F...2266` with private key `0xac09...ff80`. We hardcode these so prose matches execution.

```python
"""§2 — Accounts & keys."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 2. Accounts & keys\n"
            "\n"
            "An Ethereum **account** is just a keypair. Anvil generates 10 funded "
            "accounts deterministically on startup — same mnemonic every time, so "
            "the addresses and private keys are stable across runs.\n"
            "\n"
            "We'll use these two throughout:\n"
            "\n"
            "| Role | Address | Private key |\n"
            "|---|---|---|\n"
            "| Alice (acct 0) | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` | `0xac0974...ff80` |\n"
            "| Bob (acct 1) | `0x70997970C51812dc3A010C7d01b50e0d17dc79C8` | `0x59c699...690d` |\n"
            "\n"
            "(Full keys are below — these are well-known test keys. **Never use them on a real network.**)"
        ),
        code(
            "ALICE = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266'\n"
            "ALICE_PK = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'\n"
            "BOB   = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'\n"
            "BOB_PK = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'\n"
            "\n"
            "# Derive Alice's address from her private key to prove the link.\n"
            "derived = run(['cast', 'wallet', 'address', ALICE_PK])\n"
            "assert derived.lower().endswith(ALICE[2:].lower()), (derived, ALICE)\n"
            "print('derived address matches Alice')"
        ),
        md(
            "**How the address is derived:** take the public key, hash it with "
            "`keccak256`, keep the last 20 bytes. That's it. No central registry, "
            "no certificate authority. Whoever holds the private key controls the "
            "account because only they can produce signatures that verify against "
            "the public key.\n"
            "\n"
            "The private key never leaves the holder. Signing happens locally; only "
            "the signature goes on-chain."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both commands exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s02_accounts.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §2 accounts & keys"
```

---

## Task 6: §3 A transaction (signing, hash, receipt)

**Files:**
- Create: `notebooks/blockchain_primer/sections/s03_transactions.py`

- [ ] **Step 1: Write `sections/s03_transactions.py`**

```python
"""§3 — A transaction, the smallest unit."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 3. A transaction, the smallest unit\n"
            "\n"
            "A transaction is the only way to change state. Even deploying a "
            "contract or running a function is just \"send a tx.\"\n"
            "\n"
            "We're going to send 1 ETH from Alice to Bob. Three things happen:\n"
            "\n"
            "1. Alice signs the tx **locally** with her private key.\n"
            "2. The signed bytes are sent to anvil over JSON-RPC.\n"
            "3. anvil includes the tx in a block. The tx now exists forever; the "
            "   state (balances) is updated accordingly."
        ),
        code(
            "# Send 1 ETH from Alice to Bob. --private-key tells cast which key to sign with.\n"
            "tx_hash = run([\n"
            "    'cast', 'send', BOB, '--value', '1ether',\n"
            "    '--private-key', ALICE_PK, '--rpc-url', RPC,\n"
            "    '--json',\n"
            "])\n"
            "import json\n"
            "receipt = json.loads(tx_hash)\n"
            "tx_hash = receipt['transactionHash']\n"
            "print(f'\\ntx hash: {tx_hash}')"
        ),
        md(
            "The **transaction hash** is `keccak256(rlp(signed_tx))` — a "
            "content-addressed fingerprint. Changing any field of the tx changes "
            "the hash; that's how the network refers to txs without trusting any "
            "label.\n"
            "\n"
            "Let's pull the tx itself, then its receipt."
        ),
        code(
            "run(['cast', 'tx', tx_hash, '--rpc-url', RPC])"
        ),
        md(
            "Field-by-field:\n"
            "\n"
            "- **`from`** — recovered from the signature `(v, r, s)`, not sent explicitly.\n"
            "- **`to`** — Bob's address. If empty, this would be a contract deployment.\n"
            "- **`value`** — wei being transferred (1 ETH = 10¹⁸ wei).\n"
            "- **`nonce`** — counter per sender; prevents replay. Alice's first tx is nonce 0.\n"
            "- **`gas`, `gasPrice`** — the fee budget.\n"
            "- **`input`** — empty for a plain transfer; we'll see it filled later.\n"
            "- **`v`, `r`, `s`** — the ECDSA signature.\n"
            "\n"
            "The **receipt** is the post-execution summary."
        ),
        code(
            "run(['cast', 'receipt', tx_hash, '--rpc-url', RPC])"
        ),
        md(
            "`status` `1` means success. `gasUsed` is what Alice actually paid for "
            "in computational work. `logs` is empty here (a transfer emits none) — "
            "we'll see logs in §8 when we discuss events."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s03_transactions.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §3 transactions"
```

---

## Task 7: §4 State vs history

**Files:**
- Create: `notebooks/blockchain_primer/sections/s04_state_history.py`

- [ ] **Step 1: Write `sections/s04_state_history.py`**

```python
"""§4 — State vs history."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 4. State vs history\n"
            "\n"
            "Two clocks tick in parallel:\n"
            "\n"
            "- **State** — the current snapshot. \"Alice has X wei.\" Mutable. "
            "  Read via `cast balance`, `cast storage`, contract view calls.\n"
            "- **History** — the chain of blocks, each containing the txs that produced "
            "  the next state. Immutable. Read via `cast block`, `cast tx`, `cast receipt`.\n"
            "\n"
            "The state is *derived* from the history: replay every tx from genesis "
            "and you get the current state. That's why the chain is auditable."
        ),
        code(
            "# Current balances\n"
            "alice_bal = run(['cast', 'balance', ALICE, '--rpc-url', RPC])\n"
            "bob_bal   = run(['cast', 'balance', BOB,   '--rpc-url', RPC])\n"
            "print(f'\\nAlice: {alice_bal} wei')\n"
            "print(f'Bob:   {bob_bal} wei')"
        ),
        code(
            "# Same question, but as of block 0 (before the transfer in §3).\n"
            "alice_bal0 = run(['cast', 'balance', ALICE, '--block', '0', '--rpc-url', RPC])\n"
            "bob_bal0   = run(['cast', 'balance', BOB,   '--block', '0', '--rpc-url', RPC])\n"
            "print(f'\\nAlice @ block 0: {alice_bal0} wei')\n"
            "print(f'Bob   @ block 0: {bob_bal0} wei')"
        ),
        md(
            "Notice: the *historical* balances differ from the current ones. That's "
            "the point — the chain remembers every state it ever held, because it "
            "remembers every tx.\n"
            "\n"
            "(Anvil keeps full archive state by default. Real Ethereum nodes can "
            "drop historical state to save disk, but the txs themselves never go away.)"
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s04_state_history.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §4 state vs history"
```

---

## Task 8: §5 Deploy Counter.sol

**Files:**
- Create: `notebooks/blockchain_primer/sections/s05_deploy.py`

- [ ] **Step 1: Write `sections/s05_deploy.py`**

```python
"""§5 — Deploying code: Counter.sol."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 5. From transactions to code: deploying `Counter.sol`\n"
            "\n"
            "Until now, our txs only moved ETH. The next leap: a tx can also "
            "**deploy code**. A *smart contract* is just an account whose `code` "
            "field is non-empty. When you send a tx to it, the EVM runs that code.\n"
            "\n"
            "We'll deploy this tiny contract (see `contracts/Counter.sol`):\n"
            "\n"
            "```solidity\n"
            "contract Counter {\n"
            "    uint256 public number;\n"
            "    function increment() external { number += 1; }\n"
            "    function incrementBounded() external {\n"
            "        require(number < 5, \"max reached\");\n"
            "        number += 1;\n"
            "    }\n"
            "}\n"
            "```\n"
            "\n"
            "First, compile it with `forge build`."
        ),
        code(
            "run(['forge', 'build'])"
        ),
        code(
            "# Deploy. `forge create` sends a creation tx (no `to`, code in `input`).\n"
            "output = run([\n"
            "    'forge', 'create', 'contracts/Counter.sol:Counter',\n"
            "    '--private-key', ALICE_PK, '--rpc-url', RPC,\n"
            "    '--broadcast',\n"
            "])\n"
            "# Extract the deployed address from forge's output.\n"
            "import re\n"
            "m = re.search(r'Deployed to:\\s*(0x[0-9a-fA-F]{40})', output)\n"
            "assert m, output\n"
            "COUNTER = m.group(1)\n"
            "print(f'\\nCounter deployed at: {COUNTER}')"
        ),
        code(
            "# Confirm: the deployed account has CODE. A regular EOA does not.\n"
            "counter_code = run(['cast', 'code', COUNTER, '--rpc-url', RPC])\n"
            "alice_code   = run(['cast', 'code', ALICE,   '--rpc-url', RPC])\n"
            "print(f'\\nCounter code length: {len(counter_code)} chars')\n"
            "print(f'Alice code:          {alice_code!r}  (empty)')"
        ),
        md(
            "That's it. **A smart contract is an account with code.** The code is "
            "EVM bytecode — a stack-machine instruction stream. When the network "
            "sees a tx whose `to` is this address, every node runs the bytecode "
            "against the input, applies the resulting state changes, and agrees on "
            "the outcome (because the EVM is deterministic)."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s05_deploy.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §5 deploy Counter.sol"
```

---

## Task 9: §6 EVM execution — send vs call, gas, revert

**Files:**
- Create: `notebooks/blockchain_primer/sections/s06_evm.py`

- [ ] **Step 1: Write `sections/s06_evm.py`**

```python
"""§6 — EVM execution: send vs call, gas, revert."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 6. EVM execution: `send` vs `call`, gas, revert\n"
            "\n"
            "Two ways to interact with a deployed contract:\n"
            "\n"
            "- **`cast send`** — sends a real, signed tx. State changes. Costs gas. "
            "  Mined into a block.\n"
            "- **`cast call`** — a *local simulation*. The node runs the function "
            "  against current state but discards the result. No tx, no block, no "
            "  gas paid. Used for reading view functions or previewing a call's "
            "  return value.\n"
            "\n"
            "Let's increment, then read."
        ),
        code(
            "run(['cast', 'send', COUNTER, 'increment()',\n"
            "     '--private-key', ALICE_PK, '--rpc-url', RPC])"
        ),
        code(
            "n = run(['cast', 'call', COUNTER, 'number()(uint256)', '--rpc-url', RPC])\n"
            "print(f'\\nnumber() = {n}')"
        ),
        md(
            "The receipt for the `increment` tx had a `gasUsed` field — that's the "
            "EVM measuring how much computational work the function did. Every "
            "opcode (ADD, SSTORE, etc.) has a fixed gas cost; the tx's gas budget "
            "must cover the total.\n"
            "\n"
            "**Revert.** When a contract calls `require(...)` or `revert(...)` and "
            "the condition fails, all state changes from that tx are undone. The "
            "tx still gets mined and consumes gas, but its receipt has `status: 0`. "
            "Let's see it."
        ),
        code(
            "# Push number up to 5, then try a 6th increment which should revert.\n"
            "for _ in range(4):\n"
            "    run(['cast', 'send', COUNTER, 'incrementBounded()',\n"
            "         '--private-key', ALICE_PK, '--rpc-url', RPC])\n"
            "n = run(['cast', 'call', COUNTER, 'number()(uint256)', '--rpc-url', RPC])\n"
            "print(f'\\nnumber() = {n}  (expect 5)')"
        ),
        code(
            "# The 6th call should revert with \"max reached\".\n"
            "# We pass check=False because we expect a non-zero exit.\n"
            "run(['cast', 'send', COUNTER, 'incrementBounded()',\n"
            "     '--private-key', ALICE_PK, '--rpc-url', RPC], check=False)"
        ),
        code(
            "# State unchanged — still 5.\n"
            "n = run(['cast', 'call', COUNTER, 'number()(uint256)', '--rpc-url', RPC])\n"
            "print(f'\\nnumber() after revert = {n}  (still 5)')"
        ),
        md(
            "Revert is the contract's safety hatch: any invalid condition unwinds "
            "the whole tx atomically. You'll see `BandwidthEscrow` use this "
            "extensively — every state-machine violation is a `revert WrongStatus(...)`."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s06_evm.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §6 EVM execution, gas, revert"
```

---

## Task 10: §7 Solidity syntax via HelloWorld.sol

**Files:**
- Create: `notebooks/blockchain_primer/sections/s07_solidity.py`

- [ ] **Step 1: Write `sections/s07_solidity.py`**

```python
"""§7 — Solidity syntax via HelloWorld.sol → mapped to BandwidthEscrow."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 7. Solidity syntax via `HelloWorld.sol`\n"
            "\n"
            "Time to read Solidity, not just call it. `HelloWorld.sol` is tiny but "
            "uses every feature `BandwidthEscrow` does. We'll deploy it, exercise "
            "each feature, and map it to where the same feature appears in the real "
            "escrow contract.\n"
            "\n"
            "```solidity\n"
            "contract HelloWorld {\n"
            "    address public owner;\n"
            "    mapping(address => uint256) public greetings;\n"
            "\n"
            "    event Greeted(address indexed who, uint256 count);\n"
            "    error NotOwner();\n"
            "    error SendSomething();\n"
            "\n"
            "    constructor() { owner = msg.sender; }\n"
            "\n"
            "    function greet() external payable {\n"
            "        if (msg.value == 0) revert SendSomething();\n"
            "        greetings[msg.sender] += 1;\n"
            "        emit Greeted(msg.sender, greetings[msg.sender]);\n"
            "    }\n"
            "\n"
            "    function withdraw() external {\n"
            "        if (msg.sender != owner) revert NotOwner();\n"
            "        (bool ok, ) = msg.sender.call{value: address(this).balance}(\"\");\n"
            "        require(ok, \"transfer failed\");\n"
            "    }\n"
            "}\n"
            "```"
        ),
        code(
            "output = run([\n"
            "    'forge', 'create', 'contracts/HelloWorld.sol:HelloWorld',\n"
            "    '--private-key', ALICE_PK, '--rpc-url', RPC, '--broadcast',\n"
            "])\n"
            "import re\n"
            "m = re.search(r'Deployed to:\\s*(0x[0-9a-fA-F]{40})', output)\n"
            "assert m, output\n"
            "HELLO = m.group(1)\n"
            "print(f'\\nHelloWorld at: {HELLO}')"
        ),
        code(
            "# Alice greets twice, paying 0.1 ETH each time.\n"
            "for _ in range(2):\n"
            "    run(['cast', 'send', HELLO, 'greet()', '--value', '0.1ether',\n"
            "         '--private-key', ALICE_PK, '--rpc-url', RPC])\n"
            "\n"
            "# Read her greet count from the mapping.\n"
            "count = run(['cast', 'call', HELLO, 'greetings(address)(uint256)',\n"
            "             ALICE, '--rpc-url', RPC])\n"
            "print(f'\\nAlice greeted {count} times')"
        ),
        code(
            "# Owner check: Bob tries to withdraw, should revert NotOwner.\n"
            "run(['cast', 'send', HELLO, 'withdraw()',\n"
            "     '--private-key', BOB_PK, '--rpc-url', RPC], check=False)\n"
            "print('(Bob failed as expected)')"
        ),
        code(
            "# Alice withdraws successfully.\n"
            "run(['cast', 'send', HELLO, 'withdraw()',\n"
            "     '--private-key', ALICE_PK, '--rpc-url', RPC])\n"
            "bal = run(['cast', 'balance', HELLO, '--rpc-url', RPC])\n"
            "print(f'\\nHelloWorld balance: {bal} wei (should be 0)')"
        ),
        md(
            "### Feature map: HelloWorld → BandwidthEscrow\n"
            "\n"
            "| Concept | In HelloWorld | In BandwidthEscrow |\n"
            "|---|---|---|\n"
            "| `pragma solidity ^0.8.20;` | line 2 | line 2 |\n"
            "| `mapping(K => V)` | `greetings` | `_agreements` (id → Agreement) |\n"
            "| `struct` | — | `Agreement`, `TokenMetadata` |\n"
            "| `enum` | — | `Status { NONE, REQUESTED, ACTIVE, CLOSED, CANCELLED }` |\n"
            "| `event ... indexed` | `Greeted(address indexed who, uint256)` | `AgreementRequested(uint256 indexed, address indexed, address indexed, ...)` |\n"
            "| custom `error` + `revert Foo()` | `NotOwner`, `SendSomething` | `NotProvider`, `WrongStatus`, `MetadataMismatch`, … |\n"
            "| `msg.sender` | `withdraw()` ownership check | every function's authorization check |\n"
            "| `msg.value` + `payable` | `greet() external payable` | `requestAgreement(...) external payable` |\n"
            "| `block.timestamp` | — | `requestDeadline = block.timestamp + 1 hours` |\n"
            "| `external` vs `public` | both | all entry points `external` |\n"
            "| Low-level `call{value: ...}(\"\")` | `withdraw()` | `ag.provider.call{value: ag.priceWei}(\"\")` |\n"
            "| Constructor | sets `owner` | sets `nftContract` (immutable) |\n"
            "\n"
            "**Storage vs memory** (not exercised here, used in escrow): `storage` "
            "is a *reference* to on-chain state (writes persist). `memory` is a "
            "scratch copy for the duration of the call. In `deposit()` you'll see "
            "`Agreement storage ag = _agreements[id];` — writes to `ag.status` "
            "actually mutate the mapping."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s07_solidity.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §7 Solidity syntax via HelloWorld"
```

---

## Task 11: §8 Events — how off-chain code listens

**Files:**
- Create: `notebooks/blockchain_primer/sections/s08_events.py`

- [ ] **Step 1: Write `sections/s08_events.py`**

```python
"""§8 — Events: how off-chain code listens."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 8. Events: how off-chain code listens\n"
            "\n"
            "A contract can't push data anywhere — it has no network access. What "
            "it *can* do is emit an **event** during execution. Events become "
            "**logs** attached to the tx receipt and are indexed in a Bloom filter "
            "per block. Off-chain code subscribes to these logs over the JSON-RPC "
            "WebSocket interface (`eth_subscribe`) or polls them with `eth_getLogs`.\n"
            "\n"
            "We already emitted `Greeted` events in §7. Let's read them."
        ),
        code(
            "# Fetch all logs for HelloWorld since genesis.\n"
            "raw = run(['cast', 'logs',\n"
            "           '--address', HELLO,\n"
            "           '--from-block', '0',\n"
            "           '--rpc-url', RPC])"
        ),
        md(
            "Each log has:\n"
            "\n"
            "- **`address`** — contract that emitted it (`HELLO`).\n"
            "- **`topics[0]`** — `keccak256(\"Greeted(address,uint256)\")`. The event "
            "  *signature hash*. This is how you filter by event type without "
            "  knowing the contract's ABI.\n"
            "- **`topics[1..]`** — the `indexed` arguments (here: `who`). Indexed "
            "  args are stored as topics so they're searchable; non-indexed args "
            "  go in `data` and aren't.\n"
            "- **`data`** — ABI-encoded non-indexed args (here: `count`).\n"
            "\n"
            "Filter by indexed arg — \"give me only Greeted events where `who` is Alice\":"
        ),
        code(
            "# topics[0] = signature, topics[1] = padded Alice address.\n"
            "sig = run(['cast', 'keccak', 'Greeted(address,uint256)'])\n"
            "alice_topic = '0x' + '0' * 24 + ALICE[2:].lower()\n"
            "run(['cast', 'logs',\n"
            "     '--address', HELLO,\n"
            "     '--from-block', '0',\n"
            "     sig, alice_topic, '--rpc-url', RPC])"
        ),
        md(
            "### Why this matters for BandwidthEscrow\n"
            "\n"
            "`BandwidthEscrow` emits `AgreementRequested(uint256 indexed agreementId, "
            "address indexed consumer, address indexed provider, uint256 bandwidthMbps, "
            "uint256 durationSeconds, uint256 priceWei)`.\n"
            "\n"
            "Three fields are `indexed` — the EVM allows up to three (plus the "
            "signature) topics per log. The choice tells you what the contract "
            "expects to be *filtered on*:\n"
            "\n"
            "- `agreementId` — \"give me events for this specific agreement.\"\n"
            "- `consumer` — \"give me every request from this consumer.\"\n"
            "- `provider` — \"give me every request directed at this provider.\"\n"
            "\n"
            "This is exactly what the provider service in this repo does: it "
            "subscribes to `AgreementRequested` filtered on its own provider "
            "address, then reacts to each match by calling `deposit()`. That's the "
            "bridge between on-chain state and the off-chain agents — and now you "
            "know how the listening side actually works at the protocol level."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s08_events.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §8 events and off-chain listening"
```

---

## Task 12: §9 Foundry toolkit recap

**Files:**
- Create: `notebooks/blockchain_primer/sections/s09_foundry.py`

- [ ] **Step 1: Write `sections/s09_foundry.py`**

```python
"""§9 — Foundry toolkit recap."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 9. Foundry toolkit recap\n"
            "\n"
            "We've been using three tools without naming them properly:\n"
            "\n"
            "| Tool | What it is | Used in |\n"
            "|---|---|---|\n"
            "| **`anvil`** | Local Ethereum node — instant blocks, deterministic accounts. | §1 (background process) |\n"
            "| **`cast`** | RPC client + signing tool. Anything you can do over JSON-RPC, `cast` has a subcommand for. | §2–§8 |\n"
            "| **`forge`** | Build/test/deploy. Compiles Solidity, runs tests, scripts deployments. | §5, §7 |\n"
            "\n"
            "Now let's run `forge test` against the **real** project contracts to "
            "see the production test suite in action."
        ),
        code(
            "# Run from REPO_ROOT/contracts where the real project lives.\n"
            "run(['forge', 'test', '-vv'], cwd=REPO_ROOT / 'contracts')"
        ),
        md(
            "Each test is a Solidity function (in `contracts/test/`) that runs "
            "against a fresh EVM instance. `forge` reports pass/fail, gas used, "
            "and decoded revert reasons. The same `anvil` we've been using is "
            "what powers these tests under the hood."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

Before executing the notebook, confirm the project's `forge test` passes:
```bash
cd contracts && forge test && cd -
```
Expected: all tests pass.

Then:
```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s09_foundry.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §9 Foundry toolkit recap"
```

---

## Task 13: §10 Reading BandwidthEscrow end-to-end

**Files:**
- Create: `notebooks/blockchain_primer/sections/s10_escrow.py`

- [ ] **Step 1: Write `sections/s10_escrow.py`**

```python
"""§10 — Reading BandwidthEscrow end-to-end."""
from __future__ import annotations
from ._helpers import md, code


def cells() -> list[dict]:
    return [
        md(
            "## 10. Reading `BandwidthEscrow` end-to-end\n"
            "\n"
            "You now have every piece. Let's read the real contract. Open "
            "[`contracts/src/BandwidthEscrow.sol`](../../contracts/src/BandwidthEscrow.sol) "
            "in a split view and follow along.\n"
            "\n"
            "The contract mediates a swap: a consumer locks ETH, a provider deposits "
            "an NFT, and the contract atomically hands the NFT to the consumer and "
            "the ETH to the provider. State machine:\n"
            "\n"
            "```\n"
            "NONE  --requestAgreement(payable)-->  REQUESTED\n"
            "REQUESTED  --deposit(NFT)-->  ACTIVE\n"
            "REQUESTED  --cancel()-->  CANCELLED\n"
            "```"
        ),
        md(
            "### 10.1 `requestAgreement` — consumer locks ETH\n"
            "\n"
            "```solidity\n"
            "function requestAgreement(\n"
            "    uint256 agreementId, address provider,\n"
            "    uint256 bandwidthMbps, uint256 durationSeconds\n"
            ") external payable {\n"
            "    if (_agreements[agreementId].status != Status.NONE)\n"
            "        revert AgreementAlreadyExists(agreementId);\n"
            "    if (msg.value == 0) revert ZeroPriceNotAllowed();\n"
            "\n"
            "    _agreements[agreementId] = Agreement({\n"
            "        consumer: msg.sender, provider: provider,\n"
            "        bandwidthMbps: bandwidthMbps, durationSeconds: durationSeconds,\n"
            "        priceWei: msg.value,\n"
            "        requestDeadline: block.timestamp + 1 hours,\n"
            "        tokenId: 0, status: Status.REQUESTED\n"
            "    });\n"
            "    emit AgreementRequested(agreementId, msg.sender, provider, bandwidthMbps, durationSeconds, msg.value);\n"
            "}\n"
            "```\n"
            "\n"
            "Line by line, every keyword should now be familiar:\n"
            "\n"
            "- `external payable` — only callable from outside; accepts ETH (§7).\n"
            "- `_agreements[agreementId].status != Status.NONE` — mapping lookup (§7); the default value of a missing key is the zero struct, whose `status` is `NONE` (the first enum variant), so this rejects duplicates.\n"
            "- `revert AgreementAlreadyExists(agreementId)` — custom error with parameters; cheaper than `require` with a string (§7, §6).\n"
            "- `msg.value == 0` — the ETH the caller sent (§7); zero would mean a free agreement, disallowed.\n"
            "- `msg.sender` — the consumer's address, recovered from the tx signature (§3, §7).\n"
            "- `block.timestamp + 1 hours` — anvil/EVM time in seconds; `1 hours = 3600` (§4 timestamps in blocks).\n"
            "- `emit AgreementRequested(...)` — writes a log so the provider can react off-chain (§8).\n"
            "\n"
            "**Why the deadline?** If the provider never deposits, the consumer's "
            "ETH would be stuck. After `requestDeadline`, *anyone* can call "
            "`cancel()` (see 10.3) — a permissionless escape hatch."
        ),
        md(
            "### 10.2 `deposit` — provider settles, atomic swap\n"
            "\n"
            "```solidity\n"
            "function deposit(uint256 agreementId, uint256 tokenId) external {\n"
            "    Agreement storage ag = _agreements[agreementId];\n"
            "\n"
            "    // ── Checks ────────────────────────────────────────────────────\n"
            "    if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);\n"
            "    if (msg.sender != ag.provider) revert NotProvider();\n"
            "    if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);\n"
            "\n"
            "    BandwidthNFT.TokenMetadata memory meta = nftContract.getTokenMetadata(tokenId);\n"
            "    if (meta.agreementId != agreementId || ...) revert MetadataMismatch();\n"
            "\n"
            "    // ── Effects ───────────────────────────────────────────────────\n"
            "    ag.status = Status.ACTIVE;\n"
            "    ag.tokenId = tokenId;\n"
            "\n"
            "    // ── Interactions ──────────────────────────────────────────────\n"
            "    nftContract.safeTransferFrom(msg.sender, address(this), tokenId);\n"
            "    nftContract.safeTransferFrom(address(this), ag.consumer, tokenId);\n"
            "    (bool ok,) = ag.provider.call{value: ag.priceWei}(\"\");\n"
            "    if (!ok) revert ETHTransferFailed();\n"
            "\n"
            "    emit AgreementActive(agreementId, tokenId, ag.consumer, ag.provider);\n"
            "}\n"
            "```\n"
            "\n"
            "Two things to notice:\n"
            "\n"
            "**1. `Agreement storage ag = ...` is a reference.** Writes to `ag.status` "
            "mutate the mapping entry directly. If you'd written `Agreement memory ag` "
            "you'd be modifying a local copy and the state change would be lost.\n"
            "\n"
            "**2. Checks → Effects → Interactions.** Status flips to `ACTIVE` "
            "*before* any external call. Why? The low-level `call{value: ...}` "
            "hands control to the provider. If the provider is itself a contract, "
            "its `receive()` function could re-enter `deposit()` for the same "
            "`agreementId`. Because we already set `status = ACTIVE`, the "
            "re-entered call hits `WrongStatus` and reverts. This is the "
            "**reentrancy guard** baked into the function's structure — no extra "
            "library needed.\n"
            "\n"
            "The atomic swap is the two `safeTransferFrom` calls + the ETH `call`: "
            "either everything happens or nothing happens (any revert undoes the whole tx, §6)."
        ),
        md(
            "### 10.3 `cancel` — refund path\n"
            "\n"
            "```solidity\n"
            "function cancel(uint256 agreementId) external {\n"
            "    Agreement storage ag = _agreements[agreementId];\n"
            "    if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);\n"
            "    if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);\n"
            "\n"
            "    bool isConsumer = msg.sender == ag.consumer;\n"
            "    bool deadlinePassed = block.timestamp > ag.requestDeadline;\n"
            "    if (!isConsumer && !deadlinePassed) revert DeadlineNotPassed();\n"
            "\n"
            "    address consumer = ag.consumer;\n"
            "    uint256 refund = ag.priceWei;\n"
            "    ag.status = Status.CANCELLED;            // effect before interaction\n"
            "    (bool ok,) = consumer.call{value: refund}(\"\");\n"
            "    if (!ok) revert ETHTransferFailed();\n"
            "    emit AgreementCancelled(agreementId, consumer);\n"
            "}\n"
            "```\n"
            "\n"
            "Two-tier authorization: the consumer can always cancel while "
            "`REQUESTED`; anyone else only after the deadline. Same CEI ordering — "
            "status flipped to `CANCELLED` before the refund leaves the contract.\n"
            "\n"
            "---\n"
            "\n"
            "**You're done.** The reference doc you'll want open while reading "
            "future contracts is [01a — chain contract model](../01a_chain_contract_model.ipynb), "
            "and the lifecycle walkthrough is [01b — escrow lifecycle](../01b_chain_escrow_lifecycle.ipynb)."
        ),
    ]
```

- [ ] **Step 2: Rebuild + execute**

```bash
uv run python notebooks/blockchain_primer/build_notebook.py
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add notebooks/blockchain_primer/sections/s10_escrow.py notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "feat(primer): §10 reading BandwidthEscrow end-to-end"
```

---

## Task 14: Final end-to-end verification + index update

**Files:**
- Modify: `notebooks/README.md` (add primer link)
- Verify: `notebooks/blockchain_primer/01a0_blockchain_primer.ipynb`

- [ ] **Step 1: Cold rebuild — delete and regenerate notebook from scratch**

```bash
rm notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
uv run python notebooks/blockchain_primer/build_notebook.py
```
Expected: notebook written with all 12 section modules contributing cells (no `skip (missing)` lines).

- [ ] **Step 2: Confirm no anvil process is already running on 8545**

Run: `lsof -ti :8545 || echo "port free"`
Expected: `port free`. If a stray anvil is running, kill it: `lsof -ti :8545 | xargs -r kill`.

- [ ] **Step 3: Cold execute the notebook end-to-end**

```bash
uv run jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=120 \
  notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
```
Expected: exit 0. Open the notebook in Jupyter or VSCode to spot-check each section renders correctly.

- [ ] **Step 4: Confirm anvil was cleaned up**

Run: `lsof -ti :8545 || echo "port free"`
Expected: `port free`.

- [ ] **Step 5: Add a pointer to the primer in `notebooks/README.md`**

Read the current `notebooks/README.md` to find the right insertion point (probably near the top of the notebook list). Add a line that links to the primer as a prerequisite for `01a` for blockchain newcomers, for example:

```markdown
- **[blockchain_primer/](blockchain_primer/)** — Ground-up primer for blockchain newcomers. Run before `01a` if you've never deployed a contract.
```

- [ ] **Step 6: Commit**

```bash
git add notebooks/README.md notebooks/blockchain_primer/01a0_blockchain_primer.ipynb
git commit -m "docs(primer): link primer from notebooks/README"
```

---

## Self-Review Summary

**Spec coverage:**
- §1 What is a chain → Task 4 ✓
- §2 Accounts & keys → Task 5 ✓
- §3 A transaction → Task 6 ✓
- §4 State vs history → Task 7 ✓
- §5 Deploying Counter → Task 8 ✓
- §6 EVM execution → Task 9 ✓
- §7 Solidity via HelloWorld → Task 10 ✓
- §8 Events → Task 11 ✓
- §9 Foundry recap → Task 12 ✓
- §10 Reading BandwidthEscrow → Task 13 ✓
- Folder layout (contracts/, foundry.toml, README) → Tasks 1–2 ✓
- Builder pattern + atexit anvil cleanup → Task 3 ✓
- Acceptance criteria verified by end-to-end execution → Task 14 ✓

**Placeholder scan:** clean — every section module has full cell content; every command has an expected result.

**Type/name consistency:** `run()` signature stable across all sections; constants (`ALICE`, `BOB`, `ALICE_PK`, `BOB_PK`, `COUNTER`, `HELLO`, `RPC`, `REPO_ROOT`, `PRIMER_DIR`) declared in `s00_setup`/`s02_accounts`/`s05_deploy`/`s07_solidity` and only referenced after their declaring section.
