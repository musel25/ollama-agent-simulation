# Bandwidth Agent Simulation

A proof-of-concept demonstrating autonomous agent-to-agent (A2A) negotiation and on-chain settlement for tokenized network bandwidth services. Two Ollama-powered LLM agents (consumer and provider) negotiate over HTTP; settlement is enforced by a double-escrow Ethereum smart contract running locally on Anvil (Foundry's local chain).

## Architecture

```
Consumer UI (Streamlit :8501)
        │  HTTP POST /chat
        ▼
Consumer Agent (:8001)
  LLM tool calls ──► query_provider_catalog ──────────────► Provider Agent (:8002)
                                                               GET /catalog
                 ──► request_agreement_on_chain
                           │  POST /quote → agreementId
                           │  requestAgreement() ──────────► BandwidthEscrow (Anvil)
                           │                                      │
                           │                              AgreementRequested event
                           │                                      │
                           │                              Provider Agent (listener)
                           │                                mint NFT → BandwidthNFT
                           │                                approve escrow
                           │                                deposit() ──► BandwidthEscrow
                           │                                         atomic swap:
                           │                                         ETH ──► Provider
                           │                                         NFT ──► Consumer
                 ──► check_agreement_status
                           │  getAgreement() on-chain
                           │  signed nonce
                           └─────────────────────────────► Gateway (:8003)
                                                             ownerOf() on-chain
                                                           "100 Mbps, 590s remaining"
```

## What this PoC does and does not do

**Does:**
- Tier 1 provider-asserted bandwidth — the provider self-reports capacity with per-tier slot counts and time-based lease expiration.
- Double-escrow atomic swap on a local EVM chain: ETH from consumer and NFT from provider are exchanged in a single `deposit()` transaction.
- On-chain NFT entitlement: the ERC-721 token carries `bandwidthMbps`, `durationSeconds`, `startTime`, and `endpoint` fully on-chain — no IPFS.
- LLM-driven negotiation: the consumer agent uses natural language to interpret user requests and select a bandwidth package.
- NFT-gated gateway: the gateway verifies on-chain NFT ownership via signed Ethereum nonce before returning service metadata.

**Does not:**
- Enforce bandwidth at the network layer (no QoS, no traffic shaping, no hardware integration).
- Use an oracle to attest actual bandwidth delivered.
- Support multi-round price negotiation (one quote, accept or reject).
- Use ERC-20 token payments (native ETH only via `msg.value`).
- Deploy to testnet or mainnet (Anvil only, deterministic test accounts).
- Use DID / verifiable credential identity (identity = Ethereum address).

## Quickstart

### Prerequisites

- [Foundry](https://getfoundry.sh/) — `forge` + `anvil` (install: `curl -L https://foundry.paradigm.xyz | bash`)
- [Docker + Docker Compose v2](https://docs.docker.com/get-docker/)
- [Ollama](https://ollama.com/) running locally with `qwen3:4b` pulled: `ollama pull qwen3:4b`
- [uv](https://github.com/astral-sh/uv) — Python package manager (install: `pip install uv`)

### Run with Docker

```bash
# 1. Copy environment (Anvil deterministic accounts — no real ETH needed)
cp .env.example .env

# 2. Start all services
make up

# 3. Open the UI
open http://localhost:8501
# Type: "I need 100 Mbps for 10 minutes"

# 4. Run the scripted demo (no UI required)
make demo

# 5. Stop everything
make down
```

### Run locally (no Docker)

```bash
# Terminal 1: Anvil (local chain)
anvil --block-time 1

# Terminal 2: Deploy contracts
source .env
cd contracts && forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast \
  --private-key $DEPLOYER_PRIVATE_KEY

# Terminal 3: Provider service
source .env && uv run uvicorn provider.app:app --port 8002

# Terminal 4: Gateway service
source .env && uv run uvicorn provider.gateway:app --port 8003

# Terminal 5: Consumer service
source .env && uv run uvicorn consumer.app:app --port 8001

# Terminal 6: Streamlit UI
source .env && uv run streamlit run consumer/ui.py
```

## Project Structure

```
contracts/
  src/
    BandwidthNFT.sol       ERC-721 with fully on-chain metadata
    BandwidthEscrow.sol    Double-escrow: ETH <-> NFT atomic swap
  script/
    Deploy.s.sol           Deploys both contracts, writes addresses to local.json
  deployments/
    local.json             Runtime-generated contract addresses

consumer/
  app.py                   FastAPI :8001 — LLM tool-calling loop + chain interactions
  ui.py                    Streamlit :8501 — thin HTTP client to consumer/app.py

provider/
  app.py                   FastAPI :8002 — catalog, quotes, AgreementRequested listener
  gateway.py               FastAPI :8003 — NFT-gated service endpoint
  inventory.txt            Per-tier slot counts with lease expiration (JSON-lines)

shared/
  contracts.py             Loads deployment addresses + exposes web3 Contract objects
  abi/                     ABI JSONs copied from Foundry build artifacts

docs/
  decisions.md             Architecture and implementation decision log
```

## See Also

- [`docs/decisions.md`](docs/decisions.md) — Every non-obvious decision made during implementation, with reasoning.
