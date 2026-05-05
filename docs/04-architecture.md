# Architecture Reference

> **Audience:** developers reading or modifying the code. Assumes you have already read [`01-introduction.md`](01-introduction.md) and the concepts you need from [`02-concepts.md`](02-concepts.md). For end-to-end behaviour, read [`03-walkthrough.md`](03-walkthrough.md) first.

---

## 1. PROJECT IDENTITY

**ollama-agent-simulation** is a proof-of-concept multi-agent simulation where two autonomous AI agents — a Consumer and a Provider — negotiate, pay for, and activate internet bandwidth packages without human intervention.

Architecturally it follows the paper's split:
- **A2A is the inter-agent protocol.** Consumer ↔ Provider talk over Google's Agent2Agent SDK (JSON-RPC `message/send`, agent cards at `/.well-known/agent-card.json`). The provider's three skills are `get_catalog`, `request_quote`, and `activate`.
- **MCP is the intra-agent tool-invocation protocol.** Each agent runs its own FastMCP server. The LLM (or the inbound A2A executor) only calls its own MCP — never the other agent's. Cross-agent calls are wrapped inside MCP tools that internally use A2A.
- **SDN activation is real.** On `activate`, the provider verifies the NFT credential then calls `srl_bandwidth.allocate_bandwidth` (gNMI policer push to Nokia SR Linux + Linux `tc tbf` on the connected CE container) via the sibling repo `srl-gnmi-bandwidth-poc`. `SDN_MOCK=true` short-circuits this for CI/dev.
- **Atomic on-chain settlement.** Consumer locks ETH via `BandwidthEscrow.requestAgreement`; provider mints an ERC-721 credential via `BandwidthNFT.mint`; `BandwidthEscrow.deposit` swaps ETH→provider and NFT→consumer atomically. The previous standalone gateway service is gone — its role (signature/nonce/ownerOf check) is now an MCP tool the activate-handler calls.

This is a research prototype accompanying an academic paper.

---

## 2. TECH STACK SUMMARY

| Component | Version | Role |
|---|---|---|
| Python | ≥3.13 | Runtime for all Python services |
| uv | 0.8.22 | Dependency & venv management |
| FastAPI | ≥0.136.0 | HTTP framework for consumer (:8001), provider (:8002) |
| Uvicorn | ≥0.44.0 (standard) | ASGI server |
| FastMCP | ≥3.2.4 | Per-agent MCP server (provider + consumer); used in-memory via `Client(mcp)` |
| a2a-sdk | ≥1.0,<2.0 | Inter-agent protocol — agent cards, JSON-RPC `message/send`, executor |
| srl-bandwidth | git pin | Brother repo: gNMI policer push + Linux tc enforcement (real SDN) |
| Ollama Python SDK | ≥0.6.1 | Drives local LLM inference; `ollama.AsyncClient` for tool-calling loop |
| Streamlit | ≥1.56.0 | Chat UI at :8501 |
| web3.py | ≥6.0,<7 | Ethereum JSON-RPC client; signs and sends transactions |
| eth-account | ≥0.11.3 | Key management, signing, signature recovery |
| httpx | ≥0.28.1 | Sync/async HTTP client (UI→consumer, consumer→provider via A2A) |
| Pydantic | (bundled with FastAPI) | Request/response validation |
| Solidity | ^0.8.20 | Smart contract language |
| Foundry (forge, anvil) | latest | EVM toolchain; Anvil runs the local chain at :8545 |
| OpenZeppelin Contracts | (Foundry lib) | ERC-721 base (`ERC721`, `ERC721Holder`, `Ownable`) |
| Docker / Docker Compose v2 | — | Container orchestration for the full stack |
| Ollama (container) | latest | Hosts LLM models locally; serves at :11434 inside Docker |
| llama3.2:3b / llama3.2:1b | — | Default LLM models; must support tool-calling |
| pytest | ≥9.0.3 | Unit tests |
| pytest-asyncio | ≥1.3.0 | Async test support |

---

## 3. FULL DIRECTORY TREE

