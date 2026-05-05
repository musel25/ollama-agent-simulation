# End-to-End Walkthrough

> **Audience:** anyone who has read [`01-introduction.md`](01-introduction.md) and at least skimmed [`02-concepts.md`](02-concepts.md). You'll come out of this doc knowing what every component does and how a single typed sentence ends up enforcing a real bandwidth limit.
>
> **What we trace:** a successful run of `make demo` with `SDN_MOCK=true`. The mock-vs-real difference is called out at the end.

---

## The setup before the user types

**What the user sees**

The terminal shows `Services starting... UI at http://localhost:8501`. After 60–90 seconds, all health checks pass. Nothing more to see yet.

**What happens between components**

Eight services start in dependency order. `anvil` runs first; `deployer` fires once, publishes `BandwidthEscrow` and `BandwidthNFT`, writes their addresses to `contracts/deployments/`, then exits. The three Ollama containers start in parallel: `ollama` serves the inference API, `ollama-pull-3b` and `ollama-pull-1b` each run `ollama pull` and exit once the model layers are cached. `provider-agent` and `consumer-agent` start only after `deployer` has completed successfully; `consumer-ui` starts after the consumer agent.

```
docker-compose up

Anvil           Deployer        Ollama          Provider        Consumer        UI
   │                │               │               │               │            │
   │  starts        │               │               │               │            │
   │───────────────▶│               │               │               │            │
   │  healthy       │               │               │               │            │
   │◀───────────────│               │               │               │            │
   │                │  forge script │               │               │            │
   │◀───────────────┼───────────────│               │               │            │
   │  deploy()      │               │               │               │            │
   │──────────────▶ │               │               │               │            │
   │  contracts OK  │               │               │               │            │
   │─────────────── ┤  completed    │               │               │            │
   │                │───────────────┤               │               │            │
   │                │               │               │               │            │
   │                │               │ ollama pull   │               │            │
   │                │               │◀──────────────│               │            │
   │                │               │ model cached  │               │            │
   │                │               │───────────────▶               │            │
   │                │               │               │  uvicorn :8002│            │
   │                │               │               │───────────────▶            │
   │                │               │               │               │  :8001     │
   │                │               │               │               │────────────▶
   │                │               │               │               │            │ :8501
   │                │               │               │               │            │──▶
```

The provider's `lifespan()` handler (line 144 of `provider/app.py`) spawns two background tasks:
- `_event_listener()` — polls Anvil every 2 seconds for `AgreementRequested` events.
- `expiry_sweep_loop()` — runs every 30 seconds, revoking slots whose lease timer has expired.

The provider's `SlotPool` reads `provider/inventory.txt` on first access: three tiers (`small`, `medium`, `large`), each with a fixed number of subinterface slots.

**Where in the code**

- `docker-compose.yml` — service dependency graph
- `provider/app.py:144` — `lifespan()` that starts `_event_listener` and `expiry_sweep_loop`
- `provider/app.py:57` — `_event_listener()` definition
- `provider/expiry.py:21` — `expiry_sweep_loop()` definition
- `provider/catalog.py:20` — `CATALOG` tiers and `slot_pool` initialisation

**Why this stage exists**

The Ethereum node and the deployed contracts are the shared ground-truth both agents trust. Neither agent can lie about what is on-chain. Starting everything before any user interaction means the consumer and provider are operating on the same contract addresses from the first message.

---

## Stage 0 — User intent

**What the user sees**

A Streamlit chat interface at `http://localhost:8501`. The user types:

> `I need 5 Mbps for 10 minutes`

The UI shows a spinner: *Agents working…*

**What happens between components**

Streamlit collects the text, POSTs it to `consumer-agent:8001/chat`, then waits up to 300 seconds for the response. The consumer agent's `/chat` handler calls `run_consumer()`, which invokes the compiled LangGraph with an initial state containing the user's message, the provider URL, and the chosen Ollama model.

