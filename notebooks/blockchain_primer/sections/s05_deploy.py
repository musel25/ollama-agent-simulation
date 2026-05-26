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