```
ollama-agent-simulation/
├── consumer/                  # Consumer agent package
│   ├── __init__.py
│   ├── app.py                 # FastAPI :8001 — LLM loop, agent card, /catalog_proxy
│   ├── agent_card.py          # a2a.types.AgentCard for the consumer
│   ├── a2a_client.py          # send_provider_action(url, payload) — single A2A round-trip
│   ├── mcp_server.py          # FastMCP — wallet/sign/lock_payment/await + browse/quote/present
│   └── ui.py                  # Streamlit app :8501
├── provider/                  # Provider agent package
│   ├── __init__.py
│   ├── app.py                 # FastAPI :8002 — catalog/quote REST + A2A JSON-RPC routes + event listener
│   ├── agent_card.py          # a2a.types.AgentCard for the provider (3 skills: catalog, quote, activate)
│   ├── agent_executor.py      # BandwidthProviderExecutor — A2A → in-memory MCP bridge
│   ├── catalog.py             # CATALOG dict + slot_pool reference + pending_quotes
│   ├── expiry.py              # Asyncio sweep that revokes SDN on slot lease expiry
│   ├── mcp_server.py          # FastMCP — 8 tools (catalog, quote, verify, mint, swap, allocate/revoke/verify_bw)
│   └── inventory.txt          # Mutable state: per-tier slots with (pe, subinterface, ce) bindings (JSONL)
├── shared/                    # Cross-service utilities
│   ├── __init__.py
│   ├── a2a_messages.py        # Pydantic schemas for A2A `data` parts (request/response shapes)
│   ├── contracts.py           # Loads deployed addresses + returns web3 contract objects
│   ├── slot_pool.py           # File-backed (pe, subinterface, ce) slot reservations, fcntl-locked
│   └── abi/
│       ├── BandwidthEscrow.json  # ABI for BandwidthEscrow — used by provider/app.py, consumer/app.py, provider/mcp_server.py
│       └── BandwidthNFT.json    # ABI for BandwidthNFT — used by provider/app.py, consumer/app.py, provider/mcp_server.py
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
│   ├── test_agent_executor.py # A2A executor end-to-end (catalog/quote/error)
│   ├── test_catalog.py        # CATALOG rescale + make_quote
│   ├── test_consumer_mcp.py   # Consumer MCP: wallet/sign/lock + A2A-bound (mocked)
│   ├── test_provider_mcp.py   # Provider MCP: verify_credential / mint / swap (mocked)
│   └── test_slot_pool.py      # SlotPool: reserve / release / lookup / expiry reclaim
├── Dockerfile.provider        # Multi-stage image: runs provider/app.py only
├── Dockerfile.consumer        # Multi-stage image: runs consumer/app.py (and also ui.py via override)
├── docker-compose.yml         # Orchestrates: anvil, deployer, ollama, provider-agent, consumer-agent[, -2], consumer-ui
├── Makefile                   # Targets: up, down, down-clean, logs, contracts, demo, clab-up, clab-down, demo-real
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
```

### File annotations

