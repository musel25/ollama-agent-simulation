# Implementation Design Rationale for the Paper

Project topic: "Autonomous Agent-to-Agent Tokenized Network Service Provisioning via Smart Contracts"

This report analyzes the repository as implementation evidence for an academic feasibility study. It is intentionally conservative: claims about implemented behavior are grounded in files, functions, configuration, deployment artifacts, or commands observed during repository inspection. Where the implementation suggests a broader paper interpretation, that interpretation is separated from what the code actually enforces.

## Executive Summary

The repository implements a proof-of-concept in which a consumer agent acquires a simulated bandwidth service from a provider agent. The system uses HTTP APIs for agent-to-agent coordination, a local Ethereum chain for settlement, a smart-contract escrow for ETH/payment custody, an ERC-721 NFT as an access credential, and a provider-controlled gateway that checks on-chain token ownership before returning service metadata.

The strongest implemented contribution is not real network provisioning. The strongest implemented contribution is the coupling of payment settlement and access-credential delivery through a smart-contract-mediated atomic exchange. The `BandwidthEscrow.deposit()` function moves the NFT to the consumer and releases ETH to the provider inside one transaction, after checking that NFT metadata matches the requested agreement (`contracts/src/BandwidthEscrow.sol:98`, `contracts/src/BandwidthEscrow.sol:106`, `contracts/src/BandwidthEscrow.sol:115`, `contracts/src/BandwidthEscrow.sol:119`).

The implementation should be presented as a feasibility study of autonomous acquisition and credential-gated access, not as production-grade bandwidth provisioning. The README explicitly states "No real money, no real internet traffic" (`README.md:5`) and lists "Enforce bandwidth at the network layer" and "Use an oracle to verify the bandwidth was actually delivered" under behavior the prototype does not provide (`README.md:210`, `README.md:211`).

## Repository Map

| Area | Main files | Purpose | Notes |
|---|---|---|---|
| Smart contracts | `contracts/src/BandwidthNFT.sol`, `contracts/src/BandwidthEscrow.sol` | ERC-721 access credential and ETH/NFT escrow state machine | Solidity 0.8.20, OpenZeppelin imports (`contracts/foundry.toml:1`, `contracts/foundry.toml:5`, `contracts/foundry.toml:6`) |
| Deployment | `contracts/script/Deploy.s.sol`, `contracts/deployments/local.json`, `contracts/broadcast/Deploy.s.sol/31337/run-latest.json` | Deploys NFT and escrow contracts to local Anvil and records addresses | Deploy script reads `DEPLOYER_PRIVATE_KEY` and `PROVIDER_ADDRESS` from environment (`contracts/script/Deploy.s.sol:10`, `contracts/script/Deploy.s.sol:11`) |
| Shared contract bindings | `shared/contracts.py`, `shared/abi/BandwidthNFT.json`, `shared/abi/BandwidthEscrow.json` | Loads deployed contract addresses and ABI files for Python services | `shared/contracts.py` reads `contracts/deployments/local.json` and creates Web3 contract objects (`shared/contracts.py:7`, `shared/contracts.py:15`, `shared/contracts.py:21`) |
| Provider agent | `provider/app.py`, `provider/inventory.txt` | Serves catalog and quote endpoints, watches escrow events, mints NFTs, approves escrow, calls `deposit()` | FastAPI service on port 8002 (`provider/app.py:1`, `provider/app.py:262`) |
| Gateway | `provider/gateway.py` | Verifies signed nonce and on-chain NFT ownership before returning service metadata | FastAPI service on port 8003 (`provider/gateway.py:1`, `provider/gateway.py:24`) |
| Consumer agent | `consumer/app.py` | Runs the Ollama tool-calling loop, requests quotes, submits on-chain agreement requests, checks gateway | FastAPI service on port 8001 (`consumer/app.py:1`, `consumer/app.py:298`) |
| Frontend | `consumer/ui.py` | Streamlit thin client for chat, provider transcript, catalog, and manual token check | Delegates logic to consumer FastAPI service (`consumer/ui.py:1`, `consumer/ui.py:82`) |
| Docker/local infrastructure | `docker-compose.yml`, `Dockerfile.consumer`, `Dockerfile.provider`, `Makefile`, `.env.example` | Runs Anvil, deployer, Ollama, provider, consumer, and UI | Compose defines Anvil, one-shot deployer, Ollama model pulls, provider, consumer, and UI (`docker-compose.yml:1`) |
| Documentation | `README.md`, `docs/how-it-works.md`, `docs/decisions.md`, `docs/superpowers/...` | User-facing explanation, design notes, implementation plans/specs | `docs/decisions.md` records design choices and bug fixes |
| Legacy prototype files | `app.py`, `consumer_agent.py`, `provider_server.py`, `catalog.txt`, `agreements.json` | Older UUID/file-backed prototype still present | `docs/decisions.md` says these were superseded by new services and on-chain agreements (`docs/decisions.md:125`) |
| Tests/CI | `contracts/.github/workflows/test.yml`, empty `contracts/test/` | CI invokes Foundry formatting, build, and tests | During this review, `forge test -vvv` reported no tests found |

## Implemented Architecture

### Component Table

| Component | Role | Implementation location | Main responsibility | Trust boundary |
|---|---|---|---|---|
| Consumer agent | Autonomous buyer | `consumer/app.py` | Interpret user request through Ollama, call structured tools, obtain quote, submit escrow request, check status and gateway | Consumer-controlled service with consumer private key in `CONSUMER_PRIVATE_KEY` |
| Provider agent | Autonomous seller | `provider/app.py` | Publish catalog, issue quote, listen for `AgreementRequested`, mint NFT, approve escrow, complete deposit | Provider-controlled service with provider private key in `PROVIDER_PRIVATE_KEY` |
| Bandwidth NFT | Access credential | `contracts/src/BandwidthNFT.sol` | Mint ERC-721 token containing agreement metadata | On-chain contract; minting restricted to provider owner |
| Bandwidth escrow | Settlement layer | `contracts/src/BandwidthEscrow.sol` | Hold consumer ETH, store agreement state, atomically swap NFT and ETH, allow cancellation/refund while requested | On-chain neutral logic after deployment |
| Gateway | Access-control bridge | `provider/gateway.py` | Recover caller address from signature, check `ownerOf(tokenId)`, return metadata | Provider-operated off-chain service |
| Inventory file | Simulated capacity model | `provider/inventory.txt`, `provider/app.py` | Track per-tier slots and lease expiration timestamps | Provider-controlled local state |
| Streamlit UI | Human interface | `consumer/ui.py` | Send chat messages to consumer service, show transcript, show catalog, verify token | User-facing client, not part of settlement guarantee |
| Local chain | Blockchain testbed | `docker-compose.yml`, Foundry/Anvil | Execute contracts with deterministic local accounts | Local development environment only |
| Deployer | Setup process | `contracts/script/Deploy.s.sol`, Docker `deployer` service | Deploy NFT and escrow and write local addresses | One-shot local deployment step |

### Consumer Agent

Implemented behavior:

- The consumer service owns an Ethereum externally owned account derived from `CONSUMER_PRIVATE_KEY` (`consumer/app.py:21`, `consumer/app.py:23`, `consumer/app.py:26`).
- It uses Ollama for tool-calling (`consumer/app.py:10`, `consumer/app.py:240`, `consumer/app.py:252`).
- It exposes structured Python tools to the LLM: `query_provider_catalog`, `request_agreement_on_chain`, and `check_agreement_status` (`consumer/app.py:94`, `consumer/app.py:112`, `consumer/app.py:162`, `consumer/app.py:233`).
- The LLM does not directly craft transactions. The Python tool `_send_tx()` signs and broadcasts transactions with the consumer private key (`consumer/app.py:70`).
- The consumer discovers the provider address through `GET /address` rather than hardcoding it (`consumer/app.py:85`).
- After an agreement is active, the consumer signs a timestamp nonce and calls the gateway with `X-Nonce` and `X-Signature` (`consumer/app.py:191`, `consumer/app.py:198`, `consumer/app.py:201`).

Inputs:

- User natural-language chat message through `POST /chat` (`consumer/app.py:312`).
- Environment variables: `RPC_URL`, `CONSUMER_PRIVATE_KEY`, `PROVIDER_BASE_URL`, `GATEWAY_BASE_URL`, and `OLLAMA_MODEL` (`consumer/app.py:22`, `consumer/app.py:23`, `consumer/app.py:29`, `consumer/app.py:30`, `consumer/app.py:31`).

Outputs and state changes:

- HTTP calls to provider `/catalog` and `/quote` (`consumer/app.py:98`, `consumer/app.py:127`).
- On-chain `requestAgreement()` transaction to `BandwidthEscrow` with ETH value (`consumer/app.py:148`, `consumer/app.py:149`, `consumer/app.py:150`).
- Gateway request to `/service` if agreement becomes `ACTIVE` (`consumer/app.py:196`).
- Agent-to-agent transcript entries stored in `inter_agent_log` (`consumer/app.py:33`, `consumer/app.py:37`).

Design interpretation:

The consumer agent is "autonomous" in the limited sense that, after the human submits an intent, the LLM-controlled tool loop can choose and execute the procurement workflow. The actual chain and HTTP operations are deterministic Python functions, not free-form LLM text. This is a useful paper point: autonomy is used for decision sequencing, while settlement-critical operations remain structured.

### Provider Agent

Implemented behavior:

