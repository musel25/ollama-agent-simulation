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
