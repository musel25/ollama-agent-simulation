# Architecture & Implementation Decisions

This document records every non-obvious decision made during the smart-contract settlement layer implementation, with the reasoning behind each choice. It is updated incrementally as tasks are completed.

---

## Solidity / Smart Contracts

### D-01 — `_ownerOf` instead of `ownerOf` for existence check in BandwidthNFT
**Decision:** `getTokenMetadata` uses `_ownerOf(tokenId) == address(0)` (internal OZ v5 function) rather than `ownerOf(tokenId) == address(0)`.  
**Why:** In OpenZeppelin v5, the public `ownerOf` reverts with `ERC721NonexistentToken` for non-existent tokens before the `== address(0)` comparison can execute. The custom `TokenDoesNotExist` error would therefore be dead code. `_ownerOf` is the internal variant that returns `address(0)` without reverting, making the custom error reachable and meaningful.

### D-02 — Atomic swap inside `deposit()`, no separate `executeSwap()`
**Decision:** The NFT→consumer and ETH→provider transfers happen in a single `deposit()` call. There is no externally callable `executeSwap()`.  
**Why:** Atomicity is the core safety property of the double-escrow. Splitting into two transactions would open a window where one party could be transferred to and the other not — breaking the trustless guarantee. A single function call on the EVM is atomic by definition.

### D-03 — PENDING state collapsed into ACTIVE
**Decision:** The paper describes a PENDING state between the provider locking the NFT and the swap executing. The contract skips it — `deposit()` goes directly REQUESTED → ACTIVE.  
**Why:** PENDING would only be observable if the swap were a separate transaction. Since the swap is atomic inside `deposit()`, PENDING is never externally visible. Adding it would be a state the contract can never reach. Documented in the contract-level comment.

### D-04 — `nftContract` named in camelCase, not SCREAMING_SNAKE_CASE
**Decision:** The immutable is named `nftContract`, not `NFT_CONTRACT`.  
**Why:** Foundry lints flag immutables as SCREAMING_SNAKE_CASE by convention, but the Python services reference the contract by ABI function names (not Solidity variable names). The camelCase name is more readable in the contract source and has zero runtime impact.

### D-05 — Deploy script reads keys from env, not hardcoded
**Decision:** `Deploy.s.sol` reads `DEPLOYER_PRIVATE_KEY` and `PROVIDER_ADDRESS` via `vm.envUint` / `vm.envAddress`.  
**Why:** Hardcoding Anvil's deterministic private keys in the contract source is fine for a PoC, but reading from env keeps the deploy script reusable across environments (local Anvil, future testnet) without editing Solidity. The `.env.example` documents the expected values.

### D-06 — `vm.writeFile` writes to `deployments/local.json` (relative to contracts/)
**Decision:** The path passed to `vm.writeFile` is `"deployments/local.json"`, relative to the Foundry project root (`contracts/`).  
**Why:** Foundry resolves `vm.writeFile` paths relative to the project root, not the repo root. Writing `"deployments/local.json"` therefore produces `contracts/deployments/local.json`, which is where `shared/contracts.py` looks for addresses.

---

## Inventory Model

### D-07 — Per-tier slot counts with time-based expiration (not a single shared pool)
**Decision:** `provider/inventory.txt` uses a JSON-lines format with one object per tier, each containing `totalSlots` and an `activeLeases` list of `{agreementId, expiresAt}` pairs.  
**Why:** The user explicitly chose per-tier slot counts over a single shared integer pool. Time expiration means slots reclaim automatically when a service agreement's duration lapses — no manual cleanup needed, and the `/catalog` endpoint always reflects live availability. `fcntl.flock` (exclusive) guards concurrent reads/writes.