- The provider service owns the provider EOA from `PROVIDER_PRIVATE_KEY` (`provider/app.py:27`, `provider/app.py:29`, `provider/app.py:32`).
- It defines three hardcoded service packages: `small`, `medium`, and `large`, with 50/100/500 Mbps, 600 seconds, and fixed ETH prices (`provider/app.py:35`, `provider/app.py:36`).
- It exposes `/catalog`, `/quote`, `/inventory`, and `/address` (`provider/app.py:270`, `provider/app.py:275`, `provider/app.py:301`, `provider/app.py:306`).
- Quotes use random 128-bit `agreementId` values and a 60-second TTL in an in-memory `pending_quotes` dictionary (`provider/app.py:129`, `provider/app.py:131`, `provider/app.py:286`, `provider/app.py:287`).
- On startup, the FastAPI lifespan starts an asynchronous event listener (`provider/app.py:256`, `provider/app.py:258`).
- The listener polls `AgreementRequested` events from the escrow contract every two seconds using `get_logs(fromBlock=..., toBlock=...)` (`provider/app.py:166`, `provider/app.py:172`, `provider/app.py:178`).
- For a recognized quote, it verifies the on-chain agreement's bandwidth, duration, and price against the quote (`provider/app.py:204`, `provider/app.py:205`, `provider/app.py:207`).
- It reserves one inventory slot, mints an NFT to the provider address, extracts the token ID from the ERC-721 `Transfer` event, approves the escrow contract, and calls `deposit()` (`provider/app.py:211`, `provider/app.py:220`, `provider/app.py:229`, `provider/app.py:234`, `provider/app.py:238`).

Inputs:

- HTTP quote requests containing `packageId` and `consumerAddress` (`provider/app.py:265`, `provider/app.py:275`).
- On-chain `AgreementRequested` events emitted by `BandwidthEscrow` (`contracts/src/BandwidthEscrow.sol:55`, `provider/app.py:178`).
- Inventory file `provider/inventory.txt` (`provider/app.py:43`, `provider/app.py:44`).

Outputs and state changes:

- Pending quote records in memory (`provider/app.py:287`).
- Inventory lease entries with `agreementId` and `expiresAt` (`provider/app.py:102`, `provider/app.py:104`).
- NFT mint transaction (`provider/app.py:220`).
- ERC-721 approval transaction (`provider/app.py:234`).
- Escrow `deposit()` transaction (`provider/app.py:238`).

Important limitation:

The provider verifies bandwidth, duration, and price, but the current `_handle_agreement()` code does not compare the on-chain consumer address against `quote["consumerAddress"]` (`provider/app.py:204`, `provider/app.py:207`, `provider/app.py:287`). This is probably acceptable for a local PoC with random agreement IDs, but it is an important security gap for a production design.

### BandwidthNFT Contract

Implemented behavior:

- `BandwidthNFT` inherits OpenZeppelin `ERC721` and `Ownable` (`contracts/src/BandwidthNFT.sol:4`, `contracts/src/BandwidthNFT.sol:5`, `contracts/src/BandwidthNFT.sol:13`).
- The token metadata is stored on-chain in a `TokenMetadata` struct with `agreementId`, `bandwidthMbps`, `durationSeconds`, `startTime`, and `endpoint` (`contracts/src/BandwidthNFT.sol:14`).
- Only the contract owner may mint because `mint()` uses `onlyOwner` (`contracts/src/BandwidthNFT.sol:33`, `contracts/src/BandwidthNFT.sol:39`).
- Minting assigns sequential token IDs using `_nextTokenId++`, safely mints to `to`, and stores metadata with `startTime = block.timestamp` (`contracts/src/BandwidthNFT.sol:22`, `contracts/src/BandwidthNFT.sol:40`, `contracts/src/BandwidthNFT.sol:41`, `contracts/src/BandwidthNFT.sol:42`, `contracts/src/BandwidthNFT.sol:46`).
- `getTokenMetadata()` returns metadata and uses `_ownerOf(tokenId) == address(0)` to detect non-existent tokens (`contracts/src/BandwidthNFT.sol:51`, `contracts/src/BandwidthNFT.sol:53`).

Design interpretation:

The NFT should be framed as a machine-verifiable access credential. It records what service was promised, but it does not itself enforce delivery of bandwidth. Ownership is used by the gateway as the access-control condition.

### BandwidthEscrow Contract

Implemented behavior:

- The contract stores agreements with consumer, provider, bandwidth, duration, price, deadline, token ID, and status (`contracts/src/BandwidthEscrow.sol:29`).
- Status values are `NONE`, `REQUESTED`, `ACTIVE`, `CLOSED`, and `CANCELLED` (`contracts/src/BandwidthEscrow.sol:21`).
- `requestAgreement()` creates a new agreement, requires nonzero ETH, sets a one-hour request deadline, stores `msg.value` as `priceWei`, and emits `AgreementRequested` (`contracts/src/BandwidthEscrow.sol:73`, `contracts/src/BandwidthEscrow.sol:77`, `contracts/src/BandwidthEscrow.sol:78`, `contracts/src/BandwidthEscrow.sol:80`, `contracts/src/BandwidthEscrow.sol:86`, `contracts/src/BandwidthEscrow.sol:91`).
- `deposit()` is provider-only, requires status `REQUESTED`, checks NFT metadata against agreement fields, sets status to `ACTIVE`, stores `tokenId`, transfers the NFT provider -> escrow -> consumer, transfers ETH to provider, and emits `AgreementActive` (`contracts/src/BandwidthEscrow.sol:98`, `contracts/src/BandwidthEscrow.sol:103`, `contracts/src/BandwidthEscrow.sol:104`, `contracts/src/BandwidthEscrow.sol:106`, `contracts/src/BandwidthEscrow.sol:115`, `contracts/src/BandwidthEscrow.sol:119`, `contracts/src/BandwidthEscrow.sol:121`, `contracts/src/BandwidthEscrow.sol:124`).
- `cancel()` can cancel only a `REQUESTED` agreement; the consumer can cancel at any time while requested, and anyone can cancel after `requestDeadline`; cancellation sets status to `CANCELLED` and refunds the consumer (`contracts/src/BandwidthEscrow.sol:132`, `contracts/src/BandwidthEscrow.sol:136`, `contracts/src/BandwidthEscrow.sol:138`, `contracts/src/BandwidthEscrow.sol:139`, `contracts/src/BandwidthEscrow.sol:145`, `contracts/src/BandwidthEscrow.sol:147`).
- `getAgreement()` returns the full agreement struct (`contracts/src/BandwidthEscrow.sol:153`).

Design interpretation:

The escrow contract is the neutral settlement layer. Its main guarantee is asset exchange: if the provider receives ETH through `deposit()`, the NFT is transferred to the consumer in the same EVM transaction. The contract does not observe or enforce bandwidth quality.

### Gateway

Implemented behavior:

- The gateway endpoint is `GET /service?tokenId=N` (`provider/gateway.py:24`, `provider/gateway.py:26`).
- Clients send `X-Nonce` and `X-Signature` headers (`provider/gateway.py:27`, `provider/gateway.py:28`).
- The nonce must parse as a Unix timestamp and be within a 300-second window (`provider/gateway.py:21`, `provider/gateway.py:39`, `provider/gateway.py:44`).
- The gateway recovers the signer address from the signature (`provider/gateway.py:47`, `provider/gateway.py:49`, `provider/gateway.py:50`).
- It checks `ownerOf(tokenId)` on the NFT contract and rejects if the recovered signer is not the current token owner (`provider/gateway.py:54`, `provider/gateway.py:57`, `provider/gateway.py:61`, `provider/gateway.py:62`).
- It reads token metadata and agreement status from the NFT and escrow contracts, computes seconds remaining, and returns service metadata (`provider/gateway.py:65`, `provider/gateway.py:71`, `provider/gateway.py:76`, `provider/gateway.py:79`).

Important limitation:

The gateway returns `status` and `seconds_remaining`, but it does not reject non-`ACTIVE` status or expired credentials. Access control is ownership-based, not status-and-time-enforced (`provider/gateway.py:73`, `provider/gateway.py:76`, `provider/gateway.py:79`). The consumer tool only calls the gateway after it sees `ACTIVE` (`consumer/app.py:185`), but direct gateway callers that own a token are not blocked by gateway code solely because the agreement is expired.

### Frontend

Implemented behavior:

- `consumer/ui.py` is a Streamlit thin client (`consumer/ui.py:1`).
- It sends chat messages to `POST /chat` on the consumer agent (`consumer/ui.py:82`, `consumer/ui.py:83`, `consumer/ui.py:84`).
- It displays agent logs and provider output (`consumer/ui.py:26`, `consumer/ui.py:105`).
- It can manually verify a token by calling the consumer service `/check_token`, which signs the nonce server-side using the consumer private key (`consumer/ui.py:48`, `consumer/ui.py:53`, `consumer/app.py:350`).

The frontend is evidence of human observability and demonstration usability, not part of the protocol guarantee.

### Infrastructure

Implemented behavior:

- Docker Compose runs an Anvil local chain on port 8545 (`docker-compose.yml:2`, `docker-compose.yml:4`, `docker-compose.yml:5`).
- A one-shot `deployer` container runs the Foundry deploy script after Anvil is healthy (`docker-compose.yml:13`, `docker-compose.yml:15`, `docker-compose.yml:24`).
- The provider container runs both provider and gateway Uvicorn processes (`Dockerfile.provider:35`, `Dockerfile.provider:36`, `Dockerfile.provider:37`).
- The consumer container runs `consumer.app:app` (`Dockerfile.consumer:34`).
- The UI container runs Streamlit on port 8501 (`docker-compose.yml:111`, `docker-compose.yml:123`).
- `.env.example` uses Anvil deterministic account 0 for deployer, account 1 for provider, and account 2 for consumer (`.env.example:1`, `.env.example:2`, `.env.example:6`, `.env.example:10`).

## End-to-End Workflow

### Step 1: Catalog discovery

Implemented behavior:

