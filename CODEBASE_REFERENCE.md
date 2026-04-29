# Codebase Technical Reference
> AI-to-AI assistant map. Do not modify this file manually — regenerate it when the architecture changes.

---

## 1. PROJECT IDENTITY

**ollama-agent-simulation** is a proof-of-concept multi-agent simulation where two autonomous AI agents — a Consumer and a Provider — negotiate, pay for, and activate internet bandwidth packages without human intervention. The Consumer agent (LLM via Ollama) interprets natural-language requests, calls the Provider's MCP server to discover catalog and price, then executes an on-chain escrow swap on a local Ethereum chain (Anvil). The Provider mints an ERC-721 NFT entitlement and deposits it atomically against the locked ETH. A separate Gateway service verifies NFT ownership before serving bandwidth metadata. Both agents advertise capabilities via A2A Agent Cards (`/.well-known/agent.json`). This is a research prototype accompanying an academic paper; no real money or network traffic is involved.

**IMPORTANT:** There are two generations of code in this repo. The **legacy prototype** (`app.py`, `consumer_agent.py`, `provider_server.py`, `catalog.txt`, `agreements.json`) uses plain HTTP and no blockchain. The **current production codebase** lives in `consumer/`, `provider/`, and `shared/` packages and uses MCP + Ethereum. The legacy files are dead code for the purpose of any active development.

---

## 2. TECH STACK SUMMARY

| Component | Version | Role |
|---|---|---|
| Python | ≥3.11 (3.13 in Docker) | Runtime for all Python services |
| uv | 0.8.22 | Dependency & venv management |
| FastAPI | ≥0.136.0 | HTTP framework for consumer (:8001), provider (:8002), gateway (:8003) |
| Uvicorn | ≥0.44.0 (standard) | ASGI server |
| FastMCP | ≥3.2.4 | MCP server (provider side) and MCP client (consumer side) |
| Ollama Python SDK | ≥0.6.1 | Drives local LLM inference; `ollama.AsyncClient` for tool-calling loop |
| Streamlit | ≥1.56.0 | Chat UI at :8501 |
| web3.py | ≥6.0,<7 | Ethereum JSON-RPC client; signs and sends transactions |
| eth-account | ≥0.11.3 | Key management, signing, signature recovery |
| httpx | ≥0.28.1 | Sync/async HTTP client (UI→consumer, consumer→gateway) |
| Pydantic | (bundled with FastAPI) | Request/response validation |
| Solidity | ^0.8.20 | Smart contract language |
| Foundry (forge, anvil) | latest | EVM toolchain; Anvil runs the local chain at :8545 |
| OpenZeppelin Contracts | (Foundry lib) | ERC-721 base (`ERC721`, `ERC721Holder`, `Ownable`) |
| Docker / Docker Compose v2 | — | Container orchestration for the full stack |
| Ollama (container) | latest | Hosts LLM models locally; serves at :11434 inside Docker |
| qwen3:4b / qwen3:1.7b | — | Default LLM models; must support tool-calling |
| pytest | ≥9.0.3 | Unit tests |
| pytest-asyncio | ≥1.3.0 | Async test support |

---

## 3. FULL DIRECTORY TREE

