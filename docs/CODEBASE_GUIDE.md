# Codebase Guide — Bandwidth Agent Simulation

A guided reading path for understanding this project end-to-end. Read sections in order; each builds on the last.

---

## 1. What the project does (big picture)

Two AI agents negotiate and pay for internet bandwidth, on-chain, running on your laptop.

- A **Consumer Agent** (LLM via Ollama) receives a natural-language request like *"buy me 100 Mbps"*.
- It calls a **Provider Agent** using the **Model Context Protocol (MCP)** to get a price quote.
- The consumer then locks **ETH** in a **Solidity smart contract** escrow.
- The provider detects this on-chain event, mints an **ERC-721 NFT**, and deposits it into the escrow, triggering an atomic swap.
- A **Gateway** service verifies NFT ownership on-chain before granting service access.

All of this happens without human intervention once the user types the initial message.

---

## 2. Service map

| Service | File | Port | What it does |
|---------|------|------|-------------|
| Consumer UI | `consumer/ui.py` | 8501 | Streamlit chat interface — thin HTTP client only |
| Consumer Agent | `consumer/app.py` | 8001 | FastAPI + Ollama LLM reasoning loop |
| Provider Agent | `provider/app.py` | 8002 | FastMCP server + event listener + REST catalog |
| Gateway | `provider/gateway.py` | 8003 | NFT-gated access verification |
| Anvil | (Docker) | 8545 | Local Ethereum test chain |

---

## 3. Suggested reading order

```
shared/contracts.py          ← how Python talks to the chain
contracts/src/               ← what the chain actually does
provider/catalog.py          ← the data model for packages and inventory
provider/mcp_server.py       ← how the provider exposes tools via MCP
provider/app.py              ← the provider: event loop + REST + MCP mount
provider/gateway.py          ← NFT-gated access check
consumer/mcp_client.py       ← how the consumer calls MCP tools
consumer/app.py              ← the consumer: LLM loop + blockchain calls
consumer/ui.py               ← the Streamlit UI
docs/decisions.md            ← why every non-obvious choice was made
```

---

## 4. The smart contracts

### `contracts/src/BandwidthNFT.sol`

A standard **ERC-721** token extended with on-chain metadata.

**Key struct — `TokenMetadata`:**
```
agreementId     uint256   links the NFT back to the escrow agreement
bandwidthMbps   uint256   speed tier (50, 100, or 500)
durationSeconds uint256   how long the service runs
startTime       uint256   block.timestamp at mint — when the clock starts
endpoint        string    grpc://provider:8003 — where to connect
```

- Only the contract owner (the provider EOA, set at deploy time) can call `mint()`.
- `getTokenMetadata(tokenId)` is how the Gateway reads service details.
- `_ownerOf` (not `ownerOf`) is used internally to avoid OZ v5's revert on nonexistent tokens (see D-01 in decisions.md).

### `contracts/src/BandwidthEscrow.sol`

A **double-escrow** contract: consumer locks ETH, provider locks NFT, both are released atomically.

**Agreement state machine:**
```
NONE ──requestAgreement()──► REQUESTED ──deposit()──► ACTIVE
                                 │
                             cancel()
                                 │
                                 ▼
                            CANCELLED
```

**`requestAgreement(agreementId, provider, mbps, duration)` — called by consumer:**
- Creates an `Agreement` struct keyed by `agreementId`
- Stores `msg.value` as the locked ETH price
- Sets a 1-hour `requestDeadline` (after which anyone can cancel to get the refund)
- Emits `AgreementRequested` — this is what the provider's event listener watches

**`deposit(agreementId, tokenId)` — called by provider:**
- Verifies NFT metadata matches the agreement parameters
- Marks status as `ACTIVE`
- Atomically: transfers NFT to consumer, transfers ETH to provider
- Follows checks-effects-interactions pattern to prevent reentrancy

**`cancel(agreementId)` — refund path:**
- Consumer can cancel any time while `REQUESTED`
- Anyone can cancel after `requestDeadline`
- Refunds ETH to the consumer

---

## 5. The shared layer (`shared/`)

### `shared/contracts.py`