| File | Exports / Exposes | Imported by |
|---|---|---|
| `provider/catalog.py` | `CATALOG`, `CATALOG_BY_ID`, `pending_quotes`, `get_catalog_with_availability`, `make_quote`, `decrement_inventory`, `rewind_inventory`, `cleanup_quotes` | `provider/app.py`, `provider/mcp_server.py` |
| `provider/mcp_server.py` | `mcp` (FastMCP instance with tools `get_catalog`, `request_quote`) | `provider/app.py` |
| `provider/app.py` | FastAPI `app`; endpoints: `/.well-known/agent.json`, `/catalog`, `/quote`, `/inventory`, `/address`, `/mcp` | Entry point via uvicorn |
| `consumer/mcp_server.py` | `mcp` (FastMCP instance with tools `wallet_address`, `sign_message`, `lock_payment`, `await_settlement`, `browse_catalog`, `request_quote`, `present_credential`), `quote_cache` | `consumer/app.py`, `consumer/graph.py` |
| `consumer/graph.py` | `build_graph()` — LangGraph state machine nodes for the six-stage workflow | `consumer/app.py` |
| `consumer/a2a_client.py` | `send_provider_action(url, payload)` — single A2A round-trip to provider | `consumer/mcp_server.py` |
| `consumer/agent_card.py` | `build_consumer_agent_card()` — returns `a2a.types.AgentCard` for the consumer | `consumer/app.py` |
| `consumer/app.py` | FastAPI `app`; endpoints: `/.well-known/agent.json`, `/chat`, `/log`, `/address`, `/catalog_proxy`, `/check_token` | Entry point via uvicorn; called by `consumer/ui.py` |
| `consumer/ui.py` | Streamlit app; calls `consumer/app.py` over HTTP | Standalone — run with `streamlit run` |
| `shared/contracts.py` | `get_nft_contract(w3)`, `get_escrow_contract(w3)` | `provider/app.py`, `provider/mcp_server.py`, `consumer/app.py` |
| `shared/abi/BandwidthEscrow.json` | ABI array | `shared/contracts.py` |
| `shared/abi/BandwidthNFT.json` | ABI array | `shared/contracts.py` |
| `contracts/deployments/local.json` | `{"bandwidthNFT": "0x...", "bandwidthEscrow": "0x..."}` | `shared/contracts.py` |
| `provider/inventory.txt` | JSONL file — one row per tier, with `tier`, `mbps`, `durationSeconds`, `totalSlots`, `activeLeases[]` | `provider/catalog.py` (r/w with fcntl locking) |

---

## 4. ARCHITECTURE & PATTERNS

### Pattern: A2A inter-agent + per-agent MCP

Three HTTP services (consumer :8001, provider :8002, anvil :8545) communicate over the network. Each agent runs its own in-process FastMCP server; the LLM and the inbound A2A executor only talk to their own MCP. Cross-agent calls always go over A2A.

```
Browser
  │ POST /chat
  ▼
consumer/ui.py :8501          (Streamlit — thin HTTP client)
  │ POST /chat
  ▼
consumer/app.py :8001         (FastAPI — owns the LLM agentic loop)
  │
  ▼
[in-memory] Client(consumer_mcp)
  │
  ├─ wallet_address / sign_message / lock_payment / await_settlement   (local tools)
  │
  └─ browse_catalog / request_quote / present_credential
        │
        └─ a2a-sdk message/send ──────────────────────► provider :8002/a2a
                                                          DefaultRequestHandler
                                                          → BandwidthProviderExecutor
                                                          → [in-memory] Client(provider_mcp)
                                                            ├─ get_catalog
                                                            ├─ request_quote
                                                            ├─ verify_credential_ownership
                                                            ├─ allocate_bandwidth (SDN)
                                                            ├─ mint_credential (web3)
                                                            └─ complete_swap (web3)

[web3] requestAgreement() ───────────────────────────► Anvil :8545
                                                        (Ethereum chain)
                AgreementRequested event ◄──────────── provider/app.py polls
                provider reserves slot, mints NFT, deposits → atomic swap
```

### Key patterns in use

**1. LLM Tool-calling loop (consumer/app.py + consumer/graph.py):**
- The workflow is a LangGraph state machine built by `build_graph()`. The LLM is consulted at `pick_tier_node` (which tier?) and `summary_node` (one-sentence reply); all on-chain and A2A calls are deterministic Python.
- `consumer/app.py` opens an in-process `MCPClient(consumer_mcp)` session (using `from fastmcp import Client as MCPClient`) to get tool schemas and call tools.
- A2A is hidden from the LLM. `browse_catalog`/`request_quote`/`present_credential` are MCP tool names in `consumer/mcp_server.py` that internally call `send_provider_action(provider_url, payload)`.

**2. Atomic double-escrow (BandwidthEscrow.sol `deposit()`):**
- Consumer calls `requestAgreement()` locking ETH → status = REQUESTED
- Provider calls `deposit(agreementId, tokenId)` → checks-effects-interactions: status set to ACTIVE first, then `safeTransferFrom` NFT to escrow then to consumer, then `call{value}` ETH to provider. If ETH transfer fails, revert (entire atomic)
- PENDING state exists in the paper's description but is never externally observable; the swap is atomic inside `deposit()`