```
ollama-agent-simulation/
├── consumer/                  # Consumer agent package
│   ├── __init__.py
│   ├── app.py                 # FastAPI app :8001 — LLM loop, all endpoints
│   ├── mcp_client.py          # MCP client utilities + quote_cache
│   └── ui.py                  # Streamlit app :8501
├── provider/                  # Provider agent package
│   ├── __init__.py
│   ├── app.py                 # FastAPI app :8002 — catalog, quotes, event listener
│   ├── catalog.py             # In-memory catalog + file-locked inventory management
│   ├── gateway.py             # FastAPI app :8003 — NFT-gated service check
│   ├── mcp_server.py          # FastMCP server — exposes get_catalog, request_quote as MCP tools
│   └── inventory.txt          # Mutable state: per-tier slot counts + active leases (JSONL)
├── shared/                    # Cross-service utilities
│   ├── __init__.py
│   ├── contracts.py           # Loads deployed addresses + returns web3 contract objects
│   └── abi/
│       ├── BandwidthEscrow.json  # ABI for BandwidthEscrow — used by provider/app.py, consumer/app.py, provider/gateway.py
│       └── BandwidthNFT.json    # ABI for BandwidthNFT — used by provider/app.py, consumer/app.py, provider/gateway.py
├── contracts/                 # Solidity smart contracts (Foundry project)
│   ├── src/
│   │   ├── BandwidthEscrow.sol   # Double-escrow contract — holds ETH + swaps for NFT
│   │   └── BandwidthNFT.sol      # ERC-721 entitlement token — on-chain metadata
│   ├── script/
│   │   └── Deploy.s.sol          # Deploys both contracts, writes deployments/local.json
│   ├── deployments/
│   │   └── local.json            # AUTO-GENERATED — contract addresses after deploy (git-tracked as a convenience)
│   ├── foundry.toml
│   └── foundry.lock
├── tests/
│   ├── __init__.py
│   ├── test_catalog.py        # Unit tests for provider.catalog
│   └── test_mcp_client.py     # Unit tests for consumer.mcp_client
├── Dockerfile.provider        # Multi-stage image: runs provider/app.py + provider/gateway.py
├── Dockerfile.consumer        # Multi-stage image: runs consumer/app.py (and also ui.py via override)
├── docker-compose.yml         # Orchestrates: anvil, deployer, ollama, provider-agent, consumer-agent, consumer-ui
├── Makefile                   # Targets: up, down, down-clean, logs, contracts, demo
├── pyproject.toml             # uv project definition — all dependencies
├── uv.lock                    # Locked dependency graph
├── .env                       # Runtime secrets (gitignored in real use — committed here with test keys)
├── .env.example               # Documented env var template
├── .python-version            # Python version pin for uv
├── .streamlit/config.toml     # Dark theme for Streamlit
├── paper/                     # Academic paper (LaTeX + references) — NOT executable code
│   ├── main.tex
│   ├── references.bib
│   └── notes.md               # Citation justifications for the paper
│
│ ── LEGACY / DEAD CODE (do not modify) ──────────────────────────────────
├── app.py                     # Legacy Streamlit app — wraps consumer_agent.py (old HTTP approach)
├── consumer_agent.py          # Legacy consumer — HTTP to provider_server.py (no MCP, no blockchain)
├── provider_server.py         # Legacy provider — plain HTTP, CSV catalog, UUID tokens
├── catalog.txt                # Legacy CSV catalog (consumer_agent.py reads this)
└── agreements.json            # Legacy agreements store (provider_server.py writes this)
```

### File annotations

| File | Exports / Exposes | Imported by |
|---|---|---|
| `provider/catalog.py` | `CATALOG`, `CATALOG_BY_ID`, `pending_quotes`, `get_catalog_with_availability`, `make_quote`, `decrement_inventory`, `rewind_inventory`, `cleanup_quotes` | `provider/app.py`, `provider/mcp_server.py` |
| `provider/mcp_server.py` | `mcp` (FastMCP instance with tools `get_catalog`, `request_quote`) | `provider/app.py` |
| `provider/app.py` | FastAPI `app`; endpoints: `/.well-known/agent.json`, `/catalog`, `/quote`, `/inventory`, `/address`, `/mcp` | Entry point via uvicorn |
| `provider/gateway.py` | FastAPI `app`; endpoint: `/service` | Entry point via uvicorn; called by `consumer/app.py` |
| `consumer/mcp_client.py` | `get_provider_tools()`, `call_provider_tool()`, `mcp_tool_to_ollama()`, `quote_cache` | `consumer/app.py` |
| `consumer/app.py` | FastAPI `app`; endpoints: `/.well-known/agent.json`, `/chat`, `/log`, `/address`, `/catalog_proxy`, `/check_token` | Entry point via uvicorn; called by `consumer/ui.py` |
| `consumer/ui.py` | Streamlit app; calls `consumer/app.py` over HTTP | Standalone — run with `streamlit run` |
| `shared/contracts.py` | `get_nft_contract(w3)`, `get_escrow_contract(w3)` | `provider/app.py`, `provider/gateway.py`, `consumer/app.py` |
| `shared/abi/BandwidthEscrow.json` | ABI array | `shared/contracts.py` |
| `shared/abi/BandwidthNFT.json` | ABI array | `shared/contracts.py` |
| `contracts/deployments/local.json` | `{"bandwidthNFT": "0x...", "bandwidthEscrow": "0x..."}` | `shared/contracts.py` |
| `provider/inventory.txt` | JSONL file — one row per tier, with `tier`, `mbps`, `durationSeconds`, `totalSlots`, `activeLeases[]` | `provider/catalog.py` (r/w with fcntl locking) |

---

## 4. ARCHITECTURE & PATTERNS

### Pattern: Microservices with LLM reasoning loop

Four independent HTTP services communicate over the network. No shared in-process state except within each service.

