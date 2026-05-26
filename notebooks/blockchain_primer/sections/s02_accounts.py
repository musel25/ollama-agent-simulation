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