**3. SlotPool — file-locked (pe, subinterface, ce) slot reservations (shared/slot_pool.py):**
- `inventory.txt` is JSONL with one row per tier; each row carries explicit per-slot bindings.
- `reserve(tier, agreement_id, duration_seconds)` returns a `Slot(pe, subinterface, ce)` or `None` if full.
- All reads/writes hold `fcntl.LOCK_EX`. Expired slots (`expiresAt < now`) are reclaimed on every read.
- `provider/expiry.py` runs a 30-second background sweep that revokes the SDN policy for any expired slot before releasing it.

**4. Signed-nonce credential verification (now an MCP tool):**
- The provider's MCP `verify_credential_ownership(token_id, signature, nonce)` recovers the signer with `Account.recover_message`, calls `ownerOf(tokenId)` on chain, and confirms the NFT's agreement is `ACTIVE`.
- Nonce window is ±300s. The standalone gateway service (formerly on port 8003) is gone; the activation flow now invokes this tool from `BandwidthProviderExecutor._handle_activate`.

**5. A2A Agent Cards (proto-based):**
- `a2a-sdk` 1.0.x exposes `a2a.types.AgentCard` as a protobuf-generated class. Construct with snake_case kwargs; serialize with `google.protobuf.json_format.MessageToDict(card, preserving_proto_field_name=True)`.
- Both agents serve `/.well-known/agent-card.json` (canonical) and `/.well-known/agent.json` (alias). Provider exposes 3 skills (`get_catalog`, `request_quote`, `activate`) at `/a2a` JSON-RPC.

**6. MCP server mounted on FastAPI:**
- `mcp.http_app()` is a Starlette sub-application mounted at root **after** all REST routes and after the A2A routes (`create_agent_card_routes` + `create_jsonrpc_routes`).
- Reversing the order would shadow REST/A2A with the MCP catch-all. The comment in `provider/app.py` near the mount call documents this.

---

## 5. ENTRY POINTS

| Entry point | Command | Port |
|---|---|---|
| Provider API + A2A + MCP | `uvicorn provider.app:app --port 8002` | 8002 |
| Consumer API + MCP | `uvicorn consumer.app:app --port 8001` | 8001 |
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

`consumer/mcp_server.py:quote_cache` is `dict[str, dict]` — keyed by `str(agreementId)` because JSON loses int precision for 128-bit integers.

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

---

## 7. API & INTERFACES

### Provider Agent (:8002)

| Method | Path | Input | Output | Side effect |
|---|---|---|---|---|
| GET | `/.well-known/agent-card.json` | — | proto-derived AgentCard dict | none |
| GET | `/.well-known/agent.json` | — | alias of `/agent-card.json` | none |
| POST | `/a2a` | JSON-RPC `message/send` | JSON-RPC response (Task + artifact) | dispatches to `BandwidthProviderExecutor` |
| GET | `/catalog` | — | `list[CatalogEntry]` with `availableSlots` | reads inventory via SlotPool |
| POST | `/quote` | `{packageId, consumerAddress}` | quote dict or 409 | adds to `pending_quotes` |
| GET | `/inventory` | — | same as `/catalog` | same |
| GET | `/address` | — | `{"address": str}` | none |
| `/mcp` | MCP HTTP transport | MCP protocol | MCP protocol | mounted but used only in-memory by the executor; remote MCP is no longer the inter-agent path |

**A2A actions (parts[0].data.action):**
- `get_catalog` → returns `{catalog: [...]}`
- `request_quote` (`package_id`, `consumer_address`) → returns `{agreementId, priceWei, bandwidthMbps, durationSeconds}` (agreementId is stringified)
- `activate` (`token_id`, `nonce`, `signature`) → returns `{status: "active"|"denied", bandwidth_mbps, seconds_remaining, endpoint, allocation, reason?}`