```
Browser
  │ POST /chat
  ▼
consumer/ui.py :8501   (Streamlit — thin HTTP client, all logic delegated)
  │ POST /chat
  ▼
consumer/app.py :8001  (FastAPI — owns the LLM agentic loop)
  │
  ├─ [MCP] get_provider_tools / call_provider_tool ──► provider/app.py :8002/mcp
  │                                                     (FastMCP over HTTP)
  │
  ├─ [web3] requestAgreement() ─────────────────────► Anvil :8545
  │                                                     (Ethereum chain)
  │                 AgreementRequested event ◄──────── provider/app.py polls
  │                 provider mints NFT, calls deposit()
  │                 atomic swap: ETH→provider, NFT→consumer
  │
  └─ [httpx] GET /service ──────────────────────────► provider/gateway.py :8003
               (signed nonce + tokenId)                ownerOf() on-chain check
```

### Key patterns in use

**1. LLM Tool-calling loop (consumer/app.py `run_consumer`):**
- System prompt + user message sent to Ollama with a combined tool list (MCP tools + local tools)
- Loop runs ≤12 iterations: if `msg.tool_calls` is non-empty, dispatch each call and append `{"role":"tool"}` messages
- MCP tools (`get_catalog`, `request_quote`) are dispatched via `call_provider_tool()` to the remote MCP server
- Local tools (`execute_agreement`, `check_agreement_status`) are dispatched as plain Python function calls
- Loop exits when no tool calls remain in the response, or at iteration 12 (returns a timeout message)

**2. Atomic double-escrow (BandwidthEscrow.sol `deposit()`):**
- Consumer calls `requestAgreement()` locking ETH → status = REQUESTED
- Provider calls `deposit(agreementId, tokenId)` → checks-effects-interactions: status set to ACTIVE first, then `safeTransferFrom` NFT to escrow then to consumer, then `call{value}` ETH to provider. If ETH transfer fails, revert (entire atomic)
- PENDING state exists in the paper's description but is never externally observable; the swap is atomic inside `deposit()`

**3. File-locked inventory (provider/catalog.py):**
- `inventory.txt` is a JSONL file with one row per tier
- Every read/write uses `fcntl.LOCK_EX` (exclusive lock) to prevent race conditions when multiple agreements land simultaneously
- Expired leases are pruned on every read via time comparison

**4. Signed nonce authentication (provider/gateway.py):**
- Client sends `X-Nonce` (unix timestamp string) and `X-Signature` (ECDSA signature of nonce)
- Gateway recovers signer with `Account.recover_message`, then calls `ownerOf(tokenId)` on-chain to verify the signer owns the NFT
- Nonce is valid within a ±300s window (replay protection)

**5. A2A Agent Cards:**
- Both agents serve `/.well-known/agent.json` advertising name, description, skills, and MCP endpoint
- Implemented as simple `GET` endpoints returning a hardcoded dict; no dynamic discovery

**6. MCP server mounted on FastAPI:**
- `mcp.http_app()` creates a Starlette sub-application; mounted at root with `app.mount("/", _mcp_http_app)` after all REST routes
- The MCP endpoint resolves to `/mcp` internally
- **CRITICAL ORDERING:** REST routes are registered before the mount so Starlette's router checks them first. Reversing this order would shadow REST routes with the MCP catch-all. See comment in `provider/app.py:210`.

---

## 5. ENTRY POINTS

| Entry point | Command | Port |
|---|---|---|
| Provider API | `uvicorn provider.app:app --port 8002` | 8002 |
| Gateway | `uvicorn provider.gateway:app --port 8003` | 8003 |
| Consumer API | `uvicorn consumer.app:app --port 8001` | 8001 |
| Consumer UI | `streamlit run consumer/ui.py` | 8501 |

### Boot sequence — Provider (`provider/app.py`)

1. Module-level: `w3` and `provider_account` initialized from `RPC_URL` + `PROVIDER_PRIVATE_KEY`
2. `_mcp_http_app = mcp.http_app()` — FastMCP creates its Starlette sub-application
3. `lifespan` context manager is registered on the FastAPI app
4. **On startup** (inside `lifespan`): `_mcp_http_app.lifespan(app)` context entered (FastMCP initializes its transport), then `asyncio.create_task(_event_listener())` spawns the blockchain event poll loop
5. `_event_listener()` polls `escrow.events.AgreementRequested.get_logs(...)` every 2 seconds. On each matching event, spawns `asyncio.create_task(_handle_agreement(...))` which mints NFT → approves escrow → calls `deposit()`
6. REST routes respond immediately; MCP endpoint at `/mcp` serves tool discovery and calls

### Boot sequence — Consumer (`consumer/app.py`)

1. Module-level: `w3`, `consumer_account`, `inter_agent_log`, `_logged_interactions` initialized
2. FastAPI app registered with no lifespan hooks
3. On `POST /chat`: calls `run_consumer(message, model)` which is an `async` function
4. Inside `run_consumer`: `await get_provider_tools()` opens an MCP client session to `PROVIDER_MCP_URL` to fetch tool schemas; builds combined tool list; enters the 12-iteration LLM loop

