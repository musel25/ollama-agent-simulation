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