Thin wrapper that loads deployed contract addresses from `contracts/deployments/local.json` (written by `forge script` at deploy time) and returns `web3.py` contract objects.

```python
get_nft_contract(w3)     # returns BandwidthNFT contract object
get_escrow_contract(w3)  # returns BandwidthEscrow contract object
```

Both services (consumer and provider) call these functions. The ABI JSON files live in `shared/abi/` and are copied from Foundry build artifacts.

---

## 6. The provider

### `provider/catalog.py` — packages and inventory

**`CATALOG`** — hardcoded list of three tiers:
```python
{"packageId": "small",  "mbps": 50,  "durationSeconds": 600, "priceWei": 0.01 ETH}
{"packageId": "medium", "mbps": 100, "durationSeconds": 600, "priceWei": 0.02 ETH}
{"packageId": "large",  "mbps": 500, "durationSeconds": 600, "priceWei": 0.08 ETH}
```

**`provider/inventory.txt`** — JSON-lines file, one object per tier:
```json
{"tier": "small",  "totalSlots": 10, "activeLeases": [{"agreementId": 123, "expiresAt": 1714000000}]}
{"tier": "medium", "totalSlots": 5,  "activeLeases": [...]}
{"tier": "large",  "totalSlots": 2,  "activeLeases": [...]}
```

Slot availability is computed live: `totalSlots - count(activeLeases where expiresAt > now)`. Expired leases are pruned on every read. `fcntl.flock` guards against concurrent access (works across processes, unlike a threading lock — see D-13).

**`make_quote(package_id, consumer_address)`:**
1. Checks availability
2. Generates a 128-bit random `agreementId`
3. Stores the quote in `pending_quotes` dict (in-memory, TTL 60 seconds)
4. Returns `{agreementId, priceWei, bandwidthMbps, durationSeconds}`

### `provider/mcp_server.py` — MCP tool exposure

Uses **FastMCP** to declare two tools that any MCP-compatible client can discover and call:

- `get_catalog()` — returns JSON array of packages with `availableSlots`
- `request_quote(package_id, consumer_address)` — calls `make_quote()`, returns JSON

This is mounted at `/mcp` inside `provider/app.py`.

### `provider/app.py` — the main provider service

**Three responsibilities:**

1. **REST API**: `GET /catalog`, `POST /quote`, `GET /address`, `GET /.well-known/agent.json`
2. **MCP server**: `app.mount("/", _mcp_http_app)` — mounts FastMCP at `/mcp` (mounted last so REST routes take priority)
3. **Event listener**: `_event_listener()` — background asyncio task polling Anvil every 2 seconds

**Event listener flow (`_handle_agreement`):**
```
AgreementRequested event detected
  │
  ├─ Look up pending_quotes[agreementId]
  ├─ Verify on-chain agreement params match quote (prevents quote tampering)
  ├─ decrement_inventory() — reserve a slot
  │
  ├─ nft.mint(PROVIDER_ADDRESS, agreementId, mbps, duration, endpoint)
  ├─ nft.approve(escrow_address, tokenId)
  ├─ escrow.deposit(agreementId, tokenId)  ← atomic swap fires here
  │
  └─ On failure: rewind_inventory() if NFT not yet minted; else log orphaned NFT
```

**Lifespan management**: The `asynccontextmanager lifespan` initialises the MCP HTTP app lifespan and starts the event listener task. This is the fix described in commit `9aa9c83` — the MCP lifespan must be nested inside the FastAPI lifespan.

---

## 7. The gateway (`provider/gateway.py`)

A stateless service that checks NFT ownership before serving metadata.

**`GET /service?tokenId=N`** with headers:
- `X-Nonce`: Unix timestamp string (self-expiring — no server-side nonce store needed, see D-16)
- `X-Signature`: Ethereum signature of the nonce

**Verification flow:**
1. Validate nonce is within 300-second window
2. Recover signer address from signature using `eth_account`
3. Call `nft.ownerOf(tokenId)` on-chain — if the signer doesn't own it, 403
4. Read NFT metadata via `nft.getTokenMetadata(tokenId)`
5. Read agreement status from escrow
6. Return `{bandwidth_mbps, seconds_remaining, endpoint, status, ...}`

---

## 8. The consumer