### Contract deployment (one-time, `contracts/script/Deploy.s.sol`)

1. `forge script` runs `Deploy.run()`
2. Deploys `BandwidthNFT(providerAddress)` — provider EOA becomes the Ownable owner (only they can mint)
3. Deploys `BandwidthEscrow(nftAddress)`
4. Writes `contracts/deployments/local.json` with both addresses

---

## 6. DATA MODELS & SCHEMA

### Solidity: `Agreement` struct (`BandwidthEscrow.sol:30`)

```
Agreement {
  consumer        address    — consumer EOA
  provider        address    — provider EOA
  bandwidthMbps   uint256
  durationSeconds uint256
  priceWei        uint256    — msg.value from requestAgreement
  requestDeadline uint256    — block.timestamp + 1 hour
  tokenId         uint256    — set to 0 until deposit(), then NFT token ID
  status          Status     — NONE(0)|REQUESTED(1)|ACTIVE(2)|CLOSED(3)|CANCELLED(4)
}
```

Stored in `mapping(uint256 => Agreement) private _agreements` keyed by `agreementId`.

### Solidity: `TokenMetadata` struct (`BandwidthNFT.sol:12`)

```
TokenMetadata {
  agreementId     uint256
  bandwidthMbps   uint256
  durationSeconds uint256
  startTime       uint256    — block.timestamp at mint
  endpoint        string     — "grpc://provider:8003" (hardcoded in provider/app.py)
}
```

Stored in `mapping(uint256 => TokenMetadata) private _metadata` keyed by `tokenId`. All on-chain; no IPFS.

### Python: Catalog entry (`provider/catalog.py:9`)

```python
{
  "packageId": "small"|"medium"|"large",
  "mbps": int,           # 50 | 100 | 500
  "durationSeconds": int, # 600 for all tiers
  "priceWei": int,        # Web3.to_wei(0.01|0.02|0.08, "ether")
}
```

Extended with `"availableSlots": int` when returned by `get_catalog_with_availability()`.

### Python: Quote dict (`provider/catalog.py:118`, stored in `pending_quotes`)

```python
pending_quotes: dict[int, dict]  # keyed by agreementId (128-bit random int)
# value:
{
  "packageId": str,
  "consumerAddress": str,
  "expires": float,        # time.time() + 60
  "priceWei": int,
  "bandwidthMbps": int,
  "durationSeconds": int,
}
```

Quote TTL is 60 seconds. Cleanup happens inside `_handle_agreement()` before processing.

### Python: Quote response (returned to consumer via MCP, cached in `quote_cache`)

```python
{
  "agreementId": int,      # 128-bit random
  "priceWei": int,
  "bandwidthMbps": int,
  "durationSeconds": int,
}
```

`consumer/mcp_client.py:quote_cache` is `dict[str, dict]` — keyed by `str(agreementId)` because JSON loses int precision for 128-bit integers.

### Python: Inventory row (`provider/inventory.txt`, JSONL)

```json
{"tier": "small", "mbps": 50, "durationSeconds": 600, "totalSlots": 10, "activeLeases": [
  {"agreementId": int, "expiresAt": float}
]}
```

One JSON line per tier. Leases with `expiresAt < time.time()` are pruned on every read.

### Python: Inter-agent log entry (`consumer/app.py:38`)

```python
{"from": "consumer"|"provider", "message": str}
```

Stored in module-level `inter_agent_log: list[dict]`. Cleared at the start of each `run_consumer()` call.

### Python: ChatRequest / ChatResponse (`consumer/app.py:358`)

```python
ChatRequest:  { message: str, model: str }
ChatResponse: { response: str, log: list[dict], thinking: list[str] }
```

### Python: AGENT_CARD (`consumer/app.py:41`, `provider/app.py:40`)

```python
{
  "name": str,
  "description": str,
  "version": "1.0.0",
  "protocols": list[str],   # ["mcp", "a2a"] or ["mcp"]
  "mcp_endpoint": "/mcp",   # provider only
  "skills": [{"id": str, "name": str, "description": str}]
}
```

### Gateway response (`provider/gateway.py:79`)

```python
{
  "token_id": int,
  "agreement_id": int,
  "bandwidth_mbps": int,
  "duration_seconds": int,
  "seconds_remaining": int,
  "status": str,
  "endpoint": str,
  "signer": str,   # recovered Ethereum address
}
```

---

## 7. API & INTERFACES

### Provider Agent (:8002)