### D-08 — Lease expiry computed from NFT `startTime + durationSeconds`
**Decision:** When a lease is recorded in `inventory.txt`, `expiresAt = now + durationSeconds` (provider clock).  
**Why:** The NFT `startTime` is set to `block.timestamp` at mint time inside the contract. The provider's clock and the chain clock may differ slightly, but for a local PoC on Anvil this is negligible. On a production system, `startTime` from the NFT metadata would be used instead.

---

## Python / Service Architecture

### D-09 — Three independent FastAPI services (not one monolith)
**Decision:** Consumer agent (port 8001), Provider agent (port 8002), and Gateway (port 8003) are separate `uvicorn` processes.  
**Why:** The original code was a single-process Streamlit app that spawned the provider as a subprocess. The new design reflects real-world microservice separation: the consumer and provider are adversarial parties who would never share a process. Independent processes also make Docker Compose natural.

### D-10 — Streamlit is a thin HTTP client, LLM loop stays in consumer/app.py
**Decision:** `consumer/ui.py` (Streamlit) only calls `consumer/app.py` over HTTP (`POST /chat`). The LLM tool-calling loop is in the FastAPI service, not in Streamlit.  
**Why:** Streamlit reruns the entire script on every interaction, which makes stateful LLM loops fragile. Moving the loop to the FastAPI service gives it stable process state and makes it independently testable via `curl`.

### D-11 — Provider address retrieved via `/address` endpoint, not hardcoded in consumer
**Decision:** `consumer/app.py` calls `GET provider/address` to discover the provider's EOA rather than reading it from `.env`.  
**Why:** Both services read from `.env`, but the consumer shouldn't need to know the provider's private key or address at startup — it should discover it at runtime. This keeps the consumer/provider boundary clean and makes the provider's identity configurable without touching the consumer's config.

### D-12 — ABI JSON files copied from Foundry build artifacts, not committed statically
**Decision:** `shared/abi/*.json` are generated by running a Python snippet that copies from `contracts/out/`.  
**Why:** Committing static ABI files risks drift if the contracts change. Generating from `contracts/out/` guarantees the Python services always use the ABI that matches the compiled bytecode on the local chain. The generation step is part of the local setup and the Docker deployer container.

### D-13 — `fcntl.flock` (not threading.Lock) for inventory file
**Decision:** Inventory reads/writes use `fcntl.flock(f, fcntl.LOCK_EX)` for exclusive locking.  
**Why:** `flock` works across processes, not just threads. Since the provider app and gateway run as separate uvicorn processes (or could), a thread-level lock would be invisible across process boundaries. `flock` is the correct POSIX primitive for per-file mutual exclusion.

### D-14 — Event listener uses HTTP polling (`get_logs`), not WebSocket filter
**Decision:** The provider's `AgreementRequested` listener polls via `escrow.events.AgreementRequested.get_logs(from_block=..., to_block=...)` on a 2-second asyncio loop.  
**Why:** WebSocket subscriptions (`eth_subscribe`) require a persistent WS connection and are not supported by all providers. HTTP polling with `get_logs` works with any JSON-RPC endpoint including Anvil's HTTP interface. For a local PoC with 1-second block times, 2-second polling has acceptable latency.

### D-15 — tokenId extracted from Transfer event log, not from `mint()` return value
**Decision:** After calling `mint()`, the provider reads the `Transfer(address,address,uint256)` event from the transaction receipt to discover the newly minted `tokenId`.  
**Why:** Solidity return values from `eth_sendRawTransaction` are not accessible in transaction receipts — only events are. The ERC-721 standard mandates a `Transfer` event on every mint, so this is reliable and doesn't require a custom event.

### D-16 — Gateway auth: signed Unix timestamp as nonce
**Decision:** Clients sign `str(int(time.time()))` (a Unix timestamp string) and send it as `X-Nonce`. The gateway rejects nonces older than 300 seconds.  
**Why:** A timestamp nonce is self-expiring without requiring the gateway to maintain a nonce database. 300 seconds is generous enough for clock skew while preventing replay attacks. The alternative (random nonce + server-side store) would add state to a stateless gateway.