### `consumer/mcp_client.py` — MCP client utilities

```python
get_provider_tools()              # calls provider /mcp → list of Tool objects
call_provider_tool(name, args)    # calls provider /mcp → text result
mcp_tool_to_ollama(tool)          # converts MCP Tool schema → Ollama tool dict format
quote_cache                       # dict[agreementId_str → quote_dict]
```

`call_provider_tool` automatically caches `request_quote` responses in `quote_cache`. This is how `execute_agreement` in `app.py` retrieves the `priceWei` without the LLM having to store it.

### `consumer/app.py` — the LLM reasoning loop

**Startup:**
1. Loads private key from env, creates `consumer_account` and `CONSUMER_ADDRESS`
2. Connects to Anvil via `Web3.HTTPProvider`

**`run_consumer(user_message, model)` — the main loop:**
```
1. Fetch MCP tools from provider (get_catalog, request_quote)
2. Combine with local tools (execute_agreement, check_agreement_status)
3. Build messages = [system_prompt, user_message]
4. Loop up to 12 turns:
   a. Call ollama.AsyncClient().chat(model, messages, tools)
   b. If no tool_calls → LLM is done, break
   c. For each tool_call:
      - MCP tool? → call_provider_tool() (goes to provider over HTTP/MCP)
      - Local tool? → execute locally (execute_agreement or check_agreement_status)
   d. Append tool result to messages
5. Return (final_text, inter_agent_log, thinking_chunks)
```

**Local tools:**

`execute_agreement(agreement_id)`:
- Looks up cached quote by `agreement_id`
- Calls `escrow.requestAgreement(aid, provider_address, mbps, duration)` with `priceWei` as `msg.value`
- This is the on-chain transaction that locks ETH and triggers the provider's event listener

`check_agreement_status(agreement_id)`:
- Calls `escrow.getAgreement(aid)` to read status
- If `ACTIVE`, signs a nonce and calls `GET /service` on the gateway
- Returns service details if active, or prompts the LLM to retry if still `REQUESTED`

**System prompt** (`SYSTEM_PROMPT_TEMPLATE`):
- Instructs the LLM to follow a specific 5-step workflow: catalog → quote → execute → check
- Provides a tier mapping table so "50 Mbps" maps to "small"
- **Critically**: tells the LLM to never guess or invent agreementId/tokenId values

**`_send_tx(func, value)`** — shared transaction helper (same pattern in both `consumer/app.py` and `provider/app.py`):
- Builds transaction from the contract function
- Signs with private key
- Sends via `eth_sendRawTransaction`
- Waits for receipt and checks `status == 1`

**REST endpoints:**
- `POST /chat` — main entry point from the UI
- `GET /.well-known/agent.json` — A2A agent card (A2A discovery pattern)
- `GET /log` — current inter-agent log
- `GET /catalog_proxy` — proxies provider catalog (for the UI to display)
- `GET /check_token?tokenId=N` — direct gateway check (used by sidebar in UI)

---

## 9. The UI (`consumer/ui.py`)

A Streamlit app that is **purely a thin HTTP client** — all LLM logic is in `consumer/app.py` (see D-10).

**Layout:** Two columns — left for human chat, right for the agent-to-agent transcript.

**State (in `st.session_state`):**
```
chat_history   list of {role, content, thinking} dicts
timeline       accumulated list of phase dicts across all turns
turn           incrementing counter per user message
```

**Phase system** (`_parse_log_to_phases`):
The UI parses the flat `inter_agent_log` list returned by `/chat` and groups messages into four phases:
```
catalog   → consumer called get_catalog, provider returned tiers
quote     → consumer called request_quote, provider returned agreementId + price
onchain   → requestAgreement() transaction sent; agreement ACTIVE
gateway   → gateway responded with service details
```

These phases accumulate across turns via `_merge_timeline` and are displayed as a step-by-step transcript with color-coded message bubbles by sender (consumer / provider / chain / gateway).

**Stepper bar** (`render_stepper`): shows the four phases as pills — pending (grey), active (blue), done (green).

---

## 10. Key data flows

### Full happy path