| Method | Path | Input | Output | Side effect |
|---|---|---|---|---|
| GET | `/.well-known/agent.json` | — | `AGENT_CARD` dict | none |
| GET | `/catalog` | — | `list[CatalogEntry]` with `availableSlots` | reads+rewrites inventory.txt |
| POST | `/quote` | `{packageId: str, consumerAddress: str}` | quote dict or 409 | adds to `pending_quotes` |
| GET | `/inventory` | — | same as `/catalog` | same |
| GET | `/address` | — | `{"address": str}` | none |
| `/mcp` | MCP HTTP transport | MCP protocol | MCP protocol | tool calls execute catalog/quote logic |

**MCP tools (at `/mcp`):**
- `get_catalog() -> str` — JSON array of catalog entries with availability
- `request_quote(package_id: str, consumer_address: str) -> str` — JSON quote or `{"error": ...}`

### Gateway (:8003)

| Method | Path | Input | Output |
|---|---|---|---|
| GET | `/service` | `?tokenId=N`, headers `X-Nonce`, `X-Signature` | gateway response dict or 400/401/403/404 |

### Consumer Agent (:8001)

| Method | Path | Input | Output | Side effect |
|---|---|---|---|---|
| GET | `/.well-known/agent.json` | — | `AGENT_CARD` dict | none |
| POST | `/chat` | `ChatRequest` | `ChatResponse` | runs LLM loop, executes on-chain txs, writes inter_agent_log |
| GET | `/log` | — | `list[dict]` | none |
| DELETE | `/log` | — | `{"cleared": True}` | clears `inter_agent_log` |
| GET | `/catalog_proxy` | — | `list[dict]` | calls provider MCP `get_catalog` |
| GET | `/address` | — | `{"address": str}` | none |
| GET | `/check_token` | `?tokenId=N` | gateway response dict | calls gateway `/service` with consumer's signature |

### LLM tool interfaces (consumer/app.py)

**`execute_agreement(agreement_id: str) -> str`**
- Reads `quote_cache[agreement_id]` for priceWei, mbps, duration
- Calls `_get_provider_address()` (HTTP GET to provider `/address`)
- Calls `escrow.functions.requestAgreement(aid, provider, mbps, duration)` with `value=priceWei`
- Returns success string or error string

**`check_agreement_status(agreement_id: str) -> str`**
- Calls `escrow.functions.getAgreement(aid).call()` for status
- If ACTIVE: signs nonce, calls gateway `/service`, returns service details
- If not ACTIVE: returns retry prompt

### Smart contract interfaces

**`BandwidthEscrow`**
- `requestAgreement(agreementId, provider, bandwidthMbps, durationSeconds) payable` — consumer locks ETH
- `deposit(agreementId, tokenId)` — provider calls after NFT approval; triggers atomic swap
- `cancel(agreementId)` — consumer anytime, or anyone after deadline
- `getAgreement(agreementId) view returns (Agreement)` — returns full Agreement struct
- Events: `AgreementRequested(indexed agreementId, consumer, provider, mbps, duration, price)`, `AgreementActive(agreementId, tokenId, consumer, provider)`, `AgreementCancelled(agreementId, consumer)`

**`BandwidthNFT`**
- `mint(to, agreementId, bandwidthMbps, durationSeconds, endpoint) onlyOwner returns (tokenId)`
- `getTokenMetadata(tokenId) view returns (TokenMetadata)`
- Inherits: `ownerOf(tokenId)`, `approve(to, tokenId)`, `safeTransferFrom(...)`

---

## 8. STATE MANAGEMENT

### Provider-side state

| State | Location | Type | Mutated by |
|---|---|---|---|
| Pending quotes | `provider/catalog.py:pending_quotes` | `dict[int, dict]` in-memory | `make_quote()` adds; `cleanup_quotes()` + explicit `del` in `_handle_agreement()` remove |
| Slot inventory | `provider/inventory.txt` | JSONL file, fcntl-locked | `decrement_inventory()` adds lease; `rewind_inventory()` removes; pruned on every read |
| On-chain agreements | `BandwidthEscrow._agreements` | Solidity mapping | `requestAgreement()`, `deposit()`, `cancel()` |
| NFT ownership | `BandwidthNFT._metadata` + ERC-721 base | Solidity mappings | `mint()`, `safeTransferFrom()` |

### Consumer-side state

| State | Location | Type | Lifetime |
|---|---|---|---|
| Quote cache | `consumer/mcp_client.py:quote_cache` | `dict[str, dict]` in-memory | Process lifetime; populated by `call_provider_tool("request_quote", ...)` |
| Inter-agent log | `consumer/app.py:inter_agent_log` | `list[dict]` in-memory | Cleared at each `run_consumer()` call |
| LLM message history | Local var in `run_consumer()` | `list[dict]` | Per-request; discarded after response |

