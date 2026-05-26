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