```
User: "Buy 100 Mbps"
  │
  ▼
consumer/ui.py  POST /chat  →  consumer/app.py
  │
  │  LLM turn 1: calls get_catalog (MCP)
  │    consumer/mcp_client.py  →  provider/mcp_server.py
  │    ←  JSON array of tiers + availableSlots
  │
  │  LLM turn 2: calls request_quote(package_id="medium", consumer_address=0x...)  (MCP)
  │    consumer/mcp_client.py  →  provider/mcp_server.py  →  provider/catalog.py
  │    ←  {agreementId: 99123, priceWei: 20000000000000000, ...}
  │    quote_cache["99123"] = {priceWei: ..., bandwidthMbps: 100, ...}
  │
  │  LLM turn 3: calls execute_agreement(agreement_id="99123")  (local)
  │    consumer/app.py  →  BandwidthEscrow.requestAgreement(99123, providerAddr, 100, 600)
  │    ETH locked on-chain; AgreementRequested event emitted
  │
  │  provider/app.py event listener (polling Anvil):
  │    AgreementRequested event received
  │    → BandwidthNFT.mint(providerAddr, 99123, 100, 600, "grpc://...")
  │    → BandwidthNFT.approve(escrowAddr, tokenId)
  │    → BandwidthEscrow.deposit(99123, tokenId)
  │       atomic swap: NFT → consumer, ETH → provider
  │       agreement status → ACTIVE
  │
  │  LLM turn 4: calls check_agreement_status(agreement_id="99123")  (local)
  │    consumer/app.py  →  BandwidthEscrow.getAgreement(99123)  status=ACTIVE
  │    Signs nonce, GET /service?tokenId=N  →  provider/gateway.py
  │    Gateway: ownerOf(N) == consumer? yes → return {bandwidth_mbps, seconds_remaining}
  │
  └─ LLM final turn: "Service ACTIVE. 100 Mbps, 600s remaining, endpoint=grpc://..."
```

### Quote caching bridge

The LLM cannot pass `priceWei` to `execute_agreement` directly (it's a large integer that LLMs may corrupt). Instead:
- `call_provider_tool("request_quote", ...)` caches the full quote in `quote_cache[agreementId_str]`
- `execute_agreement(agreement_id)` looks up `quote_cache[agreement_id]` to get `priceWei`
- The LLM only passes the string `agreementId` between tools

---

## 11. Configuration and environment

All configuration flows from `.env` (copy `.env.example`). Key variables:

```
RPC_URL                 http://localhost:8545 (or anvil container name in Docker)
CONSUMER_PRIVATE_KEY    Anvil account[2] private key
PROVIDER_PRIVATE_KEY    Anvil account[1] private key
DEPLOYER_PRIVATE_KEY    Anvil account[0] private key
PROVIDER_BASE_URL       http://localhost:8002
GATEWAY_BASE_URL        http://localhost:8003
OLLAMA_MODEL            qwen3:4b (or ministral:3b)
```

Contract addresses are written to `contracts/deployments/local.json` by `forge script Deploy.s.sol` and read at runtime by `shared/contracts.py`.

---

## 12. Common gotchas (from decisions.md)

| Issue | Root cause | Fix |
|-------|-----------|-----|
| Deploy silently writes nothing | `foundry.toml` missing `fs_permissions` | Added `read-write` for `./deployments` |
| Event listener crashes on `get_logs()` | web3.py v6 uses camelCase (`fromBlock`, not `from_block`) | Fixed in `provider/app.py` |
| MCP server not responding | FastMCP lifespan not wired into FastAPI | `async with _mcp_http_app.lifespan(app)` in lifespan context |
| REST routes shadowed by MCP | MCP app mounted at `/` before REST routes defined | Mount MCP **last** with `app.mount("/", _mcp_http_app)` |
| tokenId not available from transaction | Solidity return values unavailable from receipts | Extract `tokenId` from `Transfer(address,address,uint256)` event log |

---

## 13. Testing without the UI

```bash
# Full purchase flow via curl
make demo

# Check a specific token
curl http://localhost:8001/check_token?tokenId=0

# See inter-agent log
curl http://localhost:8001/log

# Raw catalog from provider
curl http://localhost:8002/catalog

# Provider's A2A agent card
curl http://localhost:8002/.well-known/agent.json
```