### UI state (Streamlit session_state)

| Key | Type | Purpose |
|---|---|---|
| `chat_history` | `list[dict]` | Full chat messages for the left column |
| `timeline` | `list[dict]` | Accumulated phase entries (cumulative, not reset each turn) |
| `turn` | `int` | Monotonically increasing turn counter |
| `ui_state_version` | int (3) | Version-gated state reset on schema changes |

Streamlit state is client-session-scoped and does not persist across page reloads.

---

## 9. DEPENDENCY MAP

### Key imports per file

**`provider/app.py`** imports from:
- `provider.catalog` (all catalog/quote functions)
- `provider.mcp_server` (the `mcp` instance)
- `shared.contracts` (`get_escrow_contract`, `get_nft_contract`)
- `web3`, `eth_account`, `fastapi`, `uvicorn`, `asyncio`

**`provider/mcp_server.py`** imports from:
- `provider.catalog` (`get_catalog_with_availability`, `make_quote`)
- `fastmcp` (`FastMCP`)

**`provider/catalog.py`** imports from:
- `web3` (only `Web3.to_wei` at module level)
- stdlib only (`fcntl`, `json`, `secrets`, `time`, `pathlib`)

**`provider/gateway.py`** imports from:
- `shared.contracts`
- `web3`, `eth_account`, `fastapi`, `uvicorn`

**`consumer/app.py`** imports from:
- `consumer.mcp_client` (`call_provider_tool`, `get_provider_tools`, `mcp_tool_to_ollama`, `quote_cache`)
- `shared.contracts`
- `web3`, `eth_account`, `ollama`, `httpx`, `fastapi`

**`consumer/mcp_client.py`** imports from:
- `fastmcp` (`Client`)
- stdlib only (`json`, `os`, `typing`)

**`consumer/ui.py`** imports from:
- `httpx`, `streamlit`, `web3` (only for `Web3.from_wei`)
- No import from any local Python module — communicates only via HTTP

**`shared/contracts.py`** imports from:
- `web3`, `json`, `pathlib`
- Reads from filesystem: `contracts/deployments/local.json`, `shared/abi/*.json`

### Most-imported shared files

1. `shared/contracts.py` — imported by `provider/app.py`, `provider/gateway.py`, `consumer/app.py`
2. `provider/catalog.py` — imported by `provider/app.py`, `provider/mcp_server.py`

### No circular dependencies detected.

---

## 10. CONFIGURATION & ENVIRONMENT

### Environment variables

| Variable | Required | Default | What it controls | Breaks if missing/wrong |
|---|---|---|---|---|
| `PROVIDER_PRIVATE_KEY` | YES | — | Provider EOA key; used to sign all provider txs and is the NFT contract owner | provider/app.py raises `KeyError` on startup |
| `CONSUMER_PRIVATE_KEY` | YES | — | Consumer EOA key; used to sign consumer txs and gateway nonces | consumer/app.py raises `KeyError` on startup |
| `DEPLOYER_PRIVATE_KEY` | YES (deploy only) | — | Used by `Deploy.s.sol` to deploy contracts | Deploy script fails |
| `PROVIDER_ADDRESS` | YES (deploy only) | — | Passed to `BandwidthNFT` constructor as initial Ownable owner | NFT minting will revert if wrong |
| `RPC_URL` | No | `http://localhost:8545` | Ethereum JSON-RPC endpoint for all services | All on-chain calls fail silently |
| `PROVIDER_BASE_URL` | No | `http://localhost:8002` | Consumer → provider REST base URL (for `/address` call) | `execute_agreement` fails |
| `GATEWAY_BASE_URL` | No | `http://localhost:8003` | Consumer → gateway base URL | `check_agreement_status` fails |
| `PROVIDER_MCP_URL` | No | `http://localhost:8002/mcp` | MCP endpoint for consumer's FastMCP client | LLM has no provider tools; purchases impossible |
| `CONSUMER_BASE_URL` | No | `http://localhost:8001` | UI → consumer agent base URL | UI cannot reach backend |
| `OLLAMA_MODEL` | No | `qwen3:4b` | Default LLM model name | Falls back to `qwen3:4b`; fails if model not pulled |
| `OLLAMA_HOST` | No | unset (Ollama default) | Ollama server URL for Docker containers | In Docker: consumer can't reach the Ollama container |

### Config files

