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
