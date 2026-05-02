# Bandwidth Agent Simulation

> Two AI agents negotiate and pay for internet bandwidth — entirely on-chain, running on your laptop.

This is a proof-of-concept where a **Consumer AI** and a **Provider AI** interact using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), agree on a bandwidth package, and settle the payment using a real Ethereum smart contract (running locally). No real money, no real internet traffic — just a working demonstration of what autonomous AI-to-AI commerce could look like.

**Key protocols:** The Provider exposes a FastMCP server at `/mcp` and an A2A JSON-RPC endpoint at `/a2a`. Both agents advertise their capabilities via an A2A Agent Card at `/.well-known/agent-card.json`. Inside the consumer, the LLM only sees a small set of MCP tools (`query_provider_catalog`, `purchase_package`, …); the consumer's own MCP server then drives the A2A client end-to-end so the LLM never has to know about A2A.

---

## What actually happens when you run it

1. You open a chat UI and type something like *"I need 100 Mbps for 10 minutes"*.
2. A **Consumer Agent** (an LLM running locally via Ollama) reads your message and decides which bandwidth tier to buy.
3. The Consumer Agent calls the **Provider Agent** to get a price quote.
4. It locks ETH into a smart contract (on a local test blockchain — no real money).
5. The Provider mints an **NFT** that proves you own the bandwidth service, and the escrow releases the ETH to the provider atomically.
6. The Provider's A2A executor activates the bandwidth slot (mock or real ContainerLab + tc) and the Consumer Agent reports back your active service details.

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
   │  LLM tools = local MCP server only (query_provider_catalog, purchase_package, …)
   │  discovers provider via /.well-known/agent-card.json  (A2A Agent Card)
   │
   ├─ MCP get_catalog  ─────────────────────────► Provider Agent  (:8002/mcp)
   │   tools/list + tools/call ◄── FastMCP ─────┘  catalog, quote, address
   │
   ├─ A2A purchase task  ───────────────────────► Provider Agent  (:8002/a2a)
   │   JSON-RPC message/send ◄── A2A SDK ───────┘  returns agreementId + price
   │
   ├─ requestAgreement()  ─────────────────────► BandwidthEscrow  (Anvil :8545)
   │    Consumer locks ETH on-chain               Smart contract holds funds
   │                                              Provider sees AgreementRequested event
   │                                              Provider mints NFT → BandwidthNFT
   │                                              Provider calls deposit()
   │                                              Atomic swap: ETH → Provider, NFT → Consumer
   │
   └─ A2A activate task  ───────────────────────► Provider Agent  (:8002/a2a)
        signed nonce + tokenId                    executor verifies ownerOf() on-chain
        service details ◄──────────────────────┘  allocate_bandwidth (mock or clab+tc)
```

### Services at a glance

| Service | Port | What it does |
|---------|------|-------------|
| Anvil (local blockchain) | 8545 | Runs a fake Ethereum chain for testing |
| Provider Agent | 8002 | Sells bandwidth — FastMCP at `/mcp`, A2A JSON-RPC at `/a2a`, Agent Card at `/.well-known/agent-card.json`. The A2A executor mints the NFT and activates the slot (mock or ContainerLab + `tc`) |
| Consumer Agent | 8001 | Buys bandwidth — LLM uses an in-process MCP server whose tools call the provider over MCP + A2A. Agent Card at `/.well-known/agent-card.json` |
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

Useful for development. Open five terminals:

```bash
# Terminal 1: Local blockchain
anvil --block-time 1

# Terminal 2: Deploy the smart contracts
source .env
cd contracts && forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast \
  --private-key $DEPLOYER_PRIVATE_KEY

# Terminal 3: Provider service (MCP @ /mcp, A2A @ /a2a, event listener, NFT mint, slot activation)
source .env && uv run uvicorn provider.app:app --port 8002

# Terminal 4: Consumer agent (LLM lives here)
source .env && uv run uvicorn consumer.app:app --port 8001

# Terminal 5: Web UI
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

### Two consumers in parallel

```bash
docker compose --profile multi-consumer up -d
# Consumer 1 reachable at http://localhost:8001/chat
# Consumer 2 reachable at http://localhost:8011/chat
```

