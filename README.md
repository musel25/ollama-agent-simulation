# Bandwidth Agent Simulation

> Two AI agents negotiate and pay for internet bandwidth — entirely on-chain, running on your laptop.

A working proof-of-concept where a **Consumer AI** and a **Provider AI** interact using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), an Agent-to-Agent (A2A) protocol, and an Ethereum smart-contract escrow. Settles a real trade (no real money, no real bandwidth — local Anvil chain, mock or real SDN).

This README is a landing page. The full documentation lives in [`docs/`](docs/).

---

## Two ways to run

- **Docker stack** (below): one command brings up Anvil, the agents, Ollama, and the dashboard.
- **Notebooks** (`notebooks/*.py`, [marimo](https://marimo.io)): every layer in-process from Python; no Docker. See [`notebooks/README.md`](notebooks/README.md).

---

## Quickstart

```bash
# 1. Install prereqs (see docs/04-running.md for details):
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

### Real SDN demo (optional)

The default demo uses a mocked SDN layer (`SDN_MOCK=true`). To exercise real bandwidth enforcement (gNMI policer push to Nokia SR Linux + `tc tbf` on the connected CE), you need the [`srl-gnmi-bandwidth-poc`](https://github.com/musel25/srl-gnmi-bandwidth-poc) sibling repo cloned next to this one:

```bash
make clab-up      # stand up the ContainerLab topology
make demo-real    # restart provider with SDN_MOCK=false, run demo, verify with iperf3
make clab-down    # tear down the topology
```

---

## Where to read next

| If you want to... | Read |
|---|---|
| Understand what this is and why | [`docs/01-introduction.md`](docs/01-introduction.md) |
| Learn the vocabulary | [`docs/02-concepts.md`](docs/02-concepts.md) |
| Read or modify the code | [`docs/03-architecture.md`](docs/03-architecture.md) |
| Get it running on your machine | [`docs/04-running.md`](docs/04-running.md) |
| See the whole flow from a Python kernel | [`notebooks/06_end_to_end.py`](notebooks/06_end_to_end.py) |

If you've never seen this project before: read those docs in the order listed.

---

## Repo layout

```
.
├── consumer/         # Buyer agent: FastAPI + Ollama + MCP client + A2A client
├── provider/         # Seller agent: FastAPI + MCP server + A2A executor + SDN tools
├── shared/           # Cross-agent code: Config, A2A messages, ABIs, slot pool, anvil/deploy helpers
├── contracts/        # Solidity contracts (BandwidthEscrow + BandwidthNFT) + Foundry scripts
├── notebooks/        # Per-stage explainers + end-to-end demo, all in-process
├── tests/            # Pytest suite (unit + integration)
├── docs/             # This documentation set
└── paper/            # Companion research paper (separate git repo)
```

---

## Tech at a glance

- **Python 3.13** with `uv` for environment management
- **FastAPI** for the agent HTTP servers, **Streamlit** for the UI
- **FastMCP** for the MCP servers, **a2a-sdk** for inter-agent calls
- **Ollama** running `llama3.2:3b` locally (swappable; see [`docs/04-running.md`](docs/04-running.md))
- **Solidity 0.8.x** + **Foundry/Anvil** for the smart-contract layer
- **`tc tbf`** + **gNMI** for SDN bandwidth enforcement (mock by default; real path uses [`srl-gnmi-bandwidth-poc`](https://github.com/musel25/srl-gnmi-bandwidth-poc))

---

## Status

Active prototype. Companion to a research paper currently in progress (see `paper/`).
