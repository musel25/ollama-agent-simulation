# Notebooks

A 21-notebook pedagogical series, authored as [marimo](https://marimo.io) reactive Python notebooks. Concept-first; each layer has at least
one concept notebook (mostly prose + diagrams) and one walkthrough
notebook (hands-on). The chain, LangGraph, and network layers each get
four; MCP and A2A each get three.

## Prerequisites

- Python 3.13 + `uv`
- `anvil` + `forge` on PATH (install from [Foundry](https://book.getfoundry.sh/getting-started/installation))
- For `06_end_to_end.py` only: `ollama` running locally with `llama3.2:3b` pulled

## Beginner primer

New to blockchain or Solidity? Start with **[blockchain_primer/](blockchain_primer/)** — a hands-on, ground-up tour of accounts, transactions, the EVM, and Solidity, driven by a local `anvil` chain. It ends with a guided read of `contracts/src/BandwidthEscrow.sol`. Run it before `01a` if you've never deployed a smart contract.

## From-scratch deep dive

Want to understand HOW the primer works under the hood? **[from_scratch/](from_scratch/)** is a 10-notebook series that builds every Ethereum primitive by hand in Python — keys, signatures, RLP, a toy chain, real-TCP networking with `tcpdump` debugging, P2P gossip, fork choice & reorgs, a Merkle-Patricia trie, and a toy EVM that disassembles real compiled bytecode. No web3.py, no shortcuts. Stops just before Solidity — at which point the `blockchain_primer/` picks up.

## Setup

```bash
uv sync
uv run marimo edit notebooks/
```

Open any `.py` notebook in the marimo editor. Run a single notebook directly:

```bash
uv run marimo edit notebooks/00_overview.py     # interactive editor
uv run marimo run notebooks/00_overview.py      # read-only app view
```

## Run order

| # | Notebook | What it teaches |
|---|---|---|
| 0  | [`00_overview.py`](00_overview.py) | The 6-stage flow; who talks to whom. |
| 1a | [`01a_chain_contract_model.py`](01a_chain_contract_model.py) | Solidity structs, Status enum, ERC-721 credential. |
| 1b | [`01b_chain_escrow_lifecycle.py`](01b_chain_escrow_lifecycle.py) | State machine; CEI ordering inside `deposit()`. |
| 1c | [`01c_chain_nft_minting.py`](01c_chain_nft_minting.py) | TokenMetadata; on-chain endpoint binding. |
| 1d | [`01d_chain_walkthrough.py`](01d_chain_walkthrough.py) | Deploy + walk one trade; events, gas, balances. |
| 2a | [`02a_mcp_concepts.py`](02a_mcp_concepts.py) | MCP, FastMCP, tools/resources, transports. |
| 2b | [`02b_mcp_tool_catalog.py`](02b_mcp_tool_catalog.py) | Inspect every provider + consumer tool's schema. |
| 2c | [`02c_mcp_walkthrough.py`](02c_mcp_walkthrough.py) | Call tools through `fastmcp.Client`. |
| 3a | [`03a_a2a_concepts.py`](03a_a2a_concepts.py) | AgentCard, skills, executor, EventQueue. |
| 3b | [`03b_a2a_agent_cards.py`](03b_a2a_agent_cards.py) | Render both agent cards as styled views. |
| 3c | [`03c_a2a_walkthrough.py`](03c_a2a_walkthrough.py) | Drive the executor in-process. |
| 4a | [`04a_graph_state_schema.py`](04a_graph_state_schema.py) | WorkflowState fields; reducer behavior. |
| 4b | [`04b_graph_topology.py`](04b_graph_topology.py) | Render the LangGraph PNG; per-node responsibilities. |
| 4c | [`04c_graph_llm_prompts.py`](04c_graph_llm_prompts.py) | The two LLM prompts verbatim; failure modes. |
| 4d | [`04d_graph_walkthrough.py`](04d_graph_walkthrough.py) | Stream node-by-node; state diffs at every step. |
| 5a | [`05a_inventory_and_expiry.py`](05a_inventory_and_expiry.py) | SlotPool, event listener, expiry sweep. |
| 6  | [`06_end_to_end.py`](06_end_to_end.py) | Full negotiation with real Ollama. |
| 7a | [`07a_network_concepts.py`](07a_network_concepts.py) | SDN_MOCK, gNMI policer, tc tbf, iperf3. |
| 7b | [`07b_network_topology.py`](07b_network_topology.py) | Inline topology drawn from inventory. |
| 7c | [`07c_network_before_after.py`](07c_network_before_after.py) | Visual: 0 Mbps → 5 Mbps after settlement. |
| 7d | [`07d_network_router_config.py`](07d_network_router_config.py) | gNMI Set body, tc command, mock vs real. |

Every notebook follows the same skeleton: **Concepts → Setup → Build →
Run → Inspect → Recap**. Concept notebooks are mostly markdown;
walkthrough notebooks drive the renderers in `_viz.py`.

## Why marimo?

Notebooks are stored as plain Python files (no JSON, no embedded outputs), which means:

- Git diffs are readable — no noise from cell IDs, execution counts, or base64 images.
- Cells form a reactive dependency graph: editing a cell re-runs everything that depends on it. Stale state is impossible.
- You can also run a notebook as a script — `uv run python notebooks/00_overview.py` — or as a read-only web app — `uv run marimo run …`.
