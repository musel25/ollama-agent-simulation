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
            "`forge` also runs Solidity-native tests. The real project hasn't added any "
            "yet, so the next cell will print `No tests found in project!` — that's "
            "`forge` telling you the test directory is empty, not an error. Once tests "
            "exist in `contracts/test/*.t.sol`, the same command runs them."
        ),
        code(
            "# Run from REPO_ROOT/contracts where the real project lives.\n"
            "run(['forge', 'test', '-vv'], cwd=REPO_ROOT / 'contracts')"
        ),
        md(
            "When tests exist, each one is a Solidity function in `contracts/test/*.t.sol` "
            "that runs against a fresh EVM instance. `forge` reports pass/fail, gas used, "
            "and decoded revert reasons. The same `anvil` we've been using is what powers "
            "these tests under the hood."
        ),
    ]