### D-17 — `check_agreement_status` requires the LLM to remember `agreementId`
**Decision:** The consumer tool `check_agreement_status(agreement_id: int)` requires the caller (LLM) to pass the agreementId it received from `request_agreement_on_chain`.  
**Why:** The LLM must not guess or fabricate chain state. If it forgets the agreementId, the tool raises a clear error rather than silently checking a wrong agreement. This enforces the "no LLM in the on-chain path" constraint — structured Python executes every chain call, the LLM only provides the argument it was given.

---

## Infrastructure

### D-18 — Anvil deterministic accounts assigned by role
**Decision:** account[0] = deployer/owner, account[1] = provider EOA, account[2] = consumer EOA.  
**Why:** Anvil always generates the same accounts from its default mnemonic. Assigning by index makes the `.env.example` reproducible and means any reviewer running `make up` gets identical addresses without generating keys.

### D-19 — Provider runs two uvicorn processes in one container (app + gateway)
**Decision:** `Dockerfile.provider` starts both `provider/app.py` (port 8002) and `provider/gateway.py` (port 8003) in the same container via a shell `&` background + `wait`.  
**Why:** The provider and gateway share the same EOA and chain state. Running them in one container avoids synchronization complexity around the shared `inventory.txt` and simplifies Docker Compose networking. For production, they'd be separate services.

### D-20 — `deployer` is a one-shot container, not part of the main service lifecycle
**Decision:** The Docker Compose `deployer` service runs `forge script` once and exits. The other services `depends_on: deployer`.  
**Why:** Contract deployment is a one-time setup step, not a long-running service. Making it a one-shot container with `restart: "no"` models this correctly and prevents accidental re-deployment on container restart.

---

---

## Bugs Found During Local E2E Test (Task 10)

### D-21 — `foundry.toml` requires explicit `fs_permissions` for `vm.writeFile`
**Decision:** Added `fs_permissions = [{ access = "read-write", path = "./deployments" }]` to `contracts/foundry.toml`.  
**Why:** Foundry's cheatcode sandbox blocks file writes by default. Without this permission, `vm.writeFile("deployments/local.json", ...)` in `Deploy.s.sol` silently fails — the deploy runs without error but `local.json` stays empty. The Python services then crash with "invalid address" when loading the zero-string. This must be set for the deploy script to function.

### D-22 — `web3.py` `get_logs()` uses camelCase keyword arguments
**Decision:** Changed `from_block=` / `to_block=` to `fromBlock=` / `toBlock=` in `provider/app.py`'s event listener.  
**Why:** web3.py v6's `ContractEvent.get_logs()` accepts camelCase filter arguments matching the JSON-RPC spec (`fromBlock`, `toBlock`), not Python-style snake_case. Using `from_block=` raises `TypeError: get_logs() got an unexpected keyword argument 'from_block'`, crashing the event listener on every 2-second poll. This would mean the provider never responds to `AgreementRequested` events, breaking the entire settlement flow.

---

## What Was Preserved from the Original Code

- Ollama integration and `qwen3:4b` as default model (unchanged)
- Three bandwidth tiers: Small (50 Mbps), Medium (100 Mbps), Large (500 Mbps), each 600s
- The `<think>` block rendering in Streamlit (`render_content`)
- The dual-column Streamlit layout (consumer chat left, provider log right)
- The `inter_agent_log` pattern for surfacing agent-to-agent calls in the UI

## What Was Removed

- `catalog.txt` (replaced by `provider/inventory.txt` with per-tier slot + expiration model)
- `agreements.json` (agreements now live on-chain in BandwidthEscrow)
- UUID tokens (replaced by ERC-721 tokenIds)
- Single-process architecture (app.py spawning provider_server as subprocess)
- Natural-language messages between agents (replaced by structured HTTP + on-chain calls)