| File | Role |
|---|---|
| `pyproject.toml` | uv project definition, Python version, all deps |
| `uv.lock` | Locked dependency graph — must be committed and kept in sync |
| `.env` | Runtime env vars — committed in this repo with Anvil test keys (not for prod) |
| `.env.example` | Template with documentation |
| `.python-version` | uv Python version pin |
| `.streamlit/config.toml` | Dark theme for Streamlit |
| `contracts/deployments/local.json` | Auto-generated by `Deploy.s.sol` — both services read this at every request via `shared/contracts.py`. If this file is absent, all contract calls raise `FileNotFoundError`. |
| `provider/inventory.txt` | Runtime state for slot inventory — must exist before provider starts. Lost on container restart unless volume-mounted. |
| `.claude/settings.local.json` | Claude Code project permissions |

### Docker networking

In Docker Compose, all services communicate by container name:
- `http://anvil:8545` — blockchain
- `http://provider-agent:8002` — provider REST + MCP
- `http://provider-agent:8003` — gateway
- `http://consumer-agent:8001` — consumer
- `http://ollama:11434` — LLM inference

The `consumer-agent` service sets `OLLAMA_HOST=http://ollama:11434`. If you run locally without Docker, Ollama must be running on localhost:11434 (its default).

---

## 11. KNOWN QUIRKS & CONSTRAINTS

1. **`quote_cache` uses string keys, `pending_quotes` uses int keys.** The `agreementId` is a 128-bit random integer. JSON cannot round-trip a 128-bit int faithfully. `consumer/mcp_client.py:quote_cache` stores it as `str(agreementId)` to avoid precision loss. `provider/catalog.py:pending_quotes` uses raw `int`. When `execute_agreement` calls `int(agreement_id)` to parse the string back, this works — but if the ID were ≥2^53 and went through JavaScript JSON parsing it would corrupt. This is acceptable for local use but would need `BigInt` handling for a browser-native consumer.

2. **`_send_tx` compatibility shim.** `provider/app.py:69` and `consumer/app.py:96` both do `getattr(signed, "raw_transaction", None) or signed.rawTransaction`. This is because older web3.py versions use `rawTransaction`, newer use `raw_transaction`. Without this shim, the provider's `_send_tx` raises `AttributeError` on some dependency versions.

3. **MCP mount ordering is load-bearing.** In `provider/app.py`, `app.mount("/", _mcp_http_app)` must come after all `@app.get(...)` / `@app.post(...)` route registrations. FastMCP's sub-application would otherwise shadow `/catalog`, `/quote`, etc. There is a comment in the file at line 210 explaining this. Do not reorder.

4. **FastMCP lifespan is nested inside FastAPI lifespan.** `provider/app.py:168-171` wraps the FastMCP app's lifespan context manager (`async with _mcp_http_app.lifespan(app):`). This is mandatory — FastMCP requires its lifespan to run for the transport to initialize. Removing this nesting breaks MCP. The event listener task is created inside the same lifespan context.

5. **MCP client opens a new connection per call.** `consumer/mcp_client.py` opens and closes an `async with Client(PROVIDER_MCP_URL) as client:` for every `get_provider_tools()` and `call_provider_tool()` invocation. This is correct but adds ~1 round-trip of latency per tool call. For a purchase flow (2 MCP calls), this is acceptable but would be a bottleneck if tools were called many times.

6. **Inventory is file-backed, not database-backed.** `provider/inventory.txt` is written by `catalog.py` with `fcntl.LOCK_EX`. This works in a single-container deployment but breaks if provider is horizontally scaled (multiple processes writing the same file would race even with fcntl). The file is Docker volume-mounted for persistence; losing the mount loses all slot state.

7. **`pending_quotes` is in-process memory on the provider.** If the provider restarts between a consumer's `request_quote` and the `AgreementRequested` event, the provider will not find the quote and will log "No valid quote for agreementId=X, skipping." The consumer's ETH remains locked in escrow and must be manually cancelled after the 1-hour deadline. No automatic recovery exists.

8. **NFT mint-before-approve-before-deposit is a three-step sequence.** If the provider crashes after minting but before `deposit()`, the NFT is orphaned (minted but not in escrow). `provider/app.py:161` logs this case explicitly ("NFT tokenId=X is orphaned"). No on-chain recovery mechanism exists.

9. **The `endpoint` field in NFT metadata is hardcoded.** `provider/app.py:143` always mints with `"grpc://provider:8003"` as the endpoint. This is a Docker container name, meaningless outside Docker. For local dev, the endpoint value in the NFT is wrong (gateway runs at `localhost:8003`), but the gateway is found via `GATEWAY_BASE_URL` env var, not the NFT endpoint.

10. **`_extract_token_id` is fragile.** `provider/app.py:77-81` parses the Transfer event log by matching the event signature hash and reading `topics[3]`. This assumes ERC-721's `Transfer(from, to, tokenId)` where the 4th topic is the tokenId. If OpenZeppelin changes their event encoding, this breaks silently. A safer approach would use the web3.py event decoder.