**Provider MCP tools (in-memory only):**
- `get_catalog`, `request_quote`
- `verify_credential_ownership(token_id, signature, nonce)`
- `mint_credential(agreement_id, consumer_address, pe, subinterface, ce, mbps, duration_seconds)`
- `complete_swap(agreement_id, token_id)`
- `allocate_bandwidth(customer_id, pe, subinterface, mbps)` — honors `SDN_MOCK`
- `revoke_bandwidth(customer_id, pe, subinterface)`
- `verify_bandwidth(src_ce, dst_ce, expected_mbps, tolerance)`

### Consumer Agent (:8001)

| Method | Path | Input | Output | Side effect |
|---|---|---|---|---|
| GET | `/.well-known/agent-card.json` | — | proto-derived AgentCard dict | none |
| GET | `/.well-known/agent.json` | — | alias | none |
| POST | `/chat` | `ChatRequest` | `ChatResponse` | runs LLM loop over Client(consumer_mcp); on-chain txs via lock_payment; A2A round-trips inside browse/quote/present tools |
| GET | `/log` | — | `list[dict]` | none |
| DELETE | `/log` | — | `{"cleared": True}` | clears `inter_agent_log` |
| GET | `/catalog_proxy` | — | `list[dict]` | calls consumer MCP `browse_catalog(provider_url=PROVIDER_A2A_URLS[0])` |
| GET | `/address` | — | `{"address": str}` | calls consumer MCP `wallet_address` |

### Consumer MCP tools

Local (no network):
- `wallet_address() -> str`
- `sign_message(text) -> str` (hex)
- `lock_payment(agreement_id) -> "OK <txHash>"|"ERROR ..."`
- `await_settlement(agreement_id, max_attempts=8) -> "OK tokenId=N"|"PENDING"|"ERROR ..."`

A2A-bound (open a fresh `a2a-sdk` client per call, via `consumer/a2a_client.send_provider_action`):
- `browse_catalog(provider_url) -> JSON catalog`
- `request_quote(provider_url, package_id) -> JSON quote` (also caches `providerAddress` for `lock_payment`)
- `present_credential(provider_url, token_id) -> JSON activate result`

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
| Quote cache | `consumer/mcp_server.py:quote_cache` | `dict[str, dict]` in-memory | Process lifetime; populated by `request_quote` MCP tool on successful A2A round-trip |
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

**`provider/agent_executor.py`** imports from:
- `a2a.server.agent_execution`, `a2a.server.events`, `a2a.types`
- `fastmcp`, `google.protobuf.json_format`, `google.protobuf.struct_pb2`
- `provider.catalog`, `provider.mcp_server`, `shared.a2a_messages`

**`consumer/app.py`** imports from:
- `consumer.mcp_server` (`mcp as consumer_mcp`)
- `consumer.graph` (`build_graph`)
- `consumer.agent_card` (`build_consumer_agent_card`)
- `fastmcp` (`Client as MCPClient`)
- `web3`, `eth_account`, `fastapi`, `uvicorn`

**`consumer/mcp_server.py`** imports from:
- `fastmcp` (`FastMCP`, `Context`)
- `consumer.a2a_client` (`send_provider_action`)
- `web3`, `eth_account`, `shared.contracts`
- stdlib only (`json`, `os`, `typing`)

**`consumer/graph.py`** imports from:
- `consumer.mcp_server` (tool functions and `quote_cache`)
- `langgraph`, `ollama`, `fastmcp` (`Client as MCPClient`)

**`consumer/ui.py`** imports from:
- `httpx`, `streamlit`, `web3` (only for `Web3.from_wei`)
- No import from any local Python module — communicates only via HTTP

**`shared/contracts.py`** imports from:
- `web3`, `json`, `pathlib`
- Reads from filesystem: `contracts/deployments/local.json`, `shared/abi/*.json`

### Most-imported shared files

1. `shared/contracts.py` — imported by `provider/app.py`, `provider/mcp_server.py`, `consumer/app.py`
2. `provider/catalog.py` — imported by `provider/app.py`, `provider/mcp_server.py`

### No circular dependencies detected.

---

## 10. CONFIGURATION & ENVIRONMENT

### Environment variables

