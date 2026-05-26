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