- The consumer tool `query_provider_catalog()` sends `GET /catalog` to the provider (`consumer/app.py:94`, `consumer/app.py:98`).
- The provider returns the hardcoded package catalog with live available slot counts (`provider/app.py:270`, `provider/app.py:75`).
- Inventory availability is computed from `provider/inventory.txt` after pruning expired leases (`provider/app.py:47`, `provider/app.py:56`, `provider/app.py:75`, `provider/app.py:80`).

Paper interpretation:

This step models service discovery. It is off-chain because browsing availability does not need settlement finality and would be expensive to place on-chain.

### Step 2: Quote creation

Implemented behavior:

- The consumer calls `POST /quote` with `packageId` and `consumerAddress` (`consumer/app.py:126`, `consumer/app.py:127`, `consumer/app.py:129`).
- The provider checks that the package exists and has an available slot (`provider/app.py:277`, `provider/app.py:281`, `provider/app.py:283`).
- The provider creates a random 128-bit `agreementId` and stores a pending quote with 60-second TTL (`provider/app.py:286`, `provider/app.py:287`, `provider/app.py:290`).
- The quote response contains `agreementId`, `priceWei`, `bandwidthMbps`, and `durationSeconds` (`provider/app.py:293`).

Paper interpretation:

The quote is an off-chain pre-agreement. It binds the provider's local event listener to a later on-chain request using a random agreement identifier.

### Step 3: Consumer locks ETH in escrow

Implemented behavior:

- The consumer calls `BandwidthEscrow.requestAgreement(agreementId, providerAddress, mbps, dur)` and sends `priceWei` as `msg.value` (`consumer/app.py:146`, `consumer/app.py:148`, `consumer/app.py:149`, `consumer/app.py:150`).
- The escrow contract rejects duplicate agreement IDs and zero-price agreements (`contracts/src/BandwidthEscrow.sol:77`, `contracts/src/BandwidthEscrow.sol:78`).
- It stores the consumer, provider, bandwidth, duration, price, one-hour deadline, token ID 0, and status `REQUESTED` (`contracts/src/BandwidthEscrow.sol:80`).
- It emits `AgreementRequested` (`contracts/src/BandwidthEscrow.sol:91`).

Paper interpretation:

The contract acts like a neutral locker. The consumer puts ETH into the locker, but the provider cannot withdraw it until the provider supplies the matching NFT credential.

### Step 4: Provider observes the request

Implemented behavior:

- The provider event listener polls escrow logs (`provider/app.py:166`, `provider/app.py:178`).
- For each `AgreementRequested` event, it calls `_handle_agreement()` asynchronously (`provider/app.py:182`, `provider/app.py:184`).
- `_handle_agreement()` requires a valid pending quote and checks the on-chain agreement against the quoted package's bandwidth, duration, and price (`provider/app.py:192`, `provider/app.py:195`, `provider/app.py:204`, `provider/app.py:207`).

Paper interpretation:

The provider agent is reactive rather than manually operated. It observes on-chain events and autonomously executes the provider side of settlement when the event matches a quote it issued.

### Step 5: Provider reserves simulated capacity

Implemented behavior:

- The provider calls `decrement_inventory()` before minting the NFT (`provider/app.py:211`, `provider/app.py:212`).
- The inventory file stores one JSON object per tier with `totalSlots` and `activeLeases` (`provider/inventory.txt:1`, `provider/inventory.txt:2`, `provider/inventory.txt:3`).
- Reservation appends `{"agreementId": ..., "expiresAt": time.time() + duration_seconds}` (`provider/app.py:102`, `provider/app.py:103`, `provider/app.py:104`).
- If minting fails before a token ID exists, the inventory reservation is rewound (`provider/app.py:243`, `provider/app.py:245`, `provider/app.py:247`).

Paper interpretation:

This is a simulated capacity model. It is useful to demonstrate that off-chain resource accounting can be coupled to on-chain settlement, but it does not prove actual network capacity enforcement.

### Step 6: Provider mints NFT credential

Implemented behavior:

- The provider calls `BandwidthNFT.mint(PROVIDER_ADDRESS, agreement_id, mbps, duration, "grpc://provider:8003")` (`provider/app.py:220`, `provider/app.py:221`, `provider/app.py:222`, `provider/app.py:226`).
- The NFT contract stores metadata on-chain (`contracts/src/BandwidthNFT.sol:42`).
- The provider extracts the new token ID from the ERC-721 `Transfer` event in the transaction receipt (`provider/app.py:157`, `provider/app.py:160`, `provider/app.py:161`, `provider/app.py:229`).

Paper interpretation:

The NFT is the access credential. It is not a decorative collectible in this prototype; it is a machine-readable entitlement whose ownership can be checked by the gateway.

### Step 7: Provider approves escrow and deposits NFT

Implemented behavior:

- The provider approves the escrow contract to move the token (`provider/app.py:232`, `provider/app.py:234`).
- The provider calls `escrow.deposit(agreement_id, token_id)` (`provider/app.py:237`, `provider/app.py:238`).
- The escrow contract checks caller is the agreement provider and status is `REQUESTED` (`contracts/src/BandwidthEscrow.sol:103`, `contracts/src/BandwidthEscrow.sol:104`).
- It verifies the NFT metadata matches `agreementId`, `bandwidthMbps`, and `durationSeconds` (`contracts/src/BandwidthEscrow.sol:106`, `contracts/src/BandwidthEscrow.sol:108`, `contracts/src/BandwidthEscrow.sol:109`).
- It marks the agreement `ACTIVE`, stores token ID, transfers NFT to consumer, and releases ETH to provider (`contracts/src/BandwidthEscrow.sol:115`, `contracts/src/BandwidthEscrow.sol:116`, `contracts/src/BandwidthEscrow.sol:119`, `contracts/src/BandwidthEscrow.sol:120`, `contracts/src/BandwidthEscrow.sol:121`).

Paper interpretation:

This is the central atomic settlement step. If any part of the transfer fails, the transaction reverts under EVM transaction semantics. The repository's design note explicitly states that splitting this into separate transactions would break the trustless guarantee (`docs/decisions.md:13`, `docs/decisions.md:15`).

### Step 8: Consumer checks agreement status

Implemented behavior:

- The consumer calls `getAgreement(agreement_id)` and maps the numeric status to a name (`consumer/app.py:176`, `consumer/app.py:178`, `consumer/app.py:182`, `consumer/app.py:216`).
- If status is not `ACTIVE`, it tells the user to try again later (`consumer/app.py:185`, `consumer/app.py:186`).
- If active, it extracts `tokenId` from the agreement (`consumer/app.py:188`).

Paper interpretation:

The consumer independently reads on-chain state before asking for service access. This reduces reliance on provider text responses.

### Step 9: Gateway verifies credential and returns service metadata

Implemented behavior:

- The consumer signs a timestamp nonce with its private key (`consumer/app.py:191`, `consumer/app.py:192`, `consumer/app.py:193`).
- The gateway recovers the signer and compares it to `ownerOf(tokenId)` (`provider/gateway.py:49`, `provider/gateway.py:50`, `provider/gateway.py:57`, `provider/gateway.py:61`).
- If they match, the gateway returns token metadata, agreement status, seconds remaining, endpoint, and signer (`provider/gateway.py:79`).

Paper interpretation:

The gateway bridges on-chain settlement to off-chain service access. It is the component that turns token ownership into service authorization.

### Step 10: Cancellation/refund path

Implemented behavior:

- `cancel()` is available only while status is `REQUESTED` (`contracts/src/BandwidthEscrow.sol:132`, `contracts/src/BandwidthEscrow.sol:136`).
- The consumer can cancel immediately while requested; anyone can cancel after the one-hour deadline (`contracts/src/BandwidthEscrow.sol:138`, `contracts/src/BandwidthEscrow.sol:139`, `contracts/src/BandwidthEscrow.sol:140`).
- Cancellation sets status `CANCELLED` and refunds `priceWei` to the consumer (`contracts/src/BandwidthEscrow.sol:143`, `contracts/src/BandwidthEscrow.sol:144`, `contracts/src/BandwidthEscrow.sol:145`, `contracts/src/BandwidthEscrow.sol:147`).

Limitations:

- No Python consumer tool calls `cancel()`.
- No automated test exercises the refund behavior.
- `CLOSED` exists in the enum but there is no implemented close function (`contracts/src/BandwidthEscrow.sol:25`).

## Beginner-Friendly Analogy

The system is like a vending machine for temporary network access.

The consumer agent is the buyer. The provider agent is the seller. The buyer asks what packages are available, such as 50 Mbps or 100 Mbps for 10 minutes. The seller replies with a price and a unique deal number.

Instead of trusting the seller directly, the buyer puts payment into a smart contract. Think of the smart contract as a transparent locker that everyone can inspect. The provider cannot take the money just by promising service. The provider must put a matching access ticket into the locker.

That access ticket is an NFT. In this project, the NFT is not used as digital art. It is used as a unique access credential. It contains the agreement ID, bandwidth amount, duration, start time, and endpoint. Whoever owns the token can prove ownership with an Ethereum signature.

When the provider deposits the correct NFT, the smart contract performs the exchange in one step: the NFT goes to the consumer and the ETH goes to the provider. This is the vending-machine moment: either both assets move, or nothing moves.

The gateway is the door to the service. Before returning service details, it checks that the caller signed a fresh nonce and owns the NFT on-chain. This prevents someone from getting access just by guessing the public token ID.

The prototype proves that the acquisition mechanism can be automated across agents, HTTP services, and smart contracts. It does not prove that real bandwidth is physically delivered, that quality of service is enforced, or that a provider cannot lie about its capacity.

## Design Decisions and Rationale

### Decision 1: Use a Smart Contract as the Settlement Layer

