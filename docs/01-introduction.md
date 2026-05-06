# Introduction

## What this project is

Two AI agents — a **buyer** and a **seller** — autonomously negotiate, pay for, and activate a network bandwidth service. The buyer is driven by a local LLM (Ollama). The seller manages an inventory of bandwidth slots. They communicate through a published protocol (A2A), use a smart-contract escrow on a local Ethereum chain to make the trade trust-minimised, and deliver the service through a software-defined-networking (SDN) layer that enforces the bandwidth cap.

The whole system runs on a single laptop. No real money, no real internet bandwidth — but every component (the contracts, the agents, the protocols, the SDN rules) is real code, doing what it would do in production.

## Why it exists

It's the working proof-of-concept that backs the paper *"Autonomous Agent-to-Agent Network Service Provisioning via Smart-Contract Escrow and Tokenized Authorization"* (see `paper/`).

## Two ways to run it

- **Docker stack** (`make up && make demo`) — everything runs in containers; the dashboard at `http://localhost:8501` shows the live trade.
- **Notebooks** (`notebooks/01_*.ipynb` … `05_*.ipynb`) — every layer is exercised in-process from Python. No Docker required (only the `anvil`/`forge` binaries from Foundry, plus optionally `ollama`).

## Reading order

1. `01-introduction.md` (this file) — what this is.
2. `02-concepts.md` — the vocabulary used in everything else.
3. `03-architecture.md` — how the pieces fit, and where to make changes.
4. `04-running.md` — how to actually get it running, both paths.
5. `notebooks/05_end_to_end.ipynb` — see the whole flow from a Python kernel.

## Glossary (one-liners)

- **MCP** — the protocol an agent uses to call its *own* tools.
- **A2A** — the protocol agents use to talk to *each other*.
- **Smart contract** — code that runs on a blockchain; here, an escrow that holds money until the trade completes.
- **NFT** — a non-fungible token; here, the buyer's "service ticket".
- **Atomic swap** — money and ticket change hands in one indivisible operation.
- **SDN** — software-defined networking; programmable network rules.
- **Anvil / Foundry** — local fake Ethereum chain (`anvil`) + deployment toolkit (`forge`).
- **Ollama** — local LLM runtime; runs `llama3.2:3b` by default.

For full explanations, see `02-concepts.md`.