| Variable | Required | Default | What it controls | Breaks if missing/wrong |
|---|---|---|---|---|
| `PROVIDER_PRIVATE_KEY` | YES | — | Provider EOA key; used to sign all provider txs and is the NFT contract owner | provider/app.py raises `KeyError` on startup |
| `CONSUMER_PRIVATE_KEY` | YES | — | Consumer EOA key; used to sign consumer chain transactions and credential nonces | consumer/app.py raises `KeyError` on startup |
| `DEPLOYER_PRIVATE_KEY` | YES (deploy only) | — | Used by `Deploy.s.sol` to deploy contracts | Deploy script fails |
| `PROVIDER_ADDRESS` | YES (deploy only) | — | Passed to `BandwidthNFT` constructor as initial Ownable owner | NFT minting will revert if wrong |
| `RPC_URL` | No | `http://localhost:8545` | Ethereum JSON-RPC endpoint for all services | All on-chain calls fail silently |
| `PROVIDER_BASE_URL` | No | `http://localhost:8002` | Consumer → provider REST base URL (for `/address` call) | `execute_agreement` fails |
| `PROVIDER_MCP_URL` | No | `http://localhost:8002/mcp` | MCP endpoint for consumer's FastMCP client | LLM has no provider tools; purchases impossible |
| `CONSUMER_BASE_URL` | No | `http://localhost:8001` | UI → consumer agent base URL | UI cannot reach backend |
| `OLLAMA_MODEL` | No | `llama3.2:3b` | Default LLM model name | Falls back to `llama3.2:3b`; fails if model not pulled |
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
- `http://provider-agent:8002` — provider REST + A2A + MCP
- `http://consumer-agent:8001` — consumer REST + MCP
- `http://ollama:11434` — LLM inference

The `consumer-agent` service sets `OLLAMA_HOST=http://ollama:11434`. If you run locally without Docker, Ollama must be running on localhost:11434 (its default).

---

## 11. KNOWN QUIRKS & CONSTRAINTS

1. **`quote_cache` uses string keys, `pending_quotes` uses int keys.** The `agreementId` is a 128-bit random integer. JSON cannot round-trip a 128-bit int faithfully. `consumer/mcp_server.py:quote_cache` stores it as `str(agreementId)` to avoid precision loss. `provider/catalog.py:pending_quotes` uses raw `int`. When `lock_payment` calls `int(agreement_id)` to parse the string back, this works — but if the ID were ≥2^53 and went through JavaScript JSON parsing it would corrupt. This is acceptable for local use but would need `BigInt` handling for a browser-native consumer.

2. **`_send_tx` compatibility shim.** `provider/app.py:69` and `consumer/app.py:96` both do `getattr(signed, "raw_transaction", None) or signed.rawTransaction`. This is because older web3.py versions use `rawTransaction`, newer use `raw_transaction`. Without this shim, the provider's `_send_tx` raises `AttributeError` on some dependency versions.

3. **MCP mount ordering is load-bearing.** In `provider/app.py`, `app.mount("/", _mcp_http_app)` must come after all `@app.get(...)` / `@app.post(...)` route registrations. FastMCP's sub-application would otherwise shadow `/catalog`, `/quote`, etc. There is a comment in the file at line 210 explaining this. Do not reorder.

4. **FastMCP lifespan is nested inside FastAPI lifespan.** `provider/app.py:168-171` wraps the FastMCP app's lifespan context manager (`async with _mcp_http_app.lifespan(app):`). This is mandatory — FastMCP requires its lifespan to run for the transport to initialize. Removing this nesting breaks MCP. The event listener task is created inside the same lifespan context.

5. **A2A client opens a new connection per call.** `consumer/a2a_client.send_provider_action` opens an `httpx.AsyncClient` and resolves the agent card every call — about one extra HTTP round-trip per `browse_catalog`/`request_quote`/`present_credential`. Acceptable for a purchase flow (≤3 A2A calls); would be a bottleneck if the LLM looped on these. The consumer's own MCP, by contrast, runs in-memory via `Client(consumer_mcp)`.