```
User          consumer-ui (:8501)    consumer-agent (:8001)
  │                  │                       │
  │  "5 Mbps..."     │                       │
  │─────────────────▶│                       │
  │                  │  POST /chat           │
  │                  │  {"message":"...",    │
  │                  │   "model":"llama3.2:3b"} │
  │                  │──────────────────────▶│
  │                  │                       │
  │                  │   [spinner]           │  run_consumer()
  │                  │                       │──────────┐
  │                  │                       │          │ build LangGraph
  │                  │                       │          │ initial state
  │                  │                       │◀─────────┘
  │                  │                       │
  │                  │   (workflow runs...   │
  │                  │    see stages 1–6)    │
  │                  │                       │
  │                  │   ChatResponse        │
  │                  │◀──────────────────────│
  │   agent reply    │                       │
  │◀─────────────────│                       │
```

**Where in the code**

- `consumer/ui.py:334` — Streamlit `httpx.Client.post` to `/chat`
- `consumer/app.py:95` — `@app.post("/chat")` FastAPI handler
- `consumer/app.py:47` — `run_consumer()` assembles initial state and calls `_compiled_graph.ainvoke()`
- `consumer/graph.py:289` — `build_graph()` wires the LangGraph nodes

**Why this stage exists**

The human's intent is unstructured natural language. Stage 0 is the boundary where that text enters the system. Everything from this point on is deterministic structured code — the LLM is only consulted once more (Stage 1, for tier selection) before the workflow becomes a pure state machine of on-chain calls.

---

## Stage 1 — Discovery (browse catalog)

**What the user sees**

Nothing visible yet; the UI spinner is still running.

**What happens between components**

The LangGraph enters `browse_node`. The node calls `_browse_catalog_tool()`, which is imported directly from `consumer/mcp_server.py` — there is no HTTP hop here, it is an in-process function call. That function calls `send_provider_action()` (from `consumer/a2a_client.py`), which constructs an A2A `Message` with `{"action": "get_catalog"}` and sends it over HTTP to `provider-agent:8002`.

The provider's A2A layer hands the message to `BandwidthProviderExecutor.execute()`, which routes to `_handle_catalog()`. That method calls the provider's own `get_catalog` MCP tool in-process via `MCPClient(mcp)`. The tool reads `provider/catalog.py:get_catalog_with_availability()` — current CATALOG joined with live slot counts from `SlotPool` — and returns a JSON array.

The A2A response travels back through `send_provider_action()`, which extracts the first artifact's data part and returns a plain Python dict. `browse_node` stores the catalog in state.

Then `pick_tier_node` asks the LLM one question: "The user said X. The tiers are small/medium/large. Reply with exactly one word." The model output is matched against the known `packageId` set. If the match fails (hallucination or punctuation), `_deterministic_tier_pick()` parses `"5 Mbps"` numerically and picks `medium` (the smallest tier with mbps >= 5).

```
consumer-agent        consumer MCP         consumer A2A client   provider-agent (:8002)   provider MCP
     │                     │                      │                      │                      │
     │  browse_node()      │                      │                      │                      │
     │────────────────────▶│                      │                      │                      │
     │                     │ browse_catalog()     │                      │                      │
     │                     │─────────────────────▶│                      │                      │
     │                     │                      │ A2A SendMessage      │                      │
     │                     │                      │ {action:get_catalog} │                      │
     │                     │                      │─────────────────────▶│                      │
     │                     │                      │                      │ executor._handle_    │
     │                     │                      │                      │ catalog()            │
     │                     │                      │                      │─────────────────────▶│
     │                     │                      │                      │                      │ get_catalog()
     │                     │                      │                      │                      │───┐
     │                     │                      │                      │                      │   │ SlotPool.tiers()
     │                     │                      │                      │                      │◀──┘
     │                     │                      │                      │  ArtifactUpdate      │
     │                     │                      │                      │  {catalog:[...]}     │
     │                     │                      │◀─────────────────────│                      │
     │                     │◀─────────────────────│                      │                      │
     │◀────────────────────│                      │                      │                      │
     │                     │                      │                      │                      │
     │  pick_tier_node()   │                      │                      │                      │
     │───┐                 │                      │                      │                      │
     │   │ LLM: "medium"   │                      │                      │                      │
     │◀──┘                 │                      │                      │                      │
```

