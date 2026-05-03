# Bandwidth Agent Simulation

> Two AI agents negotiate and pay for internet bandwidth — entirely on-chain, running on your laptop.

A working proof-of-concept where a **Consumer AI** and a **Provider AI** interact using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), an Agent-to-Agent (A2A) protocol, and an Ethereum smart-contract escrow. Settles a real trade (no real money, no real bandwidth — local Anvil chain, mock or real SDN).

This README is a landing page. The full documentation lives in [`docs/`](docs/).

---

## Quickstart

```bash
# 1. Install prereqs (see docs/05-running.md for details):
#    Foundry, Docker, Ollama, uv

# 2. Copy the example env file
cp .env.example .env

# 3. Bring everything up
make up

# 4. Open the UI
xdg-open http://localhost:8501   # or just open it in your browser

# 5. Try the scripted demo (no browser needed)
make demo
```

If `make demo` reports an active service with a `tokenId`, the whole stack works.

To stop everything: `make down` (or `make down-clean` to wipe state too).

---

## Where to read next

| If you want to... | Read |
|---|---|
| Understand what this is and why it exists | [`docs/01-introduction.md`](docs/01-introduction.md) |
| Learn the words used in everything else | [`docs/02-concepts.md`](docs/02-concepts.md) |
| See a successful run, stage by stage | [`docs/03-walkthrough.md`](docs/03-walkthrough.md) |
| Read or modify the code | [`docs/04-architecture.md`](docs/04-architecture.md) |
| Get it running on your machine | [`docs/05-running.md`](docs/05-running.md) |
| Change something safely | [`docs/06-modifying.md`](docs/06-modifying.md) |
| Understand how the code maps to the paper | [`docs/paper-alignment.md`](docs/paper-alignment.md) |

If you've never seen this project before: read those docs in the order listed.

---

## Repo layout

```
.
├── consumer/         # Buyer agent: FastAPI + Ollama + MCP client + A2A client
├── provider/         # Seller agent: FastAPI + MCP server + A2A executor + SDN tools
├── shared/           # Cross-agent code: A2A message types, ABIs, slot pool
├── contracts/        # Solidity contracts (BandwidthEscrow + BandwidthNFT) + Foundry scripts
├── tests/            # Pytest suite covering all of the above
├── docs/             # This documentation set
└── paper/            # Companion research paper (separate git repo)
```

---

## Tech at a glance

- **Python 3.13** with `uv` for environment management
- **FastAPI** for the agent HTTP servers, **Streamlit** for the UI
- **FastMCP** for the MCP servers, **a2a-sdk** for inter-agent calls
- **Ollama** running `qwen3:4b` locally (swappable; see [`docs/05-running.md`](docs/05-running.md))
- **Solidity 0.8.x** + **Foundry/Anvil** for the smart-contract layer
- **`tc tbf`** + **gNMI** for SDN bandwidth enforcement (mock by default; real path uses [`srl-gnmi-bandwidth-poc`](https://github.com/musel25/srl-gnmi-bandwidth-poc))

---

## Status

Active prototype on the `feat/mcp-a2a` branch. Companion to a research paper currently in progress (see `paper/`).