6. **Inventory is file-backed, not database-backed.** `provider/inventory.txt` is written by `catalog.py` with `fcntl.LOCK_EX`. This works in a single-container deployment but breaks if provider is horizontally scaled (multiple processes writing the same file would race even with fcntl). The file is Docker volume-mounted for persistence; losing the mount loses all slot state.

7. **`pending_quotes` is in-process memory on the provider.** If the provider restarts between a consumer's `request_quote` and the `AgreementRequested` event, the provider will not find the quote and will log "No valid quote for agreementId=X, skipping." The consumer's ETH remains locked in escrow and must be manually cancelled after the 1-hour deadline. No automatic recovery exists.

8. **NFT mint-before-approve-before-deposit is a three-step sequence.** If the provider crashes after minting but before `deposit()`, the NFT is orphaned (minted but not in escrow). `provider/app.py:161` logs this case explicitly ("NFT tokenId=X is orphaned"). No on-chain recovery mechanism exists.

9. **The `endpoint` field in NFT metadata encodes the slot.** `provider/mcp_server.py:mint_credential` writes `clab://{pe}/{subinterface}` so the credential is bound to a specific physical resource. The string is informational on chain; the activate path uses the `slot_pool.lookup(agreement_id)` mapping to resolve the actual `(pe, subinterface, ce)` to configure.

10. **`_extract_token_id` is fragile.** `provider/app.py:77-81` parses the Transfer event log by matching the event signature hash and reading `topics[3]`. This assumes ERC-721's `Transfer(from, to, tokenId)` where the 4th topic is the tokenId. If OpenZeppelin changes their event encoding, this breaks silently. A safer approach would use the web3.py event decoder.

11. **`think=False` in Ollama call.** `consumer/app.py:299` passes `think=False` to the Ollama chat API to disable native chain-of-thought. Thinking chunks emitted in `<think>...</think>` tags in `msg.content` are still parsed by `_extract_thinking()` — this is a belt-and-suspenders approach for models that emit thinking in content anyway.

12. **QUOTE_TTL is 60 seconds globally.** If the consumer's LLM loop takes more than 60 seconds between `request_quote` and `execute_agreement` (e.g., model is slow), the provider will reject the agreement as expired even though ETH was locked. The consumer would need to re-quote.

---

## 12. HOW TO MAKE SAFE MODIFICATIONS

### High-sensitivity files (change with care)

| File | Why sensitive | What to verify after change |
|---|---|---|
| `provider/app.py` | MCP lifespan nesting; mount ordering; event listener task; `_send_tx` compat shim | MCP tools still discoverable at `/mcp`; provider REST routes still respond; AgreementRequested events still handled |
| `provider/catalog.py` | File locking logic; quote TTL; inventory slot math | Run `tests/test_catalog.py`; verify slot counts decrement and rewind correctly |
| `consumer/app.py` | LangGraph graph construction; MCPClient session lifecycle; inter_agent_log clearing | Full end-to-end purchase still completes; inter-agent log still populated correctly |
| `shared/contracts.py` | Single source for contract addresses and ABIs; all services depend on it | Any change here breaks all three services simultaneously |
| `contracts/src/BandwidthEscrow.sol` | ABI changes require regenerating `shared/abi/BandwidthEscrow.json` and redeploying | After Solidity change: `forge build`, copy ABI, redeploy, update `local.json` |
| `contracts/src/BandwidthNFT.sol` | Same as above; also: changing `TokenMetadata` struct fields breaks `_extract_token_id` and MCP tool tuple unpacking | Same as above, plus verify `provider/mcp_server.py:135` tuple unpack matches new struct order |

### Tightly coupled pairs (change one → must change the other)

- `BandwidthEscrow.sol getAgreement()` tuple order ↔ `consumer/app.py:agreement[N]` index accesses (indices 2,3,4,6,7 are used)
- `BandwidthNFT.sol TokenMetadata` struct field order ↔ `provider/mcp_server.py:135` destructuring (`agreement_id, mbps, duration, start_time, endpoint = meta`)
- `provider/catalog.py make_quote()` return keys ↔ `consumer/mcp_server.py request_quote()` cache population (checks for `"agreementId"` key)
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