**Where in the code**

- `consumer/graph.py:114` — `browse_node()`
- `consumer/graph.py:128` — `pick_tier_node()` and `_deterministic_tier_pick()`
- `consumer/mcp_server.py:141` — `browse_catalog()` MCP tool
- `consumer/a2a_client.py:34` — `send_provider_action()`
- `provider/agent_executor.py:109` — `_handle_catalog()`
- `provider/mcp_server.py:89` — `get_catalog()` MCP tool
- `provider/catalog.py:35` — `get_catalog_with_availability()`

**Why this stage exists**

The consumer does not hardcode tier names or prices. Discovering the catalog at runtime means the provider can change pricing, add tiers, or mark slots as full without any consumer-side changes. The LLM translation step maps human intent ("I need 5 Mbps") to a machine-readable `packageId` without requiring a rigid input format.

---

## Stage 2 — Quote and lock

**What the user sees**

Still the spinner. Nothing visible until Stage 6.

**What happens between components**

`quote_node` calls `request_quote(provider_url, "medium")`. This again goes through `send_provider_action()` as an A2A message with `{"action": "request_quote", "package_id": "medium", "consumer_address": "0x..."}`. The provider's executor routes to `_handle_quote()`, which calls the `request_quote` MCP tool. That tool calls `make_quote()` in `provider/catalog.py`: it checks slot availability, generates a random 128-bit `agreementId`, records the quote in `pending_quotes` with a 60-second TTL, and returns `{agreementId, priceWei, bandwidthMbps, durationSeconds}`.