11. **Legacy files (`app.py`, `consumer_agent.py`, `provider_server.py`) are not deleted.** They are dead code — `consumer_agent.py` calls `provider_server.py` over HTTP with no blockchain. They share no imports with the current `consumer/`, `provider/`, `shared/` packages. Do not attempt to run them alongside the current stack (port conflicts). They exist for historical reference.

12. **`think=False` in Ollama call.** `consumer/app.py:299` passes `think=False` to the Ollama chat API to disable native chain-of-thought. Thinking chunks emitted in `<think>...</think>` tags in `msg.content` are still parsed by `_extract_thinking()` — this is a belt-and-suspenders approach for models that emit thinking in content anyway.

13. **QUOTE_TTL is 60 seconds globally.** If the consumer's LLM loop takes more than 60 seconds between `request_quote` and `execute_agreement` (e.g., model is slow), the provider will reject the agreement as expired even though ETH was locked. The consumer would need to re-quote.

---

## 12. HOW TO MAKE SAFE MODIFICATIONS

### High-sensitivity files (change with care)

| File | Why sensitive | What to verify after change |
|---|---|---|
| `provider/app.py` | MCP lifespan nesting; mount ordering; event listener task; `_send_tx` compat shim | MCP tools still discoverable at `/mcp`; provider REST routes still respond; AgreementRequested events still handled |
| `provider/catalog.py` | File locking logic; quote TTL; inventory slot math | Run `tests/test_catalog.py`; verify slot counts decrement and rewind correctly |
| `consumer/app.py` | LLM loop iteration limit; tool dispatch routing (MCP vs. local); quote_cache key type | Full end-to-end purchase still completes; `check_agreement_status` still signs nonce correctly |
| `shared/contracts.py` | Single source for contract addresses and ABIs; all services depend on it | Any change here breaks all three services simultaneously |
| `contracts/src/BandwidthEscrow.sol` | ABI changes require regenerating `shared/abi/BandwidthEscrow.json` and redeploying | After Solidity change: `forge build`, copy ABI, redeploy, update `local.json` |
| `contracts/src/BandwidthNFT.sol` | Same as above; also: changing `TokenMetadata` struct fields breaks `_extract_token_id` and gateway tuple unpacking | Same as above, plus verify `provider/gateway.py:67` tuple unpack matches new struct order |

### Tightly coupled pairs (change one → must change the other)

- `BandwidthEscrow.sol getAgreement()` tuple order ↔ `consumer/app.py:agreement[N]` index accesses (indices 2,3,4,6,7 are used)
- `BandwidthNFT.sol TokenMetadata` struct field order ↔ `provider/gateway.py:67` destructuring (`agreement_id, bandwidth_mbps, duration_seconds, start_time, endpoint = meta`)
- `provider/catalog.py make_quote()` return keys ↔ `consumer/mcp_client.py call_provider_tool()` cache population (checks for `"agreementId"` key)
- `provider/mcp_server.py request_quote()` → changes to parameter names change the MCP tool's `inputSchema` → must update consumer's system prompt tool description
- `provider/inventory.txt` schema (JSONL field names) ↔ `provider/catalog.py` `_read_inventory_locked()` / `_write_inventory_locked()`

### What to test after any change

1. **After any Python change:** `uv run pytest tests/` — covers catalog logic and MCP client schema conversion
2. **After any change to `provider/app.py` or `provider/mcp_server.py`:** Manually verify MCP tools are listed at `http://localhost:8002/mcp` and can be called
3. **After any Solidity change:** `cd contracts && forge test` (if tests exist), then redeploy and update `shared/abi/`
4. **After any change to the LLM loop (`consumer/app.py`):** Run `make demo` — a full purchase flow via curl
5. **After any env var change:** Verify `docker-compose.yml` passes the variable to all services that need it
6. **After any change to `consumer/ui.py`:** Run Streamlit locally and complete a purchase; check the stepper bar, timeline phases, and catalog card render correctly

### Safe areas to modify

- `consumer/ui.py` — pure display logic; changes do not affect any backend
- `paper/` — LaTeX only
- `Makefile` — build targets only
- `README.md`
- System prompt in `consumer/app.py:SYSTEM_PROMPT_TEMPLATE` — changes affect LLM behavior but not data integrity; test by running a purchase
- Tier pricing in `provider/catalog.py:CATALOG` — safe if `inventory.txt` is updated to match; no Solidity change needed (price is passed at runtime)
- Tier slot counts in `provider/inventory.txt` — can be edited while provider is stopped
