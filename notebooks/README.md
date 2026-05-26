# Notebooks

A 21-notebook pedagogical series. Concept-first; each layer has at least
one concept notebook (mostly prose + diagrams) and one walkthrough
notebook (hands-on). The chain, LangGraph, and network layers each get
four; MCP and A2A each get three.

## Prerequisites

- Python 3.13 + `uv`
- `anvil` + `forge` on PATH (install from [Foundry](https://book.getfoundry.sh/getting-started/installation))
- For `06_end_to_end.ipynb` only: `ollama` running locally with `llama3.2:3b` pulled

## Beginner primer

New to blockchain or Solidity? Start with **[blockchain_primer/](blockchain_primer/)** — a hands-on, ground-up tour of accounts, transactions, the EVM, and Solidity, driven by a local `anvil` chain. It ends with a guided read of `contracts/src/BandwidthEscrow.sol`. Run it before `01a` if you've never deployed a smart contract.

## From-scratch deep dive

Want to understand HOW the primer works under the hood? **[from_scratch/](from_scratch/)** is a 10-notebook series that builds every Ethereum primitive by hand in Python — keys, signatures, RLP, a toy chain, real-TCP networking with `tcpdump` debugging, P2P gossip, fork choice & reorgs, a Merkle-Patricia trie, and a toy EVM that disassembles real compiled bytecode. No web3.py, no shortcuts. Stops just before Solidity — at which point the `blockchain_primer/` picks up.

## Setup

```bash
uv sync
uv run jupyter lab .
```

## Run order

| # | Notebook | What it teaches |
|---|---|---|
| 0 | `00_overview.ipynb` | The 6-stage flow; who talks to whom. |
| 1a | `01a_chain_contract_model.ipynb` | Solidity structs, Status enum, ERC-721 credential. |
| 1b | `01b_chain_escrow_lifecycle.ipynb` | State machine; CEI ordering inside `deposit()`. |
| 1c | `01c_chain_nft_minting.ipynb` | TokenMetadata; on-chain endpoint binding. |
| 1d | `01d_chain_walkthrough.ipynb` | Deploy + walk one trade; events, gas, balances. |
| 2a | `02a_mcp_concepts.ipynb` | MCP, FastMCP, tools/resources, transports. |
| 2b | `02b_mcp_tool_catalog.ipynb` | Inspect every provider + consumer tool's schema. |
| 2c | `02c_mcp_walkthrough.ipynb` | Call tools through `fastmcp.Client`. |
| 3a | `03a_a2a_concepts.ipynb` | AgentCard, skills, executor, EventQueue. |
| 3b | `03b_a2a_agent_cards.ipynb` | Render both agent cards as styled views. |
| 3c | `03c_a2a_walkthrough.ipynb` | Drive the executor in-process. |
| 4a | `04a_graph_state_schema.ipynb` | WorkflowState fields; reducer behavior. |
| 4b | `04b_graph_topology.ipynb` | Render the LangGraph PNG; per-node responsibilities. |
| 4c | `04c_graph_llm_prompts.ipynb` | The two LLM prompts verbatim; failure modes. |
| 4d | `04d_graph_walkthrough.ipynb` | Stream node-by-node; state diffs at every step. |
| 5a | `05a_inventory_and_expiry.ipynb` | SlotPool, event listener, expiry sweep. |
| 6  | `06_end_to_end.ipynb` | Full negotiation with real Ollama. |
| 7a | `07a_network_concepts.ipynb` | SDN_MOCK, gNMI policer, tc tbf, iperf3. |
| 7b | `07b_network_topology.ipynb` | Inline topology drawn from inventory. |
| 7c | `07c_network_before_after.ipynb` | Visual: 0 Mbps → 5 Mbps after settlement. |
| 7d | `07d_network_router_config.ipynb` | gNMI Set body, tc command, mock vs real. |

Every notebook follows the same skeleton: **Concepts → Setup → Build →
Run → Inspect → Recap**. Concept notebooks are mostly markdown;
walkthrough notebooks drive the renderers in `notebooks/_viz.py`.