Back in the consumer, `quote_node` stores `agreementId` in state and `request_quote()` in `consumer/mcp_server.py` caches the full quote (including the provider's Ethereum address, fetched via `GET /address`) in `quote_cache`.

`lock_node` then calls `lock_payment(agreement_id)` — a synchronous Web3 call offloaded to a thread via `asyncio.to_thread`. The function looks up the cached quote, builds and signs a `requestAgreement(agreementId, provider, mbps, durationSeconds)` call with `msg.value = priceWei`, sends it to Anvil, and waits for the receipt. Anvil mines the block (block time: 1 second) and emits `AgreementRequested(agreementId, consumer, provider, mbps, durationSecs, priceWei)`.

```
consumer-agent    consumer MCP     A2A client     provider-agent    provider MCP     Anvil
     │                 │               │                │                 │             │
     │  quote_node()   │               │                │                 │             │
     │────────────────▶│               │                │                 │             │
     │                 │ request_quote │                │                 │             │
     │                 │──────────────▶│                │                 │             │
     │                 │               │ A2A Message    │                 │             │
     │                 │               │ {action:quote} │                 │             │
     │                 │               │───────────────▶│                 │             │
     │                 │               │                │ _handle_quote() │             │
     │                 │               │                │────────────────▶│             │
     │                 │               │                │                 │ make_quote()│
     │                 │               │                │                 │─────────────▶
     │                 │               │                │                 │  pending_   │
     │                 │               │                │                 │  quotes[id] │
     │                 │               │                │                 │◀────────────│
     │                 │               │◀───────────────│                 │             │
     │                 │◀──────────────│                │                 │             │
     │◀────────────────│               │                │                 │             │
     │  lock_node()    │               │                │                 │             │
     │────────────────▶│               │                │                 │             │
     │                 │ lock_payment()│                │                 │             │
     │                 │───────────────────────────────────────────────────────────────▶│
     │                 │               │     requestAgreement(id, ..., value=priceWei)  │
     │                 │               │                │                 │             │──┐
     │                 │               │                │                 │             │  │ mine block
     │                 │               │                │                 │             │◀─┘
     │                 │               │                │                 │             │
     │                 │               │          emit AgreementRequested               │
     │◀────────────────────────────────────────────────────────────────── │             │
     │  "OK 0xabc..."  │               │                │                 │             │
```

**Where in the code**

- `consumer/graph.py:161` — `quote_node()`
- `consumer/graph.py:175` — `lock_node()`
- `consumer/mcp_server.py:157` — `request_quote()` MCP tool (caches quote)
- `consumer/mcp_server.py:84` — `lock_payment()` MCP tool (signs `requestAgreement`)
- `provider/agent_executor.py:115` — `_handle_quote()`
- `provider/mcp_server.py:95` — `request_quote()` MCP tool
- `provider/catalog.py:50` — `make_quote()`
- `contracts/src/BandwidthEscrow.sol:73` — `requestAgreement()` function
- `contracts/src/BandwidthEscrow.sol:55` — `AgreementRequested` event definition

**Why this stage exists**

The quote pins `agreementId`, price, and tier before any ETH moves. The consumer signs exactly what was quoted — if the provider later tries to change the price, the Solidity checks will revert. The 60-second TTL on pending quotes prevents the provider from holding slots for abandoned requests.

---

## Stage 3 — Credential issuance (NFT mint)

**What the user sees**

Still the spinner.

**What happens between components**

The provider's `_event_listener()` has been polling Anvil every 2 seconds. It picks up the `AgreementRequested` event and spawns `_handle_agreement()` as a non-blocking asyncio task. That function looks up the quote in `pending_quotes`, verifies the on-chain parameters match (mbps, duration, price), and calls `slot_pool.reserve()` to claim a specific subinterface slot for this agreement.

It then opens an in-process MCP client (`MCPClient(mcp)`) and calls `mint_credential`. That MCP tool calls `BandwidthNFT.mint(providerAddress, agreementId, mbps, durationSeconds, endpoint)` via Web3 — the endpoint string encodes `clab://<pe>/<subinterface>`. The contract mints the token to the provider's own address and records the `TokenMetadata` on-chain. The receipt's Transfer log is parsed to extract the new `tokenId`.

At this point the NFT is owned by the provider.

```
Anvil               provider-app          provider MCP         BandwidthNFT
  │                      │                     │                     │
  │  AgreementRequested  │                     │                     │
  │─────────────────────▶│                     │                     │
  │                      │ _handle_agreement() │                     │
  │                      │──────────┐          │                     │
  │                      │          │ verify   │                     │
  │                      │          │ pending_ │                     │
  │                      │          │ quotes   │                     │
  │                      │          │ reserve  │                     │
  │                      │          │ slot     │                     │
  │                      │◀─────────┘          │                     │
  │                      │ MCPClient.call_tool │                     │
  │                      │ ("mint_credential") │                     │
  │                      │────────────────────▶│                     │
  │                      │                     │ BandwidthNFT.mint() │
  │                      │                     │────────────────────▶│
  │                      │                     │                     │──┐
  │                      │                     │                     │  │ _safeMint(provider)
  │                      │                     │                     │  │ _metadata[tokenId] = ...
  │                      │                     │                     │◀─┘
  │                      │                     │  Transfer event     │
  │◀────────────────────────────────────────────────────────────────│
  │                      │                     │◀────────────────────│
  │                      │  {tokenId: 0, ...}  │                     │
  │                      │◀────────────────────│                     │
```

**Where in the code**

- `provider/app.py:57` — `_event_listener()` polling loop
- `provider/app.py:87` — `_handle_agreement()` (validates quote, reserves slot, calls MCP tools)
- `provider/app.py:104` — `slot_pool.reserve()` call
- `provider/app.py:111` — `MCPClient(mcp)` and `call_tool("mint_credential", ...)`
- `provider/mcp_server.py:157` — `mint_credential()` MCP tool
- `contracts/src/BandwidthNFT.sol:33` — `mint()` function
- `contracts/src/BandwidthNFT.sol:41` — `_safeMint(to, tokenId)`

**Why this stage exists**

The credential is minted before any money moves. This gives the provider a concrete, verifiable token they can hand to the consumer. The NFT encodes the exact slot (pe + subinterface) so the consumer's credential is bound to a specific network resource, not just an abstract entitlement.

---

## Stage 4 — Atomic swap (escrow ↔ NFT)

**What the user sees**

Still the spinner. On-chain state: agreement moves from REQUESTED to ACTIVE in a single transaction.

**What happens between components**

Immediately after `mint_credential` returns, `_handle_agreement()` calls `complete_swap(agreementId, tokenId)` via the same in-process MCP client. That MCP tool issues two transactions in sequence:

1. `BandwidthNFT.approve(escrowAddress, tokenId)` — grants the escrow contract permission to transfer the NFT.
2. `BandwidthEscrow.deposit(agreementId, tokenId)` — the atomic swap. Inside `deposit()`:
   - The contract reads the NFT metadata and verifies it matches the agreement's `bandwidthMbps` and `durationSeconds`. If they differ, it reverts with `MetadataMismatch`.
   - Status is flipped to `ACTIVE` (effects before interactions, following the checks-effects-interactions pattern).
   - `nftContract.safeTransferFrom(provider, escrow, tokenId)` — NFT enters the escrow.
   - `nftContract.safeTransferFrom(escrow, consumer, tokenId)` — NFT leaves escrow, lands in consumer's wallet.
   - `provider.call{value: priceWei}("")` — ETH released to the provider.
   - Emits `AgreementActive(agreementId, tokenId, consumer, provider)`.

If any step reverts, the entire `deposit()` transaction rolls back and the agreement stays REQUESTED. The consumer's ETH remains locked. No partial state is possible.

```
provider-app       provider MCP         Anvil (BandwidthEscrow)   Anvil (BandwidthNFT)
     │                  │                         │                        │
     │ complete_swap()  │                         │                        │
     │─────────────────▶│                         │                        │
     │                  │ NFT.approve(escrow,tid) │                        │
     │                  │─────────────────────────────────────────────────▶│
     │                  │                         │                        │──┐ set approval
     │                  │                         │                        │◀─┘
     │                  │ escrow.deposit(aid,tid) │                        │
     │                  │────────────────────────▶│                        │
     │                  │                         │──┐                     │
     │                  │                         │  │ verify NFT metadata │
     │                  │                         │  │ ag.status=ACTIVE    │
     │                  │                         │  │ NFT→escrow          │
     │                  │                         │  │ NFT→consumer        │
     │                  │                         │  │ ETH→provider        │
     │                  │                         │◀─┘                     │
     │                  │                         │                        │
     │                  │                         │ emit AgreementActive   │
     │◀─────────────────────────────────────────── │                       │
     │  {approveTx, depositTx}                     │                       │
```

**Where in the code**

- `provider/app.py:127` — `call_tool("complete_swap", ...)` call
- `provider/mcp_server.py:193` — `complete_swap()` MCP tool (approve + deposit)
- `contracts/src/BandwidthEscrow.sol:98` — `deposit()` function
- `contracts/src/BandwidthEscrow.sol:114` — checks-effects section inside `deposit()`
- `contracts/src/BandwidthEscrow.sol:119` — NFT transfer chain inside `deposit()`
- `contracts/src/BandwidthNFT.sol:52` — `getTokenMetadata()` called by escrow during deposit

**Why this stage exists**

Atomicity is the security guarantee. Without it, the provider could take the ETH without delivering the NFT, or the consumer could claim the NFT without paying. The Solidity contract makes that impossible: either everything succeeds or nothing does.

---

## Stage 5 — Activation (present credential, apply rule)

**What the user sees**

Still the spinner. This is the last step before the agent replies.

**What happens between components**

Back in the consumer's LangGraph, `settle_node` polls `escrow.getAgreement(agreementId)` (via `await_settlement`) until the status field returns `ACTIVE`. It polls up to 20 times with 1.5-second gaps (30 seconds maximum). Each call is a read-only `eth_call` to Anvil — no transaction. Once ACTIVE is detected, the node reads `tokenId` from the agreement struct and stores it in state.

`present_node` then calls `_present_credential_tool(provider_url, token_id)`. This MCP tool generates a fresh nonce (current Unix timestamp as a string), signs it with the consumer's ECDSA key, and sends an A2A `activate` message to the provider: `{"action": "activate", "token_id": N, "nonce": "...", "signature": "0x..."}`.

The provider's executor routes to `_handle_activate()`. It calls `verify_credential_ownership(token_id, signature, nonce)`, which:
1. Checks the nonce is within ±300 seconds of now (replay protection).
2. Recovers the signer from `encode_defunct(text=nonce)` + signature.
3. Calls `BandwidthNFT.ownerOf(tokenId)` on-chain and asserts it equals the recovered signer.
4. Fetches `TokenMetadata` to get `agreementId`, `mbps`, and `seconds_remaining`.
5. Reads the escrow agreement status — must be ACTIVE.

If verification passes, the executor looks up the slot in `SlotPool` by `agreementId` and calls `allocate_bandwidth(customer_id, pe, subinterface, mbps)`. With `SDN_MOCK=true` this returns `{"success": true, ..., "gnmi_pushed": false, "tc_applied": false, "message": "mocked"}` immediately. The A2A response carries `{"status": "active", "bandwidth_mbps": 5, "seconds_remaining": N, ...}`.

`present_node` checks `activation["status"] == "active"`, stores the dict in state, then `summary_node` assembles the final deterministic sentence.

```
consumer LangGraph   consumer MCP     A2A client    provider-agent   provider MCP   Anvil
      │                   │               │               │               │            │
      │  settle_node()    │               │               │               │            │
      │──▶ poll x N       │               │               │               │            │
      │    getAgreement() │               │               │               │            │
      │───────────────────────────────────────────────────────────────────────────────▶│
      │    status=ACTIVE  │               │               │               │            │
      │◀───────────────────────────────────────────────────────────────────────────── │
      │                   │               │               │               │            │
      │  present_node()   │               │               │               │            │
      │──────────────────▶│               │               │               │            │
      │                   │ present_      │               │               │            │
      │                   │ credential()  │               │               │            │
      │                   │──────────────▶│               │               │            │
      │                   │               │ A2A activate  │               │            │
      │                   │               │ {token_id,    │               │            │
      │                   │               │  nonce, sig}  │               │            │
      │                   │               │──────────────▶│               │            │
      │                   │               │               │ _handle_      │            │
      │                   │               │               │ activate()    │            │
      │                   │               │               │──────────────▶│            │
      │                   │               │               │               │ verify_    │
      │                   │               │               │               │ credential_│
      │                   │               │               │               │ ownership()│
      │                   │               │               │               │────────────▶
      │                   │               │               │               │ ownerOf()  │
      │                   │               │               │               │ ok=true    │
      │                   │               │               │               │◀───────────│
      │                   │               │               │               │            │
      │                   │               │               │ slot = SlotPool.lookup()   │
      │                   │               │               │               │            │
      │                   │               │               │               │ allocate_  │
      │                   │               │               │               │ bandwidth()│
      │                   │               │               │               │──┐ (mocked)│
      │                   │               │               │               │◀─┘         │
      │                   │               │◀──────────────│               │            │
      │                   │◀──────────────│               │               │            │
      │◀──────────────────│               │               │               │            │
      │  {status:active}  │               │               │               │            │
```

**Where in the code**

- `consumer/graph.py:195` — `settle_node()` polling loop
- `consumer/graph.py:227` — `present_node()`
- `consumer/graph.py:251` — `summary_node()` (deterministic sentence)
- `consumer/mcp_server.py:116` — `await_settlement()` MCP tool
- `consumer/mcp_server.py:184` — `present_credential()` MCP tool (sign nonce + A2A activate)
- `provider/agent_executor.py:132` — `_handle_activate()`
- `provider/mcp_server.py:104` — `verify_credential_ownership()`
- `provider/mcp_server.py:214` — `allocate_bandwidth()` (mock branch at line 221)

**Why this stage exists**

The consumer proves ownership of the NFT without revealing their private key — they sign a fresh nonce, the provider verifies the signature against `ownerOf` on-chain. The freshness window (±300 s) prevents replay attacks. Only after this proof does the provider apply the network rule, ensuring that the entity controlling the credential is the same entity that paid for it.

---

## Stage 6 — Consumption and expiry

**What the user sees**

The spinner disappears. The UI displays:

> `Active service — medium tier (5 Mbps), agreementId=<N>, tokenId=<N>.`

The agent-transcript panel shows all four phases (Catalog, Quote, On-chain TX, Gateway) as green "DONE" badges.

**What happens between components**

From the consumer's perspective the workflow is complete. The `summary_node` returned its deterministic sentence; `consumer/app.py:chat()` sends the `ChatResponse`; `consumer/ui.py` re-renders.

In the background, the provider's `expiry_sweep_loop()` runs every 30 seconds. On each sweep, `_sweep_once()` opens `inventory.txt` under an `fcntl` exclusive lock, finds all slots whose `expiresAt` timestamp has passed, and for each expired slot:
1. Calls `revoke_bandwidth(customer_id, pe, subinterface)` via the in-process MCP client (no-op in mock mode).
2. Calls `slot_pool.release(agreementId)` to free the slot for the next buyer.

The NFT itself is not burned. It remains in the consumer's wallet permanently as on-chain proof of the purchase. The escrow agreement stays in ACTIVE status. Only the provider's internal slot is reclaimed.

```
consumer-ui     consumer-agent    (background: provider-agent)        Anvil
     │               │                       │                           │
     │  response     │                       │                           │
     │◀──────────────│                       │                           │
     │               │                       │                           │
     │  [user sees   │                       │  ... duration_min elapses │
     │   "Active"]   │                       │                           │
     │               │                       │                           │
     │               │                       │ expiry_sweep_loop tick    │
     │               │                       │──────────┐                │
     │               │                       │          │ open inventory │
     │               │                       │          │ find expired   │
     │               │                       │          │ slots          │
     │               │                       │◀─────────┘                │
     │               │                       │                           │
     │               │                       │ revoke_bandwidth(pe, sif) │
     │               │                       │──────────┐ (mocked)      │
     │               │                       │◀─────────┘                │
     │               │                       │                           │
     │               │                       │ slot_pool.release(aid)    │
     │               │                       │──────────┐                │
     │               │                       │◀─────────┘                │
     │               │                       │                           │
     │               │                       │  slot now free for reuse  │
     │               │                       │                           │
     │               │  (NFT remains in consumer wallet — on-chain proof)│
     │               │                       │                           │
```

**Where in the code**

- `consumer/graph.py:251` — `summary_node()` builds the final user-visible sentence
- `consumer/app.py:95` — `/chat` handler returns the `ChatResponse` to the UI
- `provider/expiry.py:21` — `expiry_sweep_loop()` outer loop
- `provider/expiry.py:32` — `_sweep_once()` reads inventory, identifies expired slots
- `provider/expiry.py:63` — `revoke_bandwidth` MCP call
- `provider/expiry.py:70` — `slot_pool.release(aid)`
- `contracts/src/BandwidthNFT.sol` — NFT contract (no burn; token persists)

**Why this stage exists**

The expiry sweep decouples the network resource lifecycle from the blockchain state. Freeing the slot allows the provider to sell the same subinterface again without a new contract deployment. Keeping the NFT in the consumer's wallet provides an auditable history of every purchase without requiring extra on-chain writes.

---

## What changes with `SDN_MOCK=false`

When you run `make demo-real` (or restart `provider-agent` with `SDN_MOCK=false`):

1. **Stage 5 — `allocate_bandwidth`** no longer returns the canned mock response. It instantiates a `ServiceRequest` and calls the real `srl_bandwidth.bandwidth.allocate_bandwidth()` function, which:
   - Pushes a gNMI policer to the SR Linux PE router.
   - `docker exec`s into the CE container (`clab-bandwidth-poc-ce3`) to run `tc tbf rate 5mbit burst 15k latency 50ms` on the relevant interface.

2. **Prerequisite:** `make clab-up` must have run first. This clones the `srl-gnmi-bandwidth-poc` repo, calls `scripts/deploy.sh` to spin up the ContainerLab topology (SR Linux PE + four CE containers), waits 60 seconds for SR Linux to boot, then calls `scripts/push-config.sh`.

3. **Verification:** after the demo, `make demo-real` runs:
   ```
   docker exec clab-bandwidth-poc-ce4 iperf3 -s -1 -p 5201
   docker exec clab-bandwidth-poc-ce3 iperf3 -c 192.168.4.10 -p 5201 -t 5 -u -b 15M -J
   ```
   The measured throughput should be capped at ~5 Mbps even though the client sends 15 Mbps.

4. **`revoke_bandwidth`** in Stage 6 also becomes real: it calls `_srl_revoke()` which removes the policer via gNMI.

The Solidity contracts, LangGraph nodes, A2A protocol, and MCP tool interfaces are identical in both modes. The only difference is what `allocate_bandwidth` and `revoke_bandwidth` do when called.

---

## Where to read the code for each stage

| Stage | Key action | File | Line |
|-------|-----------|------|------|
| Setup | Lifespan: start event listener + expiry loop | `provider/app.py` | 144 |
| Setup | `_event_listener()` definition | `provider/app.py` | 57 |
| Setup | `expiry_sweep_loop()` definition | `provider/expiry.py` | 21 |
| Setup | Catalog tiers and `SlotPool` init | `provider/catalog.py` | 20 |
| 0 | Streamlit POST to `/chat` | `consumer/ui.py` | 334 |
| 0 | `/chat` FastAPI handler | `consumer/app.py` | 95 |
| 0 | `run_consumer()` + `build_graph()` invocation | `consumer/app.py` | 47 |
| 1 | `browse_node()` | `consumer/graph.py` | 114 |
| 1 | `pick_tier_node()` + `_deterministic_tier_pick()` | `consumer/graph.py` | 128 |
| 1 | `browse_catalog()` MCP tool | `consumer/mcp_server.py` | 141 |
| 1 | `send_provider_action()` A2A client | `consumer/a2a_client.py` | 34 |
| 1 | `_handle_catalog()` in executor | `provider/agent_executor.py` | 109 |
| 1 | `get_catalog()` MCP tool | `provider/mcp_server.py` | 89 |
| 2 | `quote_node()` | `consumer/graph.py` | 161 |
| 2 | `lock_node()` | `consumer/graph.py` | 175 |
| 2 | `request_quote()` consumer MCP tool | `consumer/mcp_server.py` | 157 |
| 2 | `lock_payment()` MCP tool (signs `requestAgreement`) | `consumer/mcp_server.py` | 84 |
| 2 | `_handle_quote()` in executor | `provider/agent_executor.py` | 115 |
| 2 | `make_quote()` | `provider/catalog.py` | 50 |
| 2 | `requestAgreement()` Solidity function | `contracts/src/BandwidthEscrow.sol` | 73 |
| 2 | `AgreementRequested` event | `contracts/src/BandwidthEscrow.sol` | 55 |
| 3 | `_handle_agreement()` (mint flow) | `provider/app.py` | 87 |
| 3 | `mint_credential()` MCP tool | `provider/mcp_server.py` | 157 |
| 3 | `mint()` Solidity function | `contracts/src/BandwidthNFT.sol` | 33 |
| 4 | `call_tool("complete_swap")` | `provider/app.py` | 127 |
| 4 | `complete_swap()` MCP tool | `provider/mcp_server.py` | 193 |
| 4 | `deposit()` Solidity function (atomic swap) | `contracts/src/BandwidthEscrow.sol` | 98 |
| 5 | `settle_node()` polling loop | `consumer/graph.py` | 195 |
| 5 | `present_node()` | `consumer/graph.py` | 227 |
| 5 | `summary_node()` deterministic sentence | `consumer/graph.py` | 251 |
| 5 | `await_settlement()` MCP tool | `consumer/mcp_server.py` | 116 |
| 5 | `present_credential()` MCP tool | `consumer/mcp_server.py` | 184 |
| 5 | `_handle_activate()` in executor | `provider/agent_executor.py` | 132 |
| 5 | `verify_credential_ownership()` MCP tool | `provider/mcp_server.py` | 104 |
| 5 | `allocate_bandwidth()` MCP tool (mock branch) | `provider/mcp_server.py` | 221 |
| 6 | `_sweep_once()` reads inventory, identifies expired | `provider/expiry.py` | 32 |
| 6 | `revoke_bandwidth` call in expiry sweep | `provider/expiry.py` | 63 |
| 6 | `slot_pool.release()` in expiry sweep | `provider/expiry.py` | 70 |
