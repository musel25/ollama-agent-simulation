# Notebooks

Five notebooks that exercise every layer of the stack in-process. No Docker required.

## Prerequisites

- Python 3.13 + `uv`
- `anvil` + `forge` on PATH (install from [Foundry](https://book.getfoundry.sh/getting-started/installation))
- For `05_end_to_end.ipynb` only: `ollama` running locally with `llama3.2:3b` pulled

## Setup

```bash
uv sync
uv run jupyter lab .
```

## Run order

| # | Notebook | What it shows |
|---|---|---|
| 1 | `01_chain.ipynb` | Deploy contracts, walk one trade on Anvil. |
| 2 | `02_mcp.ipynb` | Exercise the provider's MCP tools in-process. |
| 3 | `03_a2a.ipynb` | Drive the provider's A2A executor via in-process ASGI. |
| 4 | `04_consumer_graph.ipynb` | Step through the consumer LangGraph state machine. |
| 5 | `05_end_to_end.ipynb` | Full negotiation: real Ollama, in-process apps. |

Each notebook follows: **Setup → Build → Run → Inspect → Teardown**.