**What was chosen:**  
The implementation uses `BandwidthEscrow` as the on-chain settlement contract. It stores agreements, holds ETH, emits events, performs the NFT/payment swap, and handles cancellation/refund while requested.

**Where it appears in the implementation:**  
`contracts/src/BandwidthEscrow.sol:8`, `contracts/src/BandwidthEscrow.sol:29`, `contracts/src/BandwidthEscrow.sol:73`, `contracts/src/BandwidthEscrow.sol:98`, `contracts/src/BandwidthEscrow.sol:132`.

**Why this decision matters:**  
Without a neutral settlement layer, either the consumer would have to pay first and trust the provider, or the provider would have to issue access first and trust the consumer. The contract removes this direct payment trust for the exchange of ETH and NFT.

**Alternatives:**  
A centralized payment server, direct peer-to-peer payment after service delivery, signed invoices, a custodial marketplace, or provider-controlled account credits.

**Why the chosen option is justified:**  
The paper studies autonomous agent-to-agent provisioning. A smart contract gives both agents a shared, programmable, auditable state machine without requiring either agent to operate the settlement service.

**Tradeoff or limitation:**  
The contract guarantees settlement, not physical service delivery. The provider still controls whether real network capacity exists and whether the gateway maps credentials to actual service.

### Decision 2: Use Double Escrow and Atomic Swap

**What was chosen:**  
The consumer locks ETH through `requestAgreement()`. The provider mints an NFT, approves escrow, and calls `deposit()`. The escrow contract transfers the NFT to the consumer and ETH to the provider in one transaction.

**Where it appears in the implementation:**  
`contracts/src/BandwidthEscrow.sol:73`, `contracts/src/BandwidthEscrow.sol:98`, `contracts/src/BandwidthEscrow.sol:119`, `contracts/src/BandwidthEscrow.sol:120`, `contracts/src/BandwidthEscrow.sol:121`; provider flow in `provider/app.py:220`, `provider/app.py:234`, `provider/app.py:238`.

**Why this decision matters:**  
The atomic exchange is the main safety property. There is no successful state where the provider receives ETH but the consumer does not receive the credential.

**Alternatives:**  
Separate payment then credential issuance, credential issuance then payment, a two-phase protocol with manual finalization, or an off-chain atomic swap protocol.

**Why the chosen option is justified:**  
EVM transactions are atomic. Encoding both transfers in `deposit()` keeps the settlement guarantee simple and easy to explain.

**Tradeoff or limitation:**  
If minting succeeds but approval or deposit fails, the provider code logs the NFT as orphaned and requires manual cleanup (`provider/app.py:249`, `provider/app.py:250`, `provider/app.py:251`). The contract cannot automatically recover from all off-chain orchestration failures.

### Decision 3: Collapse PENDING into ACTIVE

**What was chosen:**  
The contract has no externally visible `PENDING` state. `deposit()` moves directly from `REQUESTED` to `ACTIVE`.

**Where it appears in the implementation:**  
Contract comment in `contracts/src/BandwidthEscrow.sol:17`, status update in `contracts/src/BandwidthEscrow.sol:115`; design rationale in `docs/decisions.md:17`.

**Why this decision matters:**  
A pending state would only matter if NFT deposit and swap execution were separated. Because deposit executes the swap immediately, there is no observable intermediate state.

**Alternatives:**  
Implement `REQUESTED -> PENDING -> ACTIVE`, with a separate `executeSwap()` function.

**Why the chosen option is justified:**  
The implementation prioritizes atomicity and avoids unreachable or misleading state.

**Tradeoff or limitation:**  
The state machine is less expressive for future features such as provider deposit waiting for consumer confirmation, third-party verification, or oracle approval.

### Decision 4: Represent Access as an ERC-721 NFT

**What was chosen:**  
`BandwidthNFT` is an ERC-721 token. Each token represents one bandwidth entitlement and stores metadata on-chain.

**Where it appears in the implementation:**  
`contracts/src/BandwidthNFT.sol:4`, `contracts/src/BandwidthNFT.sol:13`, `contracts/src/BandwidthNFT.sol:14`, `contracts/src/BandwidthNFT.sol:33`.

**Why this decision matters:**  
The gateway can verify ownership using a standard `ownerOf(tokenId)` call. The credential is unique, transferable by default, and machine-verifiable.

**Alternatives:**  
ERC-1155, ERC-20 account credits, non-transferable soulbound tokens, signed provider-issued bearer tokens, W3C verifiable credentials, or centralized API keys.

**Why the chosen option is justified:**  
ERC-721 is widely supported and maps naturally to unique leases. The prototype needs one token per agreement rather than a fungible pool of credits.

**Tradeoff or limitation:**  
OpenZeppelin ERC-721 tokens are transferable unless restricted. The gateway authorizes the current token owner, not necessarily the original consumer. This may be useful for transferable rights, but it is a limitation if the intended service credential should be non-transferable.

### Decision 5: Store Service Metadata On-Chain

**What was chosen:**  
The NFT stores `agreementId`, `bandwidthMbps`, `durationSeconds`, `startTime`, and `endpoint` directly on-chain in a struct.

**Where it appears in the implementation:**  
`contracts/src/BandwidthNFT.sol:14`, `contracts/src/BandwidthNFT.sol:42`, `contracts/src/BandwidthNFT.sol:51`; README description in `README.md:205`.

**Why this decision matters:**  
The escrow can check metadata against the agreement, and the gateway can read service parameters without IPFS or a provider database.

**Alternatives:**  
Use `tokenURI` with IPFS/HTTP metadata, store only a hash on-chain, or keep metadata entirely off-chain.

**Why the chosen option is justified:**  
For a local feasibility study, direct on-chain metadata reduces moving parts and makes auditability straightforward.

**Tradeoff or limitation:**  
On-chain metadata is public and more expensive on real networks. It is not suitable for private endpoint secrets or large service descriptions.

### Decision 6: Separate Payment Settlement from Service Delivery

**What was chosen:**  
The smart contract handles payment and credential exchange. The gateway and provider services handle service metadata and simulated access.

**Where it appears in the implementation:**  
Settlement in `contracts/src/BandwidthEscrow.sol`; gateway in `provider/gateway.py`; README limitations in `README.md:210`, `README.md:211`.

**Why this decision matters:**  
Blockchains cannot directly enforce network bandwidth. The design keeps on-chain logic limited to what the chain can verify: payments, token ownership, metadata consistency, and state transitions.

**Alternatives:**  
Attempt to put service enforcement on-chain, use an oracle to attest service delivery, or avoid blockchain and use a centralized gateway ledger.

**Why the chosen option is justified:**  
It matches the feasibility goal: demonstrate autonomous acquisition and credential-gated access, not full QoS enforcement.

**Tradeoff or limitation:**  
The paper must state that the provider still controls actual service delivery. The prototype is Tier 1 provider-asserted access, not oracle-monitored delivery.

### Decision 7: Use an Off-Chain Gateway for Access Control

**What was chosen:**  
`provider/gateway.py` verifies a signed nonce and checks NFT ownership before returning service metadata.

**Where it appears in the implementation:**  
`provider/gateway.py:24`, `provider/gateway.py:49`, `provider/gateway.py:57`, `provider/gateway.py:61`.

**Why this decision matters:**  
The gateway connects blockchain state to an ordinary service endpoint. It lets an off-chain service ask the chain who owns the credential.

**Alternatives:**  
Put service data entirely on-chain, use centralized API keys, use OAuth, use mTLS client certificates, or use a DID/verifiable credential system.

**Why the chosen option is justified:**  
Network services are off-chain by nature. A gateway is a realistic bridge between tokenized rights and service access.

**Tradeoff or limitation:**  
The gateway is provider-operated and trusted to enforce access correctly. It currently checks ownership but does not deny expired tokens or non-active agreement status.

### Decision 8: Use Signed Timestamp Nonces

**What was chosen:**  
The client signs `str(int(time.time()))`, sends it as `X-Nonce`, and the gateway rejects nonces outside a 300-second window.

**Where it appears in the implementation:**  
Consumer signing in `consumer/app.py:191`, `consumer/app.py:193`; gateway validation in `provider/gateway.py:21`, `provider/gateway.py:39`, `provider/gateway.py:44`, `provider/gateway.py:49`.

**Why this decision matters:**  
The gateway must know that the caller controls the private key for the token owner address. A signed nonce proves key control without revealing the private key.

**Alternatives:**  
Random server-issued nonces, session tokens, SIWE-style authentication, mTLS, OAuth, or API keys.

**Why the chosen option is justified:**  
Timestamp nonces are simple and stateless. They fit a local prototype and avoid a server-side nonce database.

**Tradeoff or limitation:**  
The same timestamp signature can be replayed within the 300-second window because the gateway does not store used nonces. This is a bounded replay risk for the prototype, but production systems should use server-issued nonces or replay caches.

### Decision 9: Use Provider-Side Event Polling Instead of WebSockets

**What was chosen:**  
The provider polls `AgreementRequested` logs every two seconds over HTTP JSON-RPC.

**Where it appears in the implementation:**  
`provider/app.py:166`, `provider/app.py:172`, `provider/app.py:178`; rationale in `docs/decisions.md:69`.

**Why this decision matters:**  
The provider must react autonomously after the consumer locks ETH. Event polling is the trigger that connects the on-chain request to provider-side minting.

**Alternatives:**  
WebSocket subscriptions, direct callback from consumer, off-chain message queue, indexer service, or manual provider action.

**Why the chosen option is justified:**  
HTTP polling works with Anvil and avoids persistent subscription infrastructure.

**Tradeoff or limitation:**  
Polling introduces latency and may miss events if the service is down unless the last processed block is persisted. The implementation keeps `last_block` in memory (`provider/app.py:170`), so restarts can miss earlier events.

