# Blockchain From Scratch

A 10-notebook series that builds every important Ethereum primitive — including the network layer — by hand in Python. No web3.py, no Flask, no shortcuts. Stops just before real Solidity development (see `../blockchain_primer/`).

Authored as [marimo](https://marimo.io) reactive notebooks — plain Python files, clean git diffs, no hidden state.

## Order

| # | Notebook | What you build |
|---|----------|----------------|
| 00 | [`00_foundations.py`](00_foundations.py) | Bytes, hex, big-ints, mod arithmetic |
| 01 | [`01_keys_and_addresses.py`](01_keys_and_addresses.py) | secp256k1 keygen, keccak256, Ethereum addresses |
| 02 | [`02_signing_a_transaction.py`](02_signing_a_transaction.py) | RLP, EIP-1559 tx, ECDSA sign + recover |
| 03 | [`03_broadcast_to_sepolia.py`](03_broadcast_to_sepolia.py) *(optional)* | Send your hand-signed tx to a real testnet |
| 04 | [`04_toy_blockchain.py`](04_toy_blockchain.py) | Blocks, state, parent-hash linking, validation |
| 05 | [`05_networking_from_scratch.py`](05_networking_from_scratch.py) | TCP sockets, length-prefixed framing, JSON-RPC by hand, **debugging with `nc` and `tcpdump`** |
| 06 | [`06_p2p_node_protocol.py`](06_p2p_node_protocol.py) | Real TCP peer connections, handshake, sqrt-fanout gossip |
| 07 | [`07_fork_choice_and_reorgs.py`](07_fork_choice_and_reorgs.py) | Competing chains, longest-chain rule, debugging reorgs |
| 08 | [`08_merkle_patricia_trie.py`](08_merkle_patricia_trie.py) | State root + inclusion proofs (RLP-hashed nodes) |
| 09 | [`09_toy_evm.py`](09_toy_evm.py) | Interpreter for ~25 opcodes, reads real deployed bytecode |

## Setup

```bash
uv sync --extra from-scratch
uv run marimo edit notebooks/from_scratch/
```

You also need these CLI tools installed for the networking notebooks (NB05+):
- `nc` (netcat) — usually preinstalled
- `tcpdump` — `sudo apt install tcpdump` on Debian/Ubuntu
- Optional: Wireshark for pretty packet dissection

Run notebooks **in order** — later ones import code defined earlier into `_lib/`.

## Where each concept reappears in real Ethereum

| This series | Mainnet equivalent |
|---|---|
| NB01 keccak + secp256k1 keygen | Every wallet on every chain |
| NB02 RLP + EIP-1559 signing | `eth_sendRawTransaction` payload bodies |
| NB04 toy `Chain.propose` | Geth/Reth block production |
| NB05 length-prefixed framing | RLPx (the encrypted devp2p transport) |
| NB06 sqrt-fanout gossip | `eth/68` `Transactions` + `NewPooledTransactionHashes` |
| NB07 longest-chain rule | LMD-GHOST + Casper FFG (post-Merge consensus) |
| NB08 RLP-hashed trie | The Merkle-Patricia state trie in `core/state` |
| NB09 toy EVM opcodes | The full ~140-opcode EVM in `core/vm` |

## What's next

When you finish NB09, your next step is real Solidity — go to **[../blockchain_primer/](../blockchain_primer/)** for Foundry, `cast`, and a guided read of an actual deployed contract.

After that, for production smart-contract development:

- **[Cyfrin Updraft](https://updraft.cyfrin.io/)** — free, high-quality video courses by Patrick Collins covering Solidity + Foundry.
- **[Solidity by Example](https://solidity-by-example.org/)** — concise runnable patterns.
- **[Ethernaut](https://ethernaut.openzeppelin.com/)** — gamified Solidity security challenges (easier on-ramp).
- **[Damn Vulnerable DeFi](https://www.damnvulnerabledefi.xyz/)** — CTF exploiting broken DeFi contracts; teaches security by attack.

For protocol-level depth: read a real client codebase. **[Reth](https://github.com/paradigmxyz/reth)** (Rust) is the most readable; **[Geth](https://github.com/ethereum/go-ethereum)** (Go) is the reference. Start tracing from `eth_sendRawTransaction` — you'll recognize most of what's happening from NB02–NB07.
