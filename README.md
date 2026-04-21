# Bandwidth Agent Simulation

> Two AI agents negotiate and pay for internet bandwidth — entirely on-chain, running on your laptop.

This is a proof-of-concept where a **Consumer AI** and a **Provider AI** interact using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), agree on a bandwidth package, and settle the payment using a real Ethereum smart contract (running locally). No real money, no real internet traffic — just a working demonstration of what autonomous AI-to-AI commerce could look like.

**Key protocols:** The Provider exposes an MCP server at `/mcp` so any MCP-compatible agent (Claude, GPT-4, Ollama) can discover and call its tools without custom integration. Both agents advertise their capabilities via an A2A Agent Card at `/.well-known/agent.json`.

---

## What actually happens when you run it

1. You open a chat UI and type something like *"I need 100 Mbps for 10 minutes"*.
2. A **Consumer Agent** (an LLM running locally via Ollama) reads your message and decides which bandwidth tier to buy.
3. The Consumer Agent calls the **Provider Agent** to get a price quote.
4. It locks ETH into a smart contract (on a local test blockchain — no real money).
5. The Provider mints an **NFT** that proves you own the bandwidth service, and the escrow releases the ETH to the provider atomically.
6. The Consumer Agent calls the **Gateway** (which checks the NFT on-chain) and reports back your active service details.

All of this happens automatically — you just watch the agents work.

---

## Architecture

```
You (browser)
   │  type a message
   ▼
Consumer UI  (:8501)        ← Streamlit web app
   │  POST /chat
   ▼
Consumer Agent  (:8001)     ← FastAPI + Ollama LLM
   │  discovers provider via /.well-known/agent.json  (A2A Agent Card)
   │
   ├─ MCP tools/list  ─────────────────────────► Provider Agent  (:8002/mcp)
   │   get_catalog()  ◄─────── MCP ────────────┘  FastMCP server
   │
   ├─ MCP tools/call  ─────────────────────────► Provider Agent  (:8002/mcp)
   │   request_quote(package_id) ◄── MCP ───────┘  returns agreementId
   │
   ├─ requestAgreement()  ─────────────────────► BandwidthEscrow  (Anvil :8545)
   │    Consumer locks ETH on-chain               Smart contract holds funds
   │                                              Provider sees AgreementRequested event
   │                                              Provider mints NFT → BandwidthNFT
   │                                              Provider calls deposit()
   │                                              Atomic swap: ETH → Provider, NFT → Consumer
   │
   └─ GET /service  ───────────────────────────► Gateway  (:8003)
        (signed nonce + tokenId)                 checks ownerOf() on-chain
        service details ◄──────────────────────┘
```

### Services at a glance

| Service | Port | What it does |
|---------|------|-------------|
| Anvil (local blockchain) | 8545 | Runs a fake Ethereum chain for testing |
| Provider Agent | 8002 | Sells bandwidth — FastMCP server at `/mcp`, A2A Agent Card at `/.well-known/agent.json` |
| Gateway | 8003 | Verifies NFT ownership before giving access to the service |
| Consumer Agent | 8001 | Buys bandwidth — LLM uses MCP to call provider tools, A2A Agent Card at `/.well-known/agent.json` |
| Consumer UI | 8501 | The chat interface you talk to |

---

## Prerequisites

You need four tools installed before starting:

### 1. Foundry (Ethereum dev toolkit)
```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```
This gives you `anvil` (a local blockchain) and `forge` (to compile/deploy contracts).