### Decision 10: Use Per-Tier File-Based Inventory

**What was chosen:**  
The provider uses `provider/inventory.txt` as JSON lines, with one row per tier and `activeLeases` tracking expiration.

**Where it appears in the implementation:**  
`provider/inventory.txt:1`, `provider/app.py:43`, `provider/app.py:47`, `provider/app.py:75`, `provider/app.py:92`; rationale in `docs/decisions.md:37`.

**Why this decision matters:**  
The provider needs a local capacity model so `/catalog` can show available slots and quote issuance can reject sold-out tiers.

**Alternatives:**  
In-memory counters, SQL database, Redis, on-chain inventory, Kubernetes/network-controller state, or actual network telemetry.

**Why the chosen option is justified:**  
For a local PoC, a file is transparent, easy to inspect, and enough to simulate finite capacity.

**Tradeoff or limitation:**  
The file is provider-controlled and not independently verified. It does not prove physical capacity or prevent a dishonest provider from editing inventory.

### Decision 11: Use FastAPI Microservices Rather Than One Process

**What was chosen:**  
The current architecture separates consumer, provider, gateway, and UI into independent services.

**Where it appears in the implementation:**  
`consumer/app.py`, `provider/app.py`, `provider/gateway.py`, `consumer/ui.py`, `docker-compose.yml:69`, `docker-compose.yml:86`, `docker-compose.yml:111`; design note in `docs/decisions.md:49`.

**Why this decision matters:**  
Consumer and provider are separate parties. Separating services makes the trust boundary clearer than the legacy single-process prototype.

**Alternatives:**  
Single Streamlit app, one FastAPI monolith, message-bus architecture, or separate physical hosts.

**Why the chosen option is justified:**  
It gives the paper a clean component architecture while remaining easy to run locally.

**Tradeoff or limitation:**  
Provider and gateway still run inside one provider container (`Dockerfile.provider:35`), and all services run on the same developer machine in the default setup.

### Decision 12: Use Foundry, Anvil, Web3.py, FastAPI, Streamlit, and Ollama

**What was chosen:**  
The contract stack is Foundry/Anvil/Solidity/OpenZeppelin. The service stack is Python with FastAPI, Web3.py, eth-account, Streamlit, httpx, and Ollama.

**Where it appears in the implementation:**  
`contracts/foundry.toml`, `pyproject.toml:6`, `docker-compose.yml`, `consumer/app.py`, `provider/app.py`.

**Why this decision matters:**  
The stack supports local blockchain deployment, deterministic accounts, Python-based service orchestration, and local LLM execution.

**Alternatives:**  
Hardhat, Brownie, Viem/Ethers.js, Node.js services, React frontend, cloud LLM API, or a public testnet.

**Why the chosen option is justified:**  
The implementation is a local feasibility study. Anvil and deterministic keys make demos reproducible. Python reduces integration overhead with FastAPI and Web3.py.

**Tradeoff or limitation:**  
The local environment does not evaluate public-chain latency, gas economics, adversarial mempool conditions, or production-grade model serving.

### Decision 13: Keep the LLM Away from Settlement-Critical Internals

**What was chosen:**  
The LLM can choose tools and pass arguments, but Python functions perform transaction signing, contract calls, and gateway authentication.

**Where it appears in the implementation:**  
Tool map in `consumer/app.py:233`; `_send_tx()` in `consumer/app.py:70`; system prompt constraints in `consumer/app.py:219`.

**Why this decision matters:**  
It constrains autonomy to workflow selection and reduces the risk of the LLM fabricating transaction details.

**Alternatives:**  
Let the LLM directly generate JSON-RPC calls, use fixed scripts without LLM, or require human approval for every step.

**Why the chosen option is justified:**  
The paper can claim autonomous agent operation while keeping financial operations inside deterministic code.

**Tradeoff or limitation:**  
The LLM can still choose wrong tools or arguments. The system prompt instructs it to report exact IDs and not guess (`consumer/app.py:226`, `consumer/app.py:231`), but this is not a formal guarantee.

## Design Decision Table

| Design decision | Alternatives | Chosen option | Rationale | Limitation |
|---|---|---|---|---|
| Neutral settlement layer | Central server, invoices, direct trust | Smart contract escrow | Shared auditable state machine for two agents | Does not enforce real service delivery |
| Payment safety | Pay-first, service-first | ETH escrow plus NFT deposit | Prevents unilateral asset capture during settlement | Off-chain orchestration can still fail |
| Swap execution | Separate deposit and execute | Single `deposit()` atomic swap | Simpler EVM atomicity guarantee | No externally visible pending provider-deposit state |
| Access credential | API key, UUID token, VC, ERC-1155 | ERC-721 NFT | Unique lease credential and standard ownership check | Transferable unless restricted |
| Metadata storage | IPFS, hash only, provider DB | On-chain struct | Easy auditability and metadata matching | Public and costly on real chains |
| Gateway access control | API key, OAuth, mTLS | Ethereum signature plus `ownerOf` | Uses wallet key ownership directly | Replay possible within timestamp window |
| Service delivery | On-chain enforcement, oracle, real QoS | Provider gateway returns metadata | Fits feasibility scope | No proof of bandwidth delivery |
| Event handling | WebSocket, callback, manual | HTTP log polling | Works with Anvil and simple JSON-RPC | In-memory last block can miss events on restart |
| Inventory | Database, on-chain inventory, telemetry | JSON-lines file with `flock` | Transparent local simulation | Provider-controlled, not independently verified |
| Runtime architecture | Single app | FastAPI services plus Streamlit thin UI | Clearer participant boundaries | Co-located on one machine/container setup |
| Payment asset | ERC-20/stablecoin | Native ETH | Simpler escrow and local Anvil demo | No token allowance flow or stable pricing |
| Network environment | Public testnet/mainnet | Local Anvil | Reproducible no-cost development | No public-chain performance/security evidence |

## State Machine

### Implemented States

| State | Meaning | Entered by | Exited by | Why it exists |
|---|---|---|---|---|
| `NONE` | No agreement exists for this ID | Default mapping value | `requestAgreement()` | Lets the contract detect duplicate or missing agreements |
| `REQUESTED` | Consumer locked ETH and is waiting for provider NFT | `requestAgreement()` (`contracts/src/BandwidthEscrow.sol:73`) | `deposit()` or `cancel()` | Holds funds while provider decides whether to fulfill |
| `ACTIVE` | NFT/payment swap completed | `deposit()` (`contracts/src/BandwidthEscrow.sol:115`) | No implemented exit | Marks settlement success and records `tokenId` |
| `CLOSED` | Reserved for future use | Not entered by any implemented function | Not applicable | Placeholder for future lifecycle completion |
| `CANCELLED` | Requested agreement refunded before activation | `cancel()` (`contracts/src/BandwidthEscrow.sol:145`) | No implemented exit | Records failure/refund path |

### Important State-Machine Observations

- `PENDING` is intentionally not implemented because provider deposit and swap occur in the same transaction (`contracts/src/BandwidthEscrow.sol:17`, `contracts/src/BandwidthEscrow.sol:18`).
- `ACTIVE` does not automatically expire on-chain. Service duration is stored in NFT metadata, and the gateway computes `seconds_remaining`, but the escrow contract does not transition to `CLOSED`.
- Cancellation applies only before activation. Once `deposit()` succeeds, there is no contract-level refund/dispute mechanism.

## On-Chain vs Off-Chain Responsibility

| Responsibility | On-chain or off-chain? | Reason |
|---|---|---|
| Store agreement parties, price, requested bandwidth, duration, deadline, status | On-chain | Required for shared settlement state and auditability |
| Hold consumer ETH | On-chain | Prevents provider-controlled custody |
| Mint access credential | On-chain NFT contract, triggered off-chain by provider | Ownership must be verifiable by escrow and gateway |
| Check NFT metadata matches agreement | On-chain | Prevents provider from depositing a mismatched token |
| Transfer NFT and ETH | On-chain | Needs atomicity |
| Catalog discovery | Off-chain | Frequent, mutable provider information |
| Quote issuance | Off-chain | Provider policy and inventory are local in this prototype |
| Inventory/capacity tracking | Off-chain | Simulates provider resource accounting |
| Gateway authorization | Off-chain service reading on-chain state | Network access cannot be served directly by blockchain |
| Signature verification | Off-chain | Gateway needs proof of wallet control before serving API response |
| Bandwidth delivery/enforcement | Not implemented | Explicitly outside current prototype scope |
| Service monitoring/oracle attestation | Not implemented | Future work needed for delivery guarantees |

## Trust Model and Scope

### Who Is Trusted?

- The smart contracts are trusted to execute as deployed on the local Anvil chain.
- The provider is trusted to operate the gateway and to honestly map token ownership to service metadata.
- The provider is trusted for actual capacity claims because inventory is local provider-controlled state.
- The consumer's private key is trusted to represent the consumer's authority.
- The local Anvil environment and deterministic accounts are trusted for repeatable development.

### Who Is Not Fully Trusted?

- The consumer is not trusted to receive service without paying. The escrow requires ETH before provider fulfillment.
- The provider is not trusted to receive ETH without depositing a matching NFT. `deposit()` checks metadata and performs the NFT transfer before releasing ETH.
- Arbitrary gateway callers are not trusted. The gateway requires a valid signature from the current NFT owner.

### What the Smart Contract Guarantees