The two consumers use different EOAs (account[2] and account[3]) and bind
different slots. Try ordering different tiers from each at the same time
to verify the slot pool's `fcntl`-based concurrency is sound.

---

## Running the demo with real SDN enforcement

The default `make demo` runs with `SDN_MOCK=true` — `allocate_bandwidth`
returns success without touching any network device.

To run the demo against ContainerLab + Nokia SR Linux + Linux `tc`:

1. Deploy ContainerLab (one-time per session, requires sudo):
   ```bash
   make clab-up      # runs ../srl-gnmi-bandwidth-poc/scripts/deploy.sh + push-config.sh
   ```

2. Run the demo with SDN enforcement enabled:
   ```bash
   make demo-real
   ```

3. Tear down:
   ```bash
   make clab-down
   make down
   ```

ContainerLab's 7-node topology and the slot mapping:

| Tier   | Mbps | PE  | Subinterface     | CE  |
|--------|------|-----|------------------|-----|
| small  | 2    | pe1 | ethernet-1/2.0   | ce1 |
| medium | 5    | pe1 | ethernet-1/3.0   | ce3 |
| large  | 8    | pe2 | ethernet-1/2.0   | ce2 |

After a `medium` purchase you can verify the rate is shaped:
```bash
docker exec clab-bandwidth-poc-ce4 iperf3 -s -1 -p 5201 -J &
docker exec clab-bandwidth-poc-ce3 iperf3 -c 192.168.4.10 -p 5201 -t 5 -u -b 15M -J
```
Expected: receiver `bits_per_second ≈ 5.0e6`.

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

provider/
  app.py                    FastAPI :8002 — catalog, quotes, AgreementRequested listener; mounts MCP at /mcp and A2A JSON-RPC at /a2a
  agent_executor.py         A2A executor: mints NFT, verifies ownership, activates the slot (mock or ContainerLab + tc)
  agent_card.py             Builds the /.well-known/agent-card.json card (skills, capabilities, MCP/A2A URLs)
  mcp_server.py             FastMCP tools: get_catalog, request_quote, provider_address
  expiry.py                 Background sweeper that releases expired slots
  inventory.txt             Per-tier slot counts with lease expiration timestamps

consumer/
  app.py                    FastAPI :8001 — runs the Ollama tool-calling loop
  mcp_server.py             In-process MCP server the LLM sees (query_provider_catalog, purchase_package, …)
  a2a_client.py             A2A client used by the consumer's MCP tools to talk to the provider
  agent_card.py             Builds the consumer's /.well-known/agent-card.json
  ui.py                     Streamlit :8501 — chat UI

shared/
  contracts.py              Loads deployed contract addresses + Web3 contract objects
  abi/                      ABI files copied from Foundry build artifacts

docs/
  decisions.md              Why we made every non-obvious technical decision
```

---

## What this PoC does and doesn't do

**Does:**
- **MCP tool calling**: Provider exposes a FastMCP server at `/mcp`; the consumer's own MCP server (which the LLM talks to) calls it for catalog/quote operations
- **A2A messaging**: Provider mounts an A2A JSON-RPC endpoint at `/a2a` (purchase + activation skills) using the official `a2a-sdk` `DefaultRequestHandler` + `InMemoryTaskStore`
- **A2A Agent Cards**: Both agents serve `/.well-known/agent-card.json` (with a legacy `/.well-known/agent.json` alias) advertising capabilities, skills, and protocol URLs
- End-to-end autonomous purchase: consumer LLM interprets natural language, picks a package, and completes payment without human help
- Double-escrow atomic swap: ETH from consumer and NFT from provider are exchanged in a single `deposit()` transaction — neither party can cheat
- Fully on-chain NFT entitlement: `bandwidthMbps`, `durationSeconds`, `startTime`, and `endpoint` stored directly in the token (no IPFS)
- NFT-gated activation: the A2A executor verifies `ownerOf()` on-chain (signed Ethereum nonce, replay-safe) before allocating bandwidth
- Per-tier slot inventory with time-based lease expiration and a background sweeper that releases expired slots

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