### 2. Docker + Docker Compose v2
Install from [docker.com](https://docs.docker.com/get-docker/). Make sure `docker compose version` shows v2.x.

### 3. Ollama (runs AI models locally)
Install from [ollama.com](https://ollama.com/), then pull the model:
```bash
ollama pull ministral:3b
```
This downloads a ~2 GB AI model that the agents will use to think and talk.

> **Why ministral:3b?** It's small enough to run on most laptops without a GPU, and it supports tool-calling (the feature that lets the LLM call functions like `query_provider_catalog`).

### 4. uv (Python package manager)
```bash
pip install uv
```

---

## Quickstart

### Option A — Docker (recommended, everything in one command)

```bash
# 1. Copy the example environment file
cp .env.example .env

# 2. Build and start all services
make up

# 3. Open the UI in your browser
open http://localhost:8501

# 4. Stop everything when done
make down
```

That's it. Docker Compose will:
- Start a local Ethereum chain (Anvil)
- Deploy the smart contracts
- Pull the Ollama model inside the container
- Start the provider, gateway, consumer agent, and UI

> **First run takes a few minutes** — it needs to build Docker images and pull the ~2 GB AI model.

### Option B — Run locally (no Docker)

Useful for development. Open six terminals:

```bash
# Terminal 1: Local blockchain
anvil --block-time 1

# Terminal 2: Deploy the smart contracts
source .env
cd contracts && forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast \
  --private-key $DEPLOYER_PRIVATE_KEY

# Terminal 3: Provider service (catalog + quotes + event listener)
source .env && uv run uvicorn provider.app:app --port 8002

# Terminal 4: Gateway (NFT-gated access check)
source .env && uv run uvicorn provider.gateway:app --port 8003

# Terminal 5: Consumer agent (LLM lives here)
source .env && uv run uvicorn consumer.app:app --port 8001

# Terminal 6: Web UI
source .env && uv run streamlit run consumer/ui.py
```

---

## Usage

Once running, go to **http://localhost:8501** and type a message like:

- *"I need 100 Mbps for 10 minutes"*
- *"Buy me the cheapest bandwidth package"*
- *"What bandwidth options are available?"*

The right panel shows the raw agent-to-agent conversation so you can see every HTTP call and on-chain transaction happening in real time.

### Scripted demo (no browser needed)

```bash
make demo
```

This runs a full purchase flow via `curl` and prints the output at each step.

---

## Project Structure

```
contracts/
  src/
    BandwidthNFT.sol        ERC-721 token — proves you own the bandwidth service
    BandwidthEscrow.sol     Holds ETH + NFT and swaps them atomically
  script/
    Deploy.s.sol            Deploys both contracts, saves addresses to local.json
  deployments/
    local.json              Auto-generated: contract addresses after deployment

consumer/
  app.py                    FastAPI :8001 — the LLM reasoning loop runs here
  ui.py                     Streamlit :8501 — the chat UI (thin HTTP client)

provider/
  app.py                    FastAPI :8002 — catalog, quotes, AgreementRequested listener
  gateway.py                FastAPI :8003 — checks NFT ownership before serving data
  inventory.txt             Per-tier slot counts with lease expiration timestamps

shared/
  contracts.py              Loads deployed contract addresses + Web3 contract objects
  abi/                      ABI files copied from Foundry build artifacts

docs/
  decisions.md              Why we made every non-obvious technical decision
```

---

## What this PoC does and doesn't do

**Does:**
- **MCP tool calling**: Provider exposes a FastMCP server; consumer LLM discovers and calls tools dynamically — any MCP-compatible agent can use it without custom integration
- **A2A Agent Cards**: Both agents serve `/.well-known/agent.json` advertising capabilities and MCP endpoint (A2A discovery pattern)
- End-to-end autonomous purchase: consumer LLM interprets natural language, picks a package, and completes payment without human help
- Double-escrow atomic swap: ETH from consumer and NFT from provider are exchanged in a single `deposit()` transaction — neither party can cheat
- Fully on-chain NFT entitlement: `bandwidthMbps`, `durationSeconds`, `startTime`, and `endpoint` stored directly in the token (no IPFS)
- NFT-gated gateway: access is verified by checking `ownerOf()` on-chain using a signed Ethereum nonce (replay-safe)
- Per-tier slot inventory with time-based lease expiration

**Does not:**
- Enforce bandwidth at the network layer (no QoS, no traffic shaping, no real hardware)
- Use an oracle to verify the bandwidth was actually delivered
- Support multi-round price negotiation (one quote, take it or leave it)
- Accept ERC-20 token payments (native ETH only)
- Deploy to a real network (Anvil only, test accounts with no real value)
- Use DID / verifiable credentials (identity = Ethereum address)

---

## Changing the AI model

The default model is `ministral:3b`. To try a different one:

```bash
# Pull a different model
ollama pull qwen3:4b

# Use it (set before running make up, or pick it in the UI sidebar)
OLLAMA_MODEL=qwen3:4b make up
```

Models that support tool-calling work best. Tested models: `ministral:3b`, `qwen3:4b`, `qwen3:1.7b`.

---

## Troubleshooting

**`Error 404: model not found`**
The model isn't pulled yet. Run `ollama pull ministral:3b` (or whichever model is selected).

**`make up` fails at the deployer step**
Anvil might still be starting. Run `make down` then `make up` again.

**UI shows "Error reaching consumer agent"**
The consumer agent container might still be starting. Wait 30 seconds and refresh.

**Transactions revert on-chain**
The contracts may not be deployed yet — check with `docker compose logs deployer`.

---

## See Also

- [`docs/decisions.md`](docs/decisions.md) — Every non-obvious architectural decision, with reasoning.
- [Foundry Book](https://book.getfoundry.sh/) — Learn how the smart contracts work.
- [Ollama docs](https://github.com/ollama/ollama) — How to run and configure local models.