- A unique agreement ID cannot be reused after creation (`contracts/src/BandwidthEscrow.sol:77`).
- The consumer's ETH is locked in escrow during `REQUESTED` (`contracts/src/BandwidthEscrow.sol:80`).
- The provider cannot call `deposit()` unless `msg.sender` equals the stored provider (`contracts/src/BandwidthEscrow.sol:103`).
- The NFT metadata must match agreement ID, bandwidth, and duration (`contracts/src/BandwidthEscrow.sol:106`, `contracts/src/BandwidthEscrow.sol:108`).
- ETH and NFT settlement occur in one `deposit()` transaction (`contracts/src/BandwidthEscrow.sol:119`, `contracts/src/BandwidthEscrow.sol:121`).
- A requested but unfulfilled agreement can be cancelled and refunded under the implemented rules (`contracts/src/BandwidthEscrow.sol:132`, `contracts/src/BandwidthEscrow.sol:147`).

### What the Smart Contract Does Not Guarantee

- It does not guarantee physical bandwidth delivery.
- It does not monitor service quality.
- It does not know whether the provider has real capacity.
- It does not enforce expiration or close active agreements.
- It does not prevent ERC-721 transfer of the credential.
- It does not implement dispute resolution after activation.
- It does not verify the off-chain quote's `consumerAddress`.

### What the Provider Still Controls

- Service catalog values and prices (`provider/app.py:36`).
- Inventory state (`provider/inventory.txt`).
- Whether the provider event listener is online (`provider/app.py:166`).
- Gateway behavior and returned service metadata (`provider/gateway.py`).
- Real or simulated network service behind the endpoint.

### What the Consumer Independently Verifies

- The provider's address through `/address` (`consumer/app.py:85`).
- On-chain agreement status through `getAgreement()` (`consumer/app.py:176`, `consumer/app.py:178`).
- Gateway response through a signed challenge and token ID, although the consumer trusts the gateway to enforce access properly.

### What the Gateway Verifies

- Timestamp nonce freshness (`provider/gateway.py:44`).
- Signature validity and recovered signer (`provider/gateway.py:49`, `provider/gateway.py:50`).
- Current NFT ownership (`provider/gateway.py:57`, `provider/gateway.py:61`).

### Tier Classification

This implementation realizes **Tier 1: provider-asserted service access**.

It has a provider-operated gateway that checks token ownership and returns service metadata. It does not implement infrastructure-enforced network provisioning such as traffic shaping, router configuration, VPN account provisioning, or QoS. It also does not implement oracle-monitored delivery. Therefore:

- Tier 1 provider-asserted access: implemented.
- Tier 2 infrastructure-enforced access: not implemented.
- Tier 3 oracle-monitored service delivery: not implemented.

This classification is supported by the README's explicit statement that there is "No real money, no real internet traffic" (`README.md:5`) and that the project does not enforce bandwidth at the network layer or use an oracle (`README.md:210`, `README.md:211`).

## How the Implementation Measures Feasibility

The prototype measures feasibility by showing that the mechanism can be assembled end to end: an LLM-assisted consumer can call provider APIs, create an on-chain agreement, trigger provider-side event handling, receive an NFT credential, and use token ownership as a gateway authorization condition.

### Feasibility Dimension Table

| Feasibility dimension | Implementation evidence | Relevant files/tests | What this proves | What it does not prove |
|---|---|---|---|---|
| Functional feasibility | Consumer, provider, gateway, NFT, escrow, and UI components exist and are wired by Docker Compose | `consumer/app.py`, `provider/app.py`, `provider/gateway.py`, `contracts/src/*.sol`, `docker-compose.yml` | The architecture can be implemented as interacting services | It does not prove robustness under failures or adversarial traffic |
| Autonomy feasibility | LLM tool loop can call catalog, request agreement, and check status without another human step | `consumer/app.py:240`, `consumer/app.py:248`, `consumer/app.py:274` | Agent can sequence procurement actions through tools | It does not prove optimal negotiation or correct behavior for all prompts |
| Settlement feasibility | `requestAgreement()` holds ETH and `deposit()` atomically swaps NFT and ETH | `contracts/src/BandwidthEscrow.sol:73`, `contracts/src/BandwidthEscrow.sol:98` | Payment and credential exchange can be coupled on-chain | It does not prove real-world legal/economic enforceability |
| Credential feasibility | ERC-721 token stores service metadata and gateway checks `ownerOf()` | `contracts/src/BandwidthNFT.sol:14`, `provider/gateway.py:57` | Token ownership can be used as machine-readable access credential | It does not prove non-transferable identity or privacy |
| Failure-handling feasibility | `cancel()` refunds while requested; provider rewinds inventory if mint fails before token creation | `contracts/src/BandwidthEscrow.sol:132`, `provider/app.py:245` | Some unfulfilled-request failures have recovery paths | It does not prove automated recovery after orphaned NFTs or post-activation disputes |
| Integration feasibility | Provider event listener responds to `AgreementRequested`, mints, approves, deposits | `provider/app.py:178`, `provider/app.py:220`, `provider/app.py:234`, `provider/app.py:238` | Off-chain agents can react to on-chain state | It does not prove event processing survives restarts or chain reorgs |
| Network-service feasibility | Gateway returns metadata only after ownership signature check | `provider/gateway.py:24`, `provider/gateway.py:61`, `provider/gateway.py:79` | On-chain credential can gate an HTTP service endpoint | It does not prove bandwidth, QoS, or actual packet forwarding |
| Auditability/traceability | Contracts emit events; deployment artifacts record contract creation | `contracts/src/BandwidthEscrow.sol:55`, `contracts/src/BandwidthEscrow.sol:63`, `contracts/broadcast/Deploy.s.sol/31337/run-latest.json:2` | Settlement actions can be observed in chain logs | It does not prove complete business-level audit records |
| Deployment feasibility | Deploy script writes `contracts/deployments/local.json`; latest broadcast shows contract creation receipts | `contracts/script/Deploy.s.sol:20`, `contracts/deployments/local.json:1`, `contracts/broadcast/Deploy.s.sol/31337/run-latest.json:4` | Contracts can be deployed locally | It does not prove testnet/mainnet deployment |
| Build feasibility | During this review, `forge build` succeeded with lint notes and Python files passed `py_compile` | `contracts/foundry.toml`, `pyproject.toml` | Source currently compiles syntactically | It does not substitute for behavioral tests |

### Feasibility Evidence Table

| Claim | Evidence in implementation | Strength of evidence | Remaining gap |
|---|---|---|---|
| Agents can discover and quote services | Consumer `/catalog` and `/quote` calls; provider endpoints | Strong for local HTTP interaction | No multi-provider discovery |
| Consumer can lock payment | Consumer `_send_tx()` calls `requestAgreement()` with `value=priceWei` | Strong at code level | No automated test asserts balances |
| Provider can observe settlement request | Event polling of `AgreementRequested` | Moderate | No persistence of processed blocks |
| Provider can issue credential | Provider calls `BandwidthNFT.mint()` | Strong at code level | No test for mint access control |
| Settlement is atomic | `deposit()` transfers NFT and ETH in one function | Strong design evidence | No formal verification or adversarial tests |
| Gateway can reject non-owners | Gateway compares recovered signer against `ownerOf()` | Strong code evidence | No automated negative test |
| Consumer can verify active service | `check_agreement_status()` reads agreement and calls gateway if active | Strong code evidence | Depends on provider event listener timing |
| Refund path exists | `cancel()` refunds requested agreements | Strong code evidence | No consumer UI/tool integration and no tests |
| Prototype is local and reproducible | Docker Compose, `.env.example`, Anvil deterministic accounts | Strong for local demos | Not public-network evidence |
| Service delivery is token-gated | Gateway checks NFT ownership | Moderate | Gateway does not enforce expiry/status denial or real bandwidth |

## Limitations

### 1. No Real Bandwidth Enforcement

The implementation returns service metadata, but it does not configure routers, traffic shapers, VPN accounts, SDN controllers, or bandwidth meters. The README explicitly says there is no real internet traffic and no network-layer enforcement (`README.md:5`, `README.md:210`).

Why it matters: The paper cannot claim guaranteed bandwidth delivery.

Effect on feasibility claim: It does not undermine the acquisition-mechanism feasibility claim, but it limits the claim to tokenized access coordination.

Future work: Integrate the gateway with a real network controller such as Linux traffic control, WireGuard, Kubernetes network policies, SDN controller APIs, or router QoS.

### 2. No Oracle Verification

There is no oracle or third-party monitor that verifies service delivery. The README explicitly lists oracle verification as not implemented (`README.md:211`).

Why it matters: The provider can claim capacity and deliver less than promised.

Effect on feasibility claim: The prototype proves settlement mechanics, not objective delivery verification.

Future work: Add telemetry oracle attestations, consumer-side measurements, provider-side signed metrics, or dispute windows before final provider payout.

### 3. Provider-Asserted Inventory

Inventory is a provider-local JSON-lines file (`provider/inventory.txt`). The provider can edit it, reset it, or misrepresent capacity.

Why it matters: Inventory availability is not trustless.

Effect on feasibility claim: This is acceptable for Tier 1 provider-asserted access, but it prevents claims about trustless capacity availability.

Future work: Bind inventory to infrastructure state, external attestations, or on-chain deposits representing scarce capacity.

### 4. Gateway Does Not Enforce Expiration or Active Status as Access Denial

The gateway computes `seconds_remaining` and returns agreement status, but it does not reject expired credentials or non-`ACTIVE` status after ownership succeeds (`provider/gateway.py:73`, `provider/gateway.py:76`, `provider/gateway.py:79`).

Why it matters: Access control is weaker than the paper might imply if it says the gateway enforces lease duration.

Effect on feasibility claim: The prototype demonstrates ownership-gated metadata access, not complete lease lifecycle enforcement.

Future work: Reject requests unless `status == ACTIVE` and `seconds_remaining > 0`; add tests for expired and cancelled cases.

### 5. No Automated Project-Specific Behavioral Tests

The `contracts/test/` directory contains no test contracts. During this review, `forge test -vvv` reported no tests found. The CI workflow invokes `forge test -vvv` (`contracts/.github/workflows/test.yml:37`), but there are no local tests exercising contract behavior.

