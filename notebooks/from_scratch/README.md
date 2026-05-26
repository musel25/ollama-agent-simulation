# Blockchain From Scratch

A 10-notebook series that builds every important Ethereum primitive — including the network layer — by hand in Python. No web3.py, no Flask, no shortcuts. Stops just before real Solidity development (see `../blockchain_primer/`).

## Order

| # | Notebook | What you build |
|---|----------|----------------|
| 00 | Foundations | Bytes, hex, big-ints, mod arithmetic |
| 01 | Keys & Addresses | secp256k1 keygen, keccak256, Ethereum addresses |
| 02 | Signing a Transaction | RLP, EIP-1559 tx, ECDSA sign + recover |
| 03 | Broadcast to Sepolia *(optional)* | Send your hand-signed tx to a real testnet |
| 04 | Toy Blockchain | Blocks, state, parent-hash linking, validation |
| 05 | Networking From Scratch | TCP sockets, length-prefixed framing, JSON-RPC by hand, **debugging with `nc` and `tcpdump`** |
| 06 | P2P Node Protocol | Real TCP peer connections, handshake, sqrt-fanout gossip |
| 07 | Fork Choice & Reorgs | Competing chains, longest-chain rule, debugging reorgs |
| 08 | Merkle-Patricia Trie | State root + inclusion proofs (RLP-hashed nodes) |
| 09 | Toy EVM | Interpreter for ~25 opcodes, reads real deployed bytecode |

## Setup

```bash
uv sync --extra from-scratch
uv run jupyter lab notebooks/from_scratch/
```

You also need these CLI tools installed for the networking notebooks (NB05+):
- `nc` (netcat) — usually preinstalled
- `tcpdump` — `sudo apt install tcpdump` on Debian/Ubuntu
- Optional: Wireshark for pretty packet dissection

Run notebooks **in order** — later ones import code defined earlier into `_lib/`.
