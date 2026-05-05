# Introduction

## What this project is

Two AI agents — a **buyer** and a **seller** — autonomously negotiate, pay for, and activate a network bandwidth service. The buyer is driven by a local LLM (Ollama). The seller manages an inventory of bandwidth slots. They communicate through a published protocol (A2A), use a smart-contract escrow (running on a local Ethereum chain) to make the trade trust-minimised, and deliver the service through a software-defined-networking (SDN) layer that enforces the bandwidth cap.

The whole system runs on a single laptop. No real money, no real internet bandwidth — but every component (the contracts, the agents, the protocols, the SDN rules) is real code, doing what it would do in production.

## Why it exists

It's the working proof-of-concept that backs the paper *"Autonomous Agent-to-Agent Network Service Provisioning via Smart-Contract Escrow and Tokenized Authorization"* (see `paper/`). The paper argues that future AI agents will trade services with each other and need a payment-and-credential mechanism that doesn't trust either side. This repo demonstrates one such mechanism end-to-end.

## Who this documentation is for

Three reader profiles:

### A. Curious newcomer

You've heard "AI agent" and "blockchain" but you don't write code, or you write code but in a different domain. You want to understand what this project does and how, without slogging through it.

**Read in this order:** [`README.md`](../README.md) → [`01-introduction.md`](01-introduction.md) (this doc) → [`02-concepts.md`](02-concepts.md) → [`03-walkthrough.md`](03-walkthrough.md). Stop there. You'll have a solid mental model.

### B. Developer

You want to read or modify the code.

**Read in this order:** [`README.md`](../README.md) → [`03-walkthrough.md`](03-walkthrough.md) (skim) → [`04-architecture.md`](04-architecture.md) → [`06-modifying.md`](06-modifying.md). Use [`02-concepts.md`](02-concepts.md) as a glossary when you hit unfamiliar terms.

### C. Researcher / paper reader

You're checking whether the paper's claims map to working code.

**Read in this order:** [`README.md`](../README.md) → [`03-walkthrough.md`](03-walkthrough.md) → [`04-architecture.md`](04-architecture.md) → [`paper-alignment.md`](paper-alignment.md). The last one specifically tracks where the paper and the code diverge.

## What you'll learn from the docs

- How an LLM running on your laptop can autonomously buy a service from another program.
- Why the project uses **two** different agent protocols (MCP and A2A) and how they fit together.
- How a smart-contract escrow makes a trade *atomic*: the buyer never pays without getting the credential, and the seller never delivers without getting paid.
- What an NFT looks like when it's used as a service credential rather than a collectible.
- How a software-defined network actually enforces the bandwidth cap once the credential is presented.

## Glossary (one-liners)

- **MCP** — the protocol an agent uses to call its *own* tools.
- **A2A** — the protocol agents use to talk to *each other*.
- **Smart contract** — code that runs on a blockchain; here, an escrow that holds money until the trade completes.
- **NFT** — a non-fungible token; here, the buyer's "service ticket".
- **Atomic swap** — money and ticket change hands in one indivisible operation; either both happen or neither does.
- **SDN** — software-defined networking; programmable network rules.
- **Anvil** — a local fake Ethereum chain (no real money, no real chain).

For full explanations, see [`02-concepts.md`](02-concepts.md).