Why it matters: Important properties such as cancellation, metadata mismatch rejection, access denial, and balance changes are not regression-tested.

Effect on feasibility claim: Code inspection supports the design, but empirical evidence is weaker than it would be with tests.

Future work: Add Solidity tests for request/deposit/cancel/mismatch flows and Python integration tests for gateway authorization.

### 6. Local Blockchain Only

Docker Compose uses Anvil (`docker-compose.yml:2`, `docker-compose.yml:4`) and `.env.example` uses deterministic local private keys (`.env.example:1`).

Why it matters: Local-chain results do not represent public-chain latency, gas prices, reorgs, security conditions, or wallet management.

Effect on feasibility claim: It supports local feasibility, not deployment readiness.

Future work: Deploy to a public testnet, collect gas metrics, and test event listener behavior under realistic confirmation policies.

### 7. Quote State Is In-Memory

`pending_quotes` is a process-local dictionary (`provider/app.py:130`). It is lost on provider restart.

Why it matters: A consumer may lock ETH for a quote that the restarted provider no longer remembers.

Effect on feasibility claim: This is acceptable for a demo, but it weakens operational reliability.

Future work: Persist quotes in a database or encode quote commitments on-chain or as signed provider messages.

### 8. Provider Does Not Verify Consumer Address in Quote Handling

The quote stores `consumerAddress` (`provider/app.py:289`), but `_handle_agreement()` verifies only bandwidth, duration, and price (`provider/app.py:204`, `provider/app.py:207`). It does not check that the on-chain agreement consumer equals the quoted consumer.

Why it matters: In a broader threat model, an agreement ID leak could let another address consume the quote.

Effect on feasibility claim: Low for local demo because agreement IDs are random and returned directly to the consumer, but important for production.

Future work: Include consumer address in provider-side verification or use provider-signed quotes that bind consumer, provider, price, duration, and expiry.

### 9. Orphaned NFT Failure Case Requires Manual Cleanup

If minting succeeds but later approval or deposit fails, provider code logs an orphaned NFT and says manual cleanup is needed (`provider/app.py:249`, `provider/app.py:250`, `provider/app.py:251`).

Why it matters: Partial off-chain workflow failures can leave provider-owned credentials that do not settle.

Effect on feasibility claim: The atomic on-chain swap remains safe, but operational recovery is incomplete.

Future work: Add burn/retry logic, provider reconciliation jobs, and tests for failed approval/deposit paths.

### 10. No Post-Activation Dispute or Refund

Once `deposit()` succeeds, ETH is released to the provider immediately (`contracts/src/BandwidthEscrow.sol:121`). There is no dispute period, SLA validation, or partial refund mechanism.

Why it matters: The consumer has no on-chain remedy if service quality is poor after activation.

Effect on feasibility claim: This is compatible with settlement feasibility, but not with service-assurance claims.

Future work: Add escrow release delay, oracle validation, dispute arbitration, or streamed payments.

### 11. Credential Transferability May Be Unintended

Because the NFT inherits standard ERC-721 behavior without transfer restrictions, the credential can be transferred. The gateway authorizes the current owner (`provider/gateway.py:57`, `provider/gateway.py:61`).

Why it matters: Transferability changes the access model from "the original consumer gets service" to "the current token owner gets service."

Effect on feasibility claim: This can be framed as a transferable access right, but should not be described as identity-bound access.

Future work: Choose explicitly between transferable access, non-transferable soulbound credentials, or delegation rules.

### 12. LLM Autonomy Is Prompt- and Tool-Dependent

The consumer agent's behavior depends on the system prompt and tool-calling model (`consumer/app.py:219`, `consumer/app.py:240`, `consumer/app.py:252`).

Why it matters: LLMs can call wrong tools, fail to call tools, or produce incomplete final messages.

Effect on feasibility claim: The deterministic tools are strong, but the autonomous decision layer is not formally verified.

Future work: Add rule-based fallback policies, typed workflow state machines, and tests for common prompts.

### 13. No Privacy Analysis

Agreement metadata is on-chain and public. Token ownership and endpoint metadata are visible to anyone with chain access.

Why it matters: Service purchases can reveal network needs and relationships.

Effect on feasibility claim: Privacy is outside current scope.

Future work: Explore encrypted metadata, zero-knowledge ownership proofs, private chains, or off-chain metadata commitments.

### 14. No Multi-Provider Marketplace

The consumer uses a single provider base URL (`consumer/app.py:29`). There is no provider discovery, ranking, reputation, or competition.

Why it matters: The paper should avoid claiming marketplace behavior.

Effect on feasibility claim: Single-provider feasibility is still meaningful.

Future work: Add provider registry, signed catalogs, reputation, and multi-provider selection.

## Paper-Ready Contribution Statements

The following contribution statements are supported by the implementation and avoid overclaiming:

1. This work contributes a prototype architecture for autonomous agent-to-agent network service acquisition in which a consumer agent can discover a provider offer, request a quote, lock payment on-chain, and verify service access without a human intermediary after the initial request.

2. This work implements a smart-contract escrow mechanism that couples native ETH payment with delivery of an ERC-721 access credential, allowing payment release and credential transfer to occur atomically in a single provider `deposit()` transaction.

3. This work demonstrates an NFT-based access credential model in which service parameters such as agreement ID, bandwidth, duration, start time, and endpoint are stored on-chain and can be checked by both the escrow contract and an off-chain gateway.

4. This work implements a gateway pattern that bridges blockchain ownership state to off-chain service access by requiring a fresh Ethereum signature and verifying current NFT ownership before returning service metadata.

5. This work identifies the trust boundary of tokenized network service provisioning: the prototype validates autonomous acquisition and settlement feasibility, while leaving physical bandwidth enforcement, oracle-based delivery verification, and production-grade dispute handling to future work.

## Paper-Ready Architecture Description

### Overall Architecture Paragraph

The prototype consists of a consumer agent, a provider agent, a smart-contract settlement layer, an NFT access-credential contract, and a provider-operated gateway. The consumer and provider communicate through HTTP APIs for catalog discovery and quote issuance, while the settlement-critical exchange is executed through Ethereum smart contracts deployed on a local Anvil chain. The consumer agent obtains a quote from the provider, locks native ETH in the escrow contract, and later verifies on-chain agreement state. The provider agent observes the escrow contract for agreement request events, mints an NFT credential, approves the escrow contract, and completes settlement by depositing the credential into escrow. The gateway connects the on-chain credential to off-chain service access by checking token ownership before returning service metadata.

### Smart Contract Paragraph

The settlement layer is implemented by `BandwidthEscrow`, a Solidity contract that stores agreement state and mediates the exchange of consumer payment for provider-issued credentials. A consumer creates an agreement by calling `requestAgreement()` with a unique agreement ID, provider address, bandwidth, duration, and ETH payment. The contract stores the request in `REQUESTED` state and emits an `AgreementRequested` event. The provider completes the agreement by calling `deposit()` with a matching NFT token ID. Inside this transaction, the contract verifies provider identity, agreement status, and NFT metadata consistency before transferring the NFT to the consumer and releasing ETH to the provider. This makes the payment/credential exchange atomic at the smart-contract layer.

### Credential/NFT Paragraph

Service access is represented by an ERC-721 token implemented in `BandwidthNFT`. Each token stores metadata directly on-chain, including the agreement ID, bandwidth in Mbps, service duration, mint start time, and endpoint. The provider is the NFT contract owner and is the only address authorized to mint credentials. The escrow contract checks that the NFT's agreement ID, bandwidth, and duration match the stored agreement before it accepts the token for settlement. The token therefore acts as a machine-verifiable access credential rather than merely as a display asset.

### Gateway/Access-Control Paragraph

The gateway is an off-chain FastAPI service that uses blockchain state for access control. A client calls the gateway with a token ID, a timestamp nonce, and an Ethereum signature over that nonce. The gateway rejects stale nonces, recovers the signer address from the signature, and checks the NFT contract's `ownerOf(tokenId)` value. If the signer is the current token owner, the gateway reads token metadata and agreement status and returns service information. In the current prototype, this demonstrates ownership-gated access to service metadata; it does not enforce packet-level bandwidth or independently verify service delivery.

### Agent Workflow Paragraph

The consumer agent uses an Ollama tool-calling loop to translate a natural-language user request into structured actions. It can query the provider catalog, request a provider quote, submit an on-chain escrow request, and check agreement status. The provider agent exposes catalog and quote endpoints and runs an event listener that reacts to `AgreementRequested` events. When the on-chain request matches a pending quote, the provider reserves a simulated inventory slot, mints an NFT, approves the escrow contract, and calls `deposit()` to complete the atomic exchange. This workflow demonstrates autonomous coordination between agents while keeping critical blockchain operations inside deterministic Python functions.

### Trust-Boundary Paragraph

The implementation separates settlement trust from service-delivery trust. The smart contract guarantees that payment is released only when a matching NFT credential is transferred to the consumer, and that a requested agreement can be refunded before activation under the contract's cancellation rules. However, the smart contract does not guarantee that the provider has real network capacity, that bandwidth is physically delivered, or that service quality meets an SLA. The gateway is provider-operated and checks token ownership, but the current implementation does not include independent delivery monitoring or oracle-based dispute resolution. The prototype should therefore be framed as provider-asserted service access with trust-minimized settlement.

### Feasibility-Study Paragraph

The implementation supports a feasibility claim by demonstrating that autonomous service acquisition can be decomposed into off-chain negotiation, on-chain settlement, tokenized credentials, and gateway-based access verification. The prototype runs locally with Docker Compose, Anvil, Foundry, FastAPI services, Streamlit, Web3.py, and Ollama. It provides evidence that a consumer agent can initiate a purchase, a provider agent can react to on-chain state, and a gateway can use NFT ownership as an access-control primitive. The evaluation should be framed around functional integration and mechanism feasibility, not production scalability or real network performance.

## Beginner-Friendly Explanation

### What Problem Is Being Solved?

The project explores whether one software agent can buy temporary network service from another software agent without a human manually approving each step. The buyer wants bandwidth. The seller offers packages. The system needs a way to make payment and access exchange fairly.

### Who Are the Two Agents?

The consumer agent is the buyer. It reads the user's request, chooses a package, asks for a quote, locks payment, and checks whether service is active.

The provider agent is the seller. It publishes available packages, issues quotes, watches the smart contract for payment requests, creates access credentials, and completes settlement.

### What Does the Smart Contract Do?

The smart contract is a neutral settlement box. It holds the consumer's ETH while waiting for the provider to supply the right NFT. If the provider supplies the matching NFT, the smart contract gives the NFT to the consumer and the ETH to the provider in one step.

### What Is Escrow?

Escrow means a neutral third party holds something valuable until agreed conditions are met. Here, the escrow is code on the blockchain. It holds ETH until the provider deposits the correct NFT credential.

### What Is the NFT/Access Credential?

The NFT is a unique token that represents one service lease. It stores the agreement ID, bandwidth, duration, start time, and endpoint. The gateway can ask the blockchain who owns the NFT. Whoever controls the owner's private key can prove ownership with a signature.

### Why Is the Gateway Needed?

The blockchain cannot directly provide internet bandwidth. The gateway is the off-chain service door. It checks the blockchain to see whether the caller owns the NFT, then returns service metadata.

### What Does the Prototype Prove?

It proves that the acquisition flow can be automated locally: quote, payment escrow, NFT minting, atomic settlement, token ownership verification, and gateway response can be connected into one working architecture.

### What Does It Not Prove?

It does not prove that real bandwidth is delivered, that service quality is guaranteed, that a dishonest provider can be detected, or that the system scales to real networks and public blockchains.

## Useful Tables for the Paper

### Implementation Component Table

| Component | Role | Implementation location | Main responsibility | Trust boundary |
|---|---|---|---|---|
| Consumer FastAPI service | Buyer-side agent runtime | `consumer/app.py` | LLM tool loop, quote request, escrow request, gateway check | Holds consumer private key |
| Provider FastAPI service | Seller-side agent runtime | `provider/app.py` | Catalog, quote, event listener, NFT mint, escrow deposit | Holds provider private key and inventory |
| Gateway FastAPI service | Access-control endpoint | `provider/gateway.py` | Signature verification and NFT ownership check | Provider-operated |
| NFT contract | Credential issuer and registry | `contracts/src/BandwidthNFT.sol` | Mint and store service-entitlement metadata | On-chain; owner can mint |
| Escrow contract | Settlement state machine | `contracts/src/BandwidthEscrow.sol` | Hold ETH, validate NFT, atomic settlement, cancellation | On-chain neutral logic |
| Shared contract loader | ABI/address binding | `shared/contracts.py` | Load contract addresses and ABI files | Local service dependency |
| Streamlit UI | Demonstration interface | `consumer/ui.py` | Chat UI, transcript, catalog, token check | Human observability |
| Anvil | Local blockchain | `docker-compose.yml` | Execute local EVM | Development-only chain |
| Deployer | Contract setup | `contracts/script/Deploy.s.sol` | Deploy contracts and write addresses | One-shot local setup |
| Inventory file | Simulated capacity | `provider/inventory.txt` | Track local tier slots and expirations | Provider-controlled |

### Compact Design Decision Table

| Design decision | Alternatives | Chosen option | Rationale | Limitation |
|---|---|---|---|---|
| Settlement mechanism | Central server, invoices | Smart contract escrow | Neutral shared settlement | No delivery guarantee |
| Asset exchange | Sequential payment/credential | Atomic `deposit()` swap | Prevents settlement-side cheating | Operational failures still possible before deposit |
| Credential format | UUID/API key, ERC-1155, VC | ERC-721 NFT | Unique, standard ownership check | Transferable by default |
| Metadata location | IPFS/provider DB | On-chain metadata | Direct contract/gateway reads | Public and costly |
| Access bridge | Pure on-chain service | Off-chain gateway | Real services are off-chain | Gateway trusted to enforce policy |
| Authentication | Password/API key | Signed timestamp nonce | Wallet-based proof of ownership | Replay within window |
| Event response | Manual action, WebSocket | HTTP log polling | Simple local integration | In-memory event cursor |
| Inventory | Real network controller | JSON-lines local file | Simple finite-capacity simulation | Provider-asserted |
| Runtime | Monolith | Separate FastAPI services | Clearer agent boundaries | Local co-location |
| Evaluation chain | Public testnet | Anvil | Reproducible/no real funds | Not production network evidence |

### Compact State Machine Table

| State | Meaning | Entered by | Exited by | Why it exists |
|---|---|---|---|---|
| `NONE` | No agreement | Default | `requestAgreement()` | Detect missing/duplicate agreements |
| `REQUESTED` | ETH locked, provider pending | Consumer `requestAgreement()` | Provider `deposit()` or `cancel()` | Wait state for fulfillment or refund |
| `ACTIVE` | NFT and ETH exchanged | Provider `deposit()` | No implemented exit | Marks successful settlement |
| `CLOSED` | Reserved future terminal state | Not implemented | Not implemented | Placeholder |
| `CANCELLED` | Refunded before activation | `cancel()` | No implemented exit | Records failed/unfulfilled agreement |

### Compact On-Chain vs Off-Chain Responsibility Table

| Responsibility | On-chain or off-chain? | Reason |
|---|---|---|
| ETH custody | On-chain | Requires neutral escrow |
| Agreement state | On-chain | Shared auditable source of truth |
| NFT ownership | On-chain | Gateway and escrow can verify |
| Metadata consistency check | On-chain | Prevents mismatched credential settlement |
| Catalog | Off-chain | Mutable provider information |
| Quote | Off-chain | Provider policy and TTL |
| Event listener | Off-chain | Provider automation |
| Inventory | Off-chain | Simulated provider capacity |
| Gateway | Off-chain | Real service access happens outside blockchain |
| Bandwidth enforcement | Not implemented | Outside current feasibility scope |

### Compact Feasibility Evidence Table

| Claim | Evidence in implementation | Strength of evidence | Remaining gap |
|---|---|---|---|
| Autonomous buyer flow is possible | Ollama tool loop plus provider/chain/gateway tools | Moderate to strong | LLM behavior not exhaustively tested |
| Payment can be escrowed | `requestAgreement()` payable function | Strong code evidence | No balance assertions in tests |
| Credential can be issued | Provider calls `BandwidthNFT.mint()` | Strong code evidence | No minting tests |
| Settlement can be atomic | `deposit()` transfers NFT and ETH | Strong code evidence | No formal proof |
| Gateway can verify ownership | Signature recovery and `ownerOf()` check | Strong code evidence | No negative integration tests |
| Refund path exists | `cancel()` | Strong code evidence | Not wired into consumer tool |
| Local deployment works | deploy script, local deployment JSON, broadcast artifacts | Moderate | No public testnet deployment |
| Service access is tokenized | Gateway accepts token ID plus owner signature | Moderate | Does not enforce bandwidth |

## Evidence Notes from Repository Inspection

During this review:

- `forge build` in `contracts/` completed successfully with compilation skipped because files were unchanged. It emitted lint notes about import style, `vm.writeFile`, and immutable naming, but no build failure.
- `python3 -m py_compile` succeeded for `consumer/app.py`, `consumer/ui.py`, `provider/app.py`, `provider/gateway.py`, `shared/contracts.py`, and the legacy Python files.
- `forge test -vvv` reported no tests found.
- The latest deployment broadcast includes creation transactions for `BandwidthNFT` and `BandwidthEscrow` on chain 31337 (`contracts/broadcast/Deploy.s.sol/31337/run-latest.json:2`, `contracts/broadcast/Deploy.s.sol/31337/run-latest.json:4`, `contracts/broadcast/Deploy.s.sol/31337/run-latest.json:25`, `contracts/broadcast/Deploy.s.sol/31337/run-latest.json:102`, `contracts/broadcast/Deploy.s.sol/31337/run-latest.json:103`).
- `contracts/deployments/local.json` contains local deployed addresses for both contracts (`contracts/deployments/local.json:1`).

These checks support build and deployment feasibility. They do not replace automated behavior tests or a fresh end-to-end demo run.

## Most Important Takeaways for the Paper

1. Present the implementation as a feasibility study of autonomous acquisition and token-gated access, not as a production-ready provisioning platform.

2. The strongest contribution is the atomic exchange of payment and access credential in `BandwidthEscrow.deposit()`.

3. The NFT should be framed as a machine-verifiable access credential, not as proof that bandwidth physically exists.

4. The gateway is the bridge between on-chain settlement state and off-chain service access.

5. The trust boundary must be explicit: the contract guarantees settlement mechanics, not service delivery.

6. The implementation realizes Tier 1 provider-asserted service access. It does not implement infrastructure-enforced provisioning or oracle-monitored delivery.

7. The consumer agent's autonomy is constrained through structured tools. This is a strength because transaction signing and contract calls remain deterministic Python operations.

8. The provider's event listener demonstrates autonomous provider behavior, but its in-memory quote store and event cursor are prototype limitations.

9. The gateway currently verifies token ownership but does not deny expired or non-active credentials. The paper should avoid claiming full lease enforcement unless this is implemented later.

10. The lack of project-specific automated tests is the largest evidence gap. Add tests before making stronger claims about failure handling, access denial, and settlement correctness.

