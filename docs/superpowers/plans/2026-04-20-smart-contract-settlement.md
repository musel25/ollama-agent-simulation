# Smart Contract Settlement Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a double-escrow smart contract settlement layer to the A2A bandwidth provisioning PoC, split the single-process Streamlit app into three independent FastAPI services (consumer, provider, gateway), and wire everything through Docker Compose with Anvil as the local chain.

**Architecture:** Consumer agent (port 8001) owns an EOA and calls the `BandwidthEscrow` contract via `web3.py`; Provider agent (port 8002) listens for `AgreementRequested` events, mints a `BandwidthNFT` and calls `deposit()` to atomically swap ETH→provider and NFT→consumer; Gateway (port 8003) verifies NFT ownership via signed nonce before returning service metadata. Anvil provides the local chain; Foundry deploys both contracts and writes addresses to `contracts/deployments/local.json`.

**Tech Stack:** Solidity 0.8.20, OpenZeppelin v5, Foundry (forge/anvil), Python 3.11, web3.py v6, FastAPI, Streamlit, Ollama (ministral-3:3b), Docker Compose, uv.

---

## Checkpoint Plan

> **After Task 4** (forge build passes), stop and check in with the user before proceeding to Python refactor.

---

## File Map

### New files
```
contracts/
  foundry.toml
  script/Deploy.s.sol
  src/BandwidthNFT.sol
  src/BandwidthEscrow.sol
  deployments/local.json          ← written by Deploy.s.sol at runtime

consumer/
  __init__.py
  app.py                          ← FastAPI on :8001, owns consumer EOA
  ui.py                           ← Streamlit thin client → consumer/app.py

provider/
  __init__.py
  app.py                          ← FastAPI on :8002, owns provider EOA + event listener
  gateway.py                      ← FastAPI on :8003, NFT-gated service endpoint

shared/
  __init__.py
  contracts.py                    ← loads deployments/local.json, exposes web3 Contract objects
  abi/
    BandwidthNFT.json
    BandwidthEscrow.json

.env.example
docker-compose.yml
Makefile
provider/inventory.txt            ← replaces catalog.txt for the provider service
```

### Modified files
```
README.md
pyproject.toml                    ← add web3, eth-account deps
```

### Deleted / superseded
```
app.py              → replaced by consumer/ui.py
consumer_agent.py   → replaced by consumer/app.py
provider_server.py  → replaced by provider/app.py
catalog.txt         → replaced by provider/inventory.txt
```

---

## Task 1: Foundry project scaffold

**Files:**
- Create: `contracts/foundry.toml`
- Create: `contracts/src/.gitkeep`

- [ ] **Step 1: Initialize Foundry in contracts/**

```bash
cd /home/musel/Github/ollama-agent-simulation
forge init contracts --no-commit
```

Expected output: "Initialized forge project" (or equivalent). The command creates `contracts/src/Counter.sol`, `contracts/test/`, `contracts/script/`, `contracts/foundry.toml`.

- [ ] **Step 2: Remove the stub Counter files**

```bash
rm contracts/src/Counter.sol contracts/test/Counter.t.sol contracts/script/Counter.s.sol 2>/dev/null || true
```

- [ ] **Step 3: Install OpenZeppelin v5**

```bash
cd contracts && forge install OpenZeppelin/openzeppelin-contracts@v5.0.2 --no-commit
```

Verify: `contracts/lib/openzeppelin-contracts/` directory exists.

- [ ] **Step 4: Update foundry.toml**

Replace the generated `foundry.toml` with:

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc = "0.8.20"
remappings = [
    "@openzeppelin/=lib/openzeppelin-contracts/"
]
```

- [ ] **Step 5: Create deployments directory**

```bash
mkdir -p contracts/deployments
echo '{"bandwidthNFT": "", "bandwidthEscrow": ""}' > contracts/deployments/local.json
```

- [ ] **Step 6: Commit**

```bash
git add contracts/
git commit -m "chore: scaffold Foundry project with OpenZeppelin v5"
```

---

## Task 2: BandwidthNFT.sol

**Files:**
- Create: `contracts/src/BandwidthNFT.sol`

- [ ] **Step 1: Write BandwidthNFT.sol**

```solidity
// contracts/src/BandwidthNFT.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title BandwidthNFT
 * @notice ERC-721 token representing a bandwidth service entitlement.
 *         All metadata is stored on-chain; no tokenURI / IPFS.
 *         Only the contract owner (the provider EOA) may mint.
 */
contract BandwidthNFT is ERC721, Ownable {
    struct TokenMetadata {
        uint256 agreementId;
        uint256 bandwidthMbps;
        uint256 durationSeconds;
        uint256 startTime;
        string endpoint;
    }

    uint256 private _nextTokenId;
    mapping(uint256 => TokenMetadata) private _metadata;

    error TokenDoesNotExist(uint256 tokenId);

    constructor(address initialOwner)
        ERC721("BandwidthNFT", "BWNFT")
        Ownable(initialOwner)
    {}

    /**
     * @notice Mint a new bandwidth entitlement NFT. Only owner (provider) can call.
     * @return tokenId The newly minted token ID.
     */
    function mint(
        address to,
        uint256 agreementId,
        uint256 bandwidthMbps,
        uint256 durationSeconds,
        string calldata endpoint
    ) external onlyOwner returns (uint256 tokenId) {
        tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
        _metadata[tokenId] = TokenMetadata({
            agreementId: agreementId,
            bandwidthMbps: bandwidthMbps,
            durationSeconds: durationSeconds,
            startTime: block.timestamp,
            endpoint: endpoint
        });
    }

    /// @notice Returns the on-chain metadata for a given token.
    function getTokenMetadata(uint256 tokenId)
        external
        view
        returns (TokenMetadata memory)
    {
        if (ownerOf(tokenId) == address(0)) revert TokenDoesNotExist(tokenId);
        return _metadata[tokenId];
    }
}
```

- [ ] **Step 2: Run forge build**

```bash
cd contracts && forge build
```

Expected: compilation succeeds, no errors. Warnings about unused variables are OK.

- [ ] **Step 3: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation
git add contracts/src/BandwidthNFT.sol
git commit -m "feat: add BandwidthNFT ERC-721 contract"
```

---

## Task 3: BandwidthEscrow.sol

**Files:**
- Create: `contracts/src/BandwidthEscrow.sol`

- [ ] **Step 1: Write BandwidthEscrow.sol**

```solidity
// contracts/src/BandwidthEscrow.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/utils/ERC721Holder.sol";
import "./BandwidthNFT.sol";

/**
 * @title BandwidthEscrow
 * @notice Double-escrow contract mediating ETH (consumer) ↔ NFT (provider) swaps.
 *
 * State machine per agreement:
 *   NONE → REQUESTED (consumer calls requestAgreement with msg.value)
 *        → ACTIVE    (provider calls deposit; atomic swap fires inside deposit)
 *        → CLOSED    (reserved for future use)
 *        → CANCELLED (consumer or timeout trigger cancel)
 *
 * Note: the paper describes a PENDING state between provider deposit and swap.
 * Here the swap is atomic inside deposit(), so PENDING is never externally observable.
 */
contract BandwidthEscrow is ERC721Holder {
    enum Status { NONE, REQUESTED, ACTIVE, CLOSED, CANCELLED }

    struct Agreement {
        address consumer;
        address provider;
        uint256 bandwidthMbps;
        uint256 durationSeconds;
        uint256 priceWei;
        uint256 requestDeadline;
        uint256 tokenId;
        Status status;
    }

    BandwidthNFT public immutable nftContract;
    mapping(uint256 => Agreement) private _agreements;

    // ── Custom errors ──────────────────────────────────────────────────────────
    error AgreementAlreadyExists(uint256 agreementId);
    error AgreementNotFound(uint256 agreementId);
    error NotProvider();
    error NotConsumer();
    error WrongStatus(Status current, Status required);
    error DeadlineNotPassed();
    error MetadataMismatch();
    error ETHTransferFailed();
    error ZeroPriceNotAllowed();

    // ── Events ─────────────────────────────────────────────────────────────────
    event AgreementRequested(
        uint256 indexed agreementId,
        address indexed consumer,
        address indexed provider,
        uint256 bandwidthMbps,
        uint256 durationSeconds,
        uint256 priceWei
    );
    event AgreementActive(
        uint256 indexed agreementId,
        uint256 tokenId,
        address consumer,
        address provider
    );
    event AgreementCancelled(uint256 indexed agreementId, address indexed consumer);

    constructor(address _nftContract) {
        nftContract = BandwidthNFT(_nftContract);
    }

    /**
     * @notice Consumer locks ETH and creates a new agreement.
     * @param agreementId   Caller-chosen unique ID (uint256).
     * @param provider      Provider EOA address.
     * @param bandwidthMbps Requested bandwidth in Mbps.
     * @param durationSeconds Requested duration in seconds.
     */
    function requestAgreement(
        uint256 agreementId,
        address provider,
        uint256 bandwidthMbps,
        uint256 durationSeconds
    ) external payable {
        if (_agreements[agreementId].status != Status.NONE)
            revert AgreementAlreadyExists(agreementId);
        if (msg.value == 0) revert ZeroPriceNotAllowed();

        _agreements[agreementId] = Agreement({
            consumer: msg.sender,
            provider: provider,
            bandwidthMbps: bandwidthMbps,
            durationSeconds: durationSeconds,
            priceWei: msg.value,
            requestDeadline: block.timestamp + 1 hours,
            tokenId: 0,
            status: Status.REQUESTED
        });

        emit AgreementRequested(
            agreementId,
            msg.sender,
            provider,
            bandwidthMbps,
            durationSeconds,
            msg.value
        );
    }

    /**
     * @notice Provider deposits the NFT and triggers the atomic swap.
     *         Checks: caller == provider, status == REQUESTED, NFT metadata matches.
     *         Effects: status → ACTIVE, tokenId stored.
     *         Interactions: pull NFT in, transfer NFT to consumer, transfer ETH to provider.
     */
    function deposit(uint256 agreementId, uint256 tokenId) external {
        Agreement storage ag = _agreements[agreementId];

        // ── Checks ────────────────────────────────────────────────────────────
        if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);
        if (msg.sender != ag.provider) revert NotProvider();
        if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);

        BandwidthNFT.TokenMetadata memory meta = nftContract.getTokenMetadata(tokenId);
        if (
            meta.agreementId != agreementId ||
            meta.bandwidthMbps != ag.bandwidthMbps ||
            meta.durationSeconds != ag.durationSeconds
        ) revert MetadataMismatch();

        // ── Effects ───────────────────────────────────────────────────────────
        ag.status = Status.ACTIVE;
        ag.tokenId = tokenId;

        // ── Interactions ──────────────────────────────────────────────────────
        // Pull NFT from provider into escrow
        nftContract.safeTransferFrom(msg.sender, address(this), tokenId);
        // Transfer NFT to consumer
        nftContract.safeTransferFrom(address(this), ag.consumer, tokenId);
        // Transfer ETH to provider
        (bool ok,) = ag.provider.call{value: ag.priceWei}("");
        if (!ok) revert ETHTransferFailed();

        emit AgreementActive(agreementId, tokenId, ag.consumer, ag.provider);
    }

    /**
     * @notice Cancel a REQUESTED agreement.
     *         Consumer may cancel at any time while REQUESTED.
     *         Anyone may cancel after requestDeadline has passed.
     */
    function cancel(uint256 agreementId) external {
        Agreement storage ag = _agreements[agreementId];

        if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);
        if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);

        bool isConsumer = msg.sender == ag.consumer;
        bool deadlinePassed = block.timestamp > ag.requestDeadline;

        if (!isConsumer && !deadlinePassed) revert DeadlineNotPassed();

        // Effects before interaction
        address consumer = ag.consumer;
        uint256 refund = ag.priceWei;
        ag.status = Status.CANCELLED;

        (bool ok,) = consumer.call{value: refund}("");
        if (!ok) revert ETHTransferFailed();

        emit AgreementCancelled(agreementId, consumer);
    }

    /// @notice Returns the full agreement struct.
    function getAgreement(uint256 agreementId)
        external
        view
        returns (Agreement memory)
    {
        return _agreements[agreementId];
    }

    receive() external payable {}
}
```

- [ ] **Step 2: Run forge build**

```bash
cd contracts && forge build
```

Expected: both contracts compile cleanly.

- [ ] **Step 3: Run forge fmt**

```bash
cd contracts && forge fmt
```

- [ ] **Step 4: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation
git add contracts/src/BandwidthEscrow.sol
git commit -m "feat: add BandwidthEscrow double-escrow contract"
```

---

## Task 4: Deploy script

**Files:**
- Create: `contracts/script/Deploy.s.sol`

- [ ] **Step 1: Write Deploy.s.sol**

```solidity
// contracts/script/Deploy.s.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../src/BandwidthNFT.sol";
import "../src/BandwidthEscrow.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address providerAddress = vm.envAddress("PROVIDER_ADDRESS");

        vm.startBroadcast(deployerKey);

        BandwidthNFT nft = new BandwidthNFT(providerAddress);
        BandwidthEscrow escrow = new BandwidthEscrow(address(nft));

        vm.stopBroadcast();

        // Write addresses to deployments/local.json
        string memory json = string.concat(
            '{"bandwidthNFT":"',
            vm.toString(address(nft)),
            '","bandwidthEscrow":"',
            vm.toString(address(escrow)),
            '"}'
        );
        vm.writeFile("deployments/local.json", json);
    }
}
```

- [ ] **Step 2: Verify forge build still passes**

```bash
cd contracts && forge build
```

Expected: 2 contracts compiled successfully.

- [ ] **Step 3: Run forge fmt again**

```bash
cd contracts && forge fmt
```

- [ ] **Step 4: Commit**

```bash
cd /home/musel/Github/ollama-agent-simulation
git add contracts/script/Deploy.s.sol
git commit -m "feat: add Deploy script writing addresses to deployments/local.json"
```

> **⏸ CHECKPOINT: Check in with the user after this task.** Report: forge build output, any compilation warnings, and confirm before proceeding to Python refactor.

---

## Task 5: Python deps + shared layer

**Files:**
- Modify: `pyproject.toml`
- Create: `shared/__init__.py`
- Create: `shared/contracts.py`
- Create: `shared/abi/BandwidthNFT.json`
- Create: `shared/abi/BandwidthEscrow.json`

- [ ] **Step 1: Add web3 and eth-account to pyproject.toml**

```bash
cd /home/musel/Github/ollama-agent-simulation
uv add "web3>=6.0,<7" eth-account
```

- [ ] **Step 2: Copy ABI files from Foundry build artifacts**

After `forge build`, the ABI files are in `contracts/out/`:

```bash
mkdir -p shared/abi
python3 -c "
import json, pathlib
for name in ['BandwidthNFT', 'BandwidthEscrow']:
    src = pathlib.Path(f'contracts/out/{name}.sol/{name}.json')
    data = json.loads(src.read_text())
    pathlib.Path(f'shared/abi/{name}.json').write_text(json.dumps(data['abi'], indent=2))
"
```

- [ ] **Step 3: Write shared/contracts.py**

```python
# shared/contracts.py
import json
from pathlib import Path

from web3 import Web3

_ROOT = Path(__file__).parent.parent
_DEPLOYMENTS = _ROOT / "contracts" / "deployments" / "local.json"
_ABI_DIR = Path(__file__).parent / "abi"


def _load_deployments() -> dict:
    return json.loads(_DEPLOYMENTS.read_text())


def get_nft_contract(w3: Web3):
    addrs = _load_deployments()
    abi = json.loads((_ABI_DIR / "BandwidthNFT.json").read_text())
    return w3.eth.contract(address=Web3.to_checksum_address(addrs["bandwidthNFT"]), abi=abi)


def get_escrow_contract(w3: Web3):
    addrs = _load_deployments()
    abi = json.loads((_ABI_DIR / "BandwidthEscrow.json").read_text())
    return w3.eth.contract(address=Web3.to_checksum_address(addrs["bandwidthEscrow"]), abi=abi)
```

- [ ] **Step 4: Write shared/__init__.py**

```python
# shared/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add shared/ pyproject.toml uv.lock
git commit -m "feat: add shared contract bindings and web3 dependency"
```

---

## Task 6: Provider service (app.py + event listener)

**Files:**
- Create: `provider/__init__.py`
- Create: `provider/app.py`
- Create: `provider/inventory.txt`

- [ ] **Step 1: Create provider/inventory.txt**

Per-tier format with slots and expiration tracking (JSON lines):

```json
{"tier": "small",  "mbps": 50,  "durationSeconds": 600, "totalSlots": 10, "activeLeases": []}
{"tier": "medium", "mbps": 100, "durationSeconds": 600, "totalSlots": 8,  "activeLeases": []}
{"tier": "large",  "mbps": 500, "durationSeconds": 600, "totalSlots": 5,  "activeLeases": []}
```

Each lease entry in `activeLeases` is `{"agreementId": <int>, "expiresAt": <unix_timestamp>}`.
Available slots = `totalSlots - len([l for l in activeLeases if l["expiresAt"] > now()])`.
Expired leases are pruned on every read, so slots reclaim automatically.

- [ ] **Step 2: Write provider/app.py**

```python
# provider/app.py
"""
Provider agent FastAPI service — port 8002.
Serves catalog and quote endpoints; runs an event-listener background task
that processes AgreementRequested events and executes the provider side of
the double-escrow swap.
"""
import asyncio
import fcntl
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from eth_account import Account
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from web3 import Web3
from web3.exceptions import ContractLogicError

from shared.contracts import get_escrow_contract, get_nft_contract

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("provider")

# ── Ethereum setup ─────────────────────────────────────────────────────────────
RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
PROVIDER_PRIVATE_KEY = os.environ["PROVIDER_PRIVATE_KEY"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
provider_account = Account.from_key(PROVIDER_PRIVATE_KEY)
PROVIDER_ADDRESS = provider_account.address

# ── Catalog ────────────────────────────────────────────────────────────────────
CATALOG = [
    {"packageId": "small",  "mbps": 50,  "durationSeconds": 600, "priceWei": Web3.to_wei(0.01, "ether")},
    {"packageId": "medium", "mbps": 100, "durationSeconds": 600, "priceWei": Web3.to_wei(0.02, "ether")},
    {"packageId": "large",  "mbps": 500, "durationSeconds": 600, "priceWei": Web3.to_wei(0.08, "ether")},
]
CATALOG_BY_ID = {p["packageId"]: p for p in CATALOG}

# ── Inventory ──────────────────────────────────────────────────────────────────
INVENTORY_FILE = Path(__file__).parent / "inventory.txt"
INVENTORY_LOCK = None  # opened at startup


def _read_inventory() -> int:
    text = INVENTORY_FILE.read_text().strip()
    return int(text.split(":")[1].strip())


def _write_inventory(available: int) -> None:
    INVENTORY_FILE.write_text(f"AVAILABLE: {available}\n")


def _decrement_inventory() -> bool:
    """Thread-safe decrement. Returns True if successful."""
    with open(INVENTORY_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            val = int(f.read().strip().split(":")[1].strip())
            if val <= 0:
                return False
            f.seek(0)
            f.write(f"AVAILABLE: {val - 1}\n")
            f.truncate()
            return True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _increment_inventory() -> None:
    """Rewind on failure."""
    with open(INVENTORY_FILE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            val = int(f.read().strip().split(":")[1].strip())
            f.seek(0)
            f.write(f"AVAILABLE: {val + 1}\n")
            f.truncate()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ── Pending quotes ─────────────────────────────────────────────────────────────
# { agreementId (int) -> {"packageId": str, "consumerAddress": str, "expires": float} }
pending_quotes: dict[int, dict] = {}
QUOTE_TTL = 60  # seconds


def _cleanup_quotes() -> None:
    now = time.time()
    expired = [k for k, v in pending_quotes.items() if v["expires"] < now]
    for k in expired:
        del pending_quotes[k]


# ── Event listener ─────────────────────────────────────────────────────────────
async def _event_listener() -> None:
    nft = get_nft_contract(w3)
    escrow = get_escrow_contract(w3)

    log.info("Event listener started, watching AgreementRequested...")
    last_block = w3.eth.block_number

    while True:
        await asyncio.sleep(2)
        try:
            current = w3.eth.block_number
            if current <= last_block:
                continue

            events = escrow.events.AgreementRequested.get_logs(
                from_block=last_block + 1, to_block=current
            )
            last_block = current

            for evt in events:
                args = evt["args"]
                agreement_id = args["agreementId"]
                log.info(f"AgreementRequested: id={agreement_id}")
                await _handle_agreement_requested(nft, escrow, agreement_id, args)

        except Exception as e:
            log.error(f"Event listener error: {e}")


def _send_tx(func, value: int = 0) -> str:
    """Sign and send a contract function call, return tx hash."""
    tx = func.build_transaction({
        "from": PROVIDER_ADDRESS,
        "nonce": w3.eth.get_transaction_count(PROVIDER_ADDRESS, "pending"),
        "value": value,
    })
    signed = w3.eth.account.sign_transaction(tx, PROVIDER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


async def _handle_agreement_requested(
    nft, escrow, agreement_id: int, args: dict
) -> None:
    _cleanup_quotes()
    quote = pending_quotes.get(agreement_id)

    if quote is None:
        log.warning(f"No pending quote for agreementId={agreement_id}, ignoring.")
        return

    if time.time() > quote["expires"]:
        log.warning(f"Quote for agreementId={agreement_id} expired, ignoring.")
        return

    pkg = CATALOG_BY_ID.get(quote["packageId"])
    if pkg is None:
        log.error(f"Unknown packageId in quote for agreementId={agreement_id}")
        return

    # Verify on-chain params match our quote
    agreement = escrow.functions.getAgreement(agreement_id).call()
    # Agreement tuple order: consumer, provider, bandwidthMbps, durationSeconds, priceWei, ...
    on_chain_mbps = agreement[2]
    on_chain_dur = agreement[3]
    on_chain_price = agreement[4]
    if (
        on_chain_mbps != pkg["mbps"]
        or on_chain_dur != pkg["durationSeconds"]
        or on_chain_price != pkg["priceWei"]
    ):
        log.error(
            f"Param mismatch for agreementId={agreement_id}: "
            f"on_chain=({on_chain_mbps},{on_chain_dur},{on_chain_price}) "
            f"quote=({pkg['mbps']},{pkg['durationSeconds']},{pkg['priceWei']})"
        )
        return

    # Step 1: decrement inventory
    if not _decrement_inventory():
        log.error(f"Insufficient inventory for agreementId={agreement_id}")
        return

    token_id = None
    try:
        # Step 2: mint NFT to provider (minted to self, then transferred by deposit)
        log.info(f"Minting NFT for agreementId={agreement_id}...")
        tx_mint = _send_tx(
            nft.functions.mint(
                PROVIDER_ADDRESS,
                agreement_id,
                pkg["mbps"],
                pkg["durationSeconds"],
                "grpc://provider:8003",
            )
        )
        log.info(f"Minted NFT tx={tx_mint}")

        # Discover the tokenId from the Transfer event
        receipt = w3.eth.get_transaction_receipt(tx_mint)
        transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)").hex()
        token_id = None
        for log_entry in receipt["logs"]:
            if log_entry["topics"][0].hex() == transfer_topic:
                token_id = int(log_entry["topics"][3].hex(), 16)
                break
        if token_id is None:
            raise RuntimeError("Could not find tokenId from mint receipt")

        # Step 3: approve escrow to transfer the NFT
        escrow_address = escrow.address
        tx_approve = _send_tx(nft.functions.approve(escrow_address, token_id))
        log.info(f"Approved escrow for tokenId={token_id} tx={tx_approve}")

        # Step 4: call deposit — triggers atomic swap
        tx_deposit = _send_tx(escrow.functions.deposit(agreement_id, token_id))
        log.info(f"Deposit complete agreementId={agreement_id} tx={tx_deposit}")

        del pending_quotes[agreement_id]

    except Exception as e:
        log.error(f"Error in deposit flow for agreementId={agreement_id}: {e}")
        if token_id is not None:
            log.error(
                f"NFT tokenId={token_id} is now orphaned (minted but not transferred). "
                "Manual cleanup required."
            )
        # Rewind inventory only if mint failed (before NFT existed)
        if token_id is None:
            _increment_inventory()


# ── FastAPI app ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_event_listener())
    yield


app = FastAPI(title="Bandwidth Provider", lifespan=lifespan)


class QuoteRequest(BaseModel):
    packageId: str
    consumerAddress: str


@app.get("/catalog")
def get_catalog() -> list[dict]:
    available = _read_inventory()
    result = []
    for pkg in CATALOG:
        result.append({**pkg, "inventoryAvailable": available})
    return result


@app.post("/quote")
def request_quote(req: QuoteRequest) -> dict:
    pkg = CATALOG_BY_ID.get(req.packageId)
    if pkg is None:
        raise HTTPException(404, f"Package '{req.packageId}' not found.")

    available = _read_inventory()
    if available <= 0:
        raise HTTPException(409, "No inventory available.")

    # Generate a fresh agreementId
    agreement_id = int.from_bytes(secrets.token_bytes(16), "big")

    pending_quotes[agreement_id] = {
        "packageId": req.packageId,
        "consumerAddress": req.consumerAddress,
        "expires": time.time() + QUOTE_TTL,
    }

    return {
        "agreementId": agreement_id,
        "priceWei": pkg["priceWei"],
        "bandwidthMbps": pkg["mbps"],
        "durationSeconds": pkg["durationSeconds"],
    }


@app.get("/inventory")
def get_inventory() -> dict:
    return {"available": _read_inventory()}


if __name__ == "__main__":
    uvicorn.run("provider.app:app", host="0.0.0.0", port=8002, reload=False)
```

- [ ] **Step 3: Write provider/__init__.py**

```python
# provider/__init__.py
```

- [ ] **Step 4: Create provider/inventory.txt**

```bash
echo "AVAILABLE: 1000" > provider/inventory.txt
```

- [ ] **Step 5: Commit**

```bash
git add provider/
git commit -m "feat: add provider FastAPI service with quote endpoint and event listener"
```

---

## Task 7: Gateway service

**Files:**
- Create: `provider/gateway.py`

The gateway validates that a caller owns an NFT before returning service metadata. Auth: client signs a timestamp nonce with their private key; gateway recovers the address and checks `nftContract.ownerOf(tokenId) == signer`.

- [ ] **Step 1: Write provider/gateway.py**

```python
# provider/gateway.py
"""
Bandwidth service gateway — port 8003.
Clients present a signed nonce proving ownership of a wallet address.
Gateway checks on-chain that the address holds the requested NFT token,
reads its metadata, and returns service status.
"""
import os
import time

import uvicorn
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import FastAPI, Header, HTTPException, Query
from web3 import Web3

from shared.contracts import get_escrow_contract, get_nft_contract

RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
w3 = Web3(Web3.HTTPProvider(RPC_URL))

app = FastAPI(title="Bandwidth Gateway")

NONCE_WINDOW = 300  # seconds; nonces older than this are rejected


@app.get("/service")
def check_service(
    token_id: int = Query(..., alias="tokenId"),
    x_signature: str = Header(..., alias="X-Signature"),
    x_nonce: str = Header(..., alias="X-Nonce"),
) -> dict:
    """
    Verify NFT ownership and return service status.

    The client must:
      1. Choose a nonce string = str(unix_timestamp_seconds).
      2. Sign it: eth_account.sign_message(encode_defunct(text=nonce), private_key).
      3. Send: GET /service?tokenId=N  X-Nonce: <nonce>  X-Signature: <hex sig>
    """
    # ── Validate nonce age ────────────────────────────────────────────────────
    try:
        nonce_time = int(x_nonce)
    except ValueError:
        raise HTTPException(400, "X-Nonce must be a unix timestamp integer string.")

    if abs(time.time() - nonce_time) > NONCE_WINDOW:
        raise HTTPException(401, "Nonce expired or too far in the future.")

    # ── Recover signer address ────────────────────────────────────────────────
    try:
        message = encode_defunct(text=x_nonce)
        signer = Account.recover_message(message, signature=x_signature)
    except Exception:
        raise HTTPException(401, "Invalid signature.")

    # ── Check NFT ownership ───────────────────────────────────────────────────
    nft = get_nft_contract(w3)
    try:
        owner = nft.functions.ownerOf(token_id).call()
    except Exception:
        raise HTTPException(404, f"Token {token_id} does not exist.")

    if Web3.to_checksum_address(owner) != Web3.to_checksum_address(signer):
        raise HTTPException(403, "Signer does not own this token.")

    # ── Read metadata ─────────────────────────────────────────────────────────
    meta = nft.functions.getTokenMetadata(token_id).call()
    agreement_id, bandwidth_mbps, duration_seconds, start_time, endpoint = meta

    escrow = get_escrow_contract(w3)
    agreement = escrow.functions.getAgreement(agreement_id).call()
    # tuple: consumer, provider, mbps, dur, priceWei, deadline, tokenId, status
    status_code = agreement[7]  # 0=NONE,1=REQUESTED,2=ACTIVE,3=CLOSED,4=CANCELLED
    STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}

    elapsed = int(time.time()) - start_time
    seconds_remaining = max(0, duration_seconds - elapsed)

    return {
        "token_id": token_id,
        "agreement_id": agreement_id,
        "bandwidth_mbps": bandwidth_mbps,
        "duration_seconds": duration_seconds,
        "seconds_remaining": seconds_remaining,
        "status": STATUS_NAMES.get(status_code, "UNKNOWN"),
        "endpoint": endpoint,
        "signer": signer,
    }


if __name__ == "__main__":
    uvicorn.run("provider.gateway:app", host="0.0.0.0", port=8003, reload=False)
```

- [ ] **Step 2: Commit**

```bash
git add provider/gateway.py
git commit -m "feat: add NFT-gated gateway with signed nonce auth"
```

---

## Task 8: Consumer service

**Files:**
- Create: `consumer/__init__.py`
- Create: `consumer/app.py`
- Create: `consumer/ui.py`

The consumer LLM gains three structured tools: `query_provider_catalog`, `request_agreement_on_chain`, `check_agreement_status`. The LLM narrates to the human; all chain interactions are in Python code, not LLM output.

- [ ] **Step 1: Write consumer/app.py**

```python
# consumer/app.py
"""
Consumer agent FastAPI service — port 8001.
Owns the consumer EOA. Provides an HTTP endpoint the Streamlit UI calls.
The LLM tool-calling loop lives here; web3 interactions execute in Python.
"""
import asyncio
import os
import secrets
import time
from typing import Any

import httpx
import ollama
import uvicorn
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import FastAPI
from pydantic import BaseModel
from web3 import Web3

from shared.contracts import get_escrow_contract, get_nft_contract

# ── Ethereum setup ─────────────────────────────────────────────────────────────
RPC_URL = os.environ.get("RPC_URL", "http://localhost:8545")
CONSUMER_PRIVATE_KEY = os.environ["CONSUMER_PRIVATE_KEY"]

w3 = Web3(Web3.HTTPProvider(RPC_URL))
consumer_account = Account.from_key(CONSUMER_PRIVATE_KEY)
CONSUMER_ADDRESS = consumer_account.address

PROVIDER_BASE_URL = os.environ.get("PROVIDER_BASE_URL", "http://localhost:8002")
GATEWAY_BASE_URL = os.environ.get("GATEWAY_BASE_URL", "http://localhost:8003")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "ministral-3:3b")

# Shared inter-agent log visible to UI
inter_agent_log: list[dict] = []


def _send_tx(func, value: int = 0) -> str:
    tx = func.build_transaction({
        "from": CONSUMER_ADDRESS,
        "nonce": w3.eth.get_transaction_count(CONSUMER_ADDRESS, "pending"),
        "value": value,
    })
    signed = w3.eth.account.sign_transaction(tx, CONSUMER_PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt["status"] != 1:
        raise RuntimeError(f"Transaction reverted: {tx_hash.hex()}")
    return tx_hash.hex()


# ── Tools exposed to LLM ───────────────────────────────────────────────────────

def query_provider_catalog() -> str:
    """Return available bandwidth packages from the provider as a formatted string."""
    inter_agent_log.append({"from": "consumer", "message": "GET /catalog"})
    with httpx.Client() as client:
        resp = client.get(f"{PROVIDER_BASE_URL}/catalog")
        resp.raise_for_status()
    catalog = resp.json()
    lines = [
        f"{p['packageId']}: {p['mbps']} Mbps / {p['durationSeconds']}s / "
        f"{Web3.from_wei(p['priceWei'], 'ether')} ETH "
        f"(inventory: {p['inventoryAvailable']})"
        for p in catalog
    ]
    result = "\n".join(lines)
    inter_agent_log.append({"from": "provider", "message": result})
    return result


def request_agreement_on_chain(package_id: str) -> str:
    """
    Get a quote from the provider for the given package, then call
    escrow.requestAgreement() on-chain with msg.value = priceWei.

    Args:
        package_id: One of 'small', 'medium', 'large'.
    Returns:
        A status string including agreementId and tx hash, or an error message.
    """
    inter_agent_log.append({"from": "consumer", "message": f"POST /quote package_id={package_id}"})
    try:
        with httpx.Client() as client:
            resp = client.post(
                f"{PROVIDER_BASE_URL}/quote",
                json={"packageId": package_id, "consumerAddress": CONSUMER_ADDRESS},
            )
            resp.raise_for_status()
        quote = resp.json()
    except Exception as e:
        return f"ERROR getting quote: {e}"

    agreement_id = quote["agreementId"]
    price_wei = quote["priceWei"]
    mbps = quote["bandwidthMbps"]
    dur = quote["durationSeconds"]

    inter_agent_log.append({
        "from": "provider",
        "message": f"Quote: agreementId={agreement_id} price={Web3.from_wei(price_wei,'ether')} ETH",
    })

    escrow = get_escrow_contract(w3)
    try:
        tx_hash = _send_tx(
            escrow.functions.requestAgreement(
                agreement_id,
                _get_provider_address(),
                mbps,
                dur,
            ),
            value=price_wei,
        )
    except Exception as e:
        return f"ERROR calling requestAgreement: {e}"

    inter_agent_log.append({
        "from": "consumer",
        "message": f"requestAgreement() tx={tx_hash} agreementId={agreement_id}",
    })
    return (
        f"Agreement requested on-chain. agreementId={agreement_id} tx={tx_hash}. "
        "Waiting for provider to mint NFT and complete deposit..."
    )


def _get_provider_address() -> str:
    with httpx.Client() as client:
        resp = client.get(f"{PROVIDER_BASE_URL}/address")
        resp.raise_for_status()
    return resp.json()["address"]


def check_agreement_status(agreement_id: int) -> str:
    """
    Check the on-chain status of an agreement and, if ACTIVE, return NFT details.

    Args:
        agreement_id: The agreementId returned by request_agreement_on_chain.
    Returns:
        Status string. If ACTIVE, also shows token_id and gateway check result.
    """
    escrow = get_escrow_contract(w3)
    nft = get_nft_contract(w3)
    try:
        agreement = escrow.functions.getAgreement(agreement_id).call()
    except Exception as e:
        return f"ERROR reading agreement: {e}"

    STATUS_NAMES = {0: "NONE", 1: "REQUESTED", 2: "ACTIVE", 3: "CLOSED", 4: "CANCELLED"}
    status_code = agreement[7]
    status = STATUS_NAMES.get(status_code, "UNKNOWN")

    if status != "ACTIVE":
        return f"Agreement {agreement_id} status: {status}. Not yet settled."

    token_id = agreement[6]
    inter_agent_log.append({
        "from": "consumer",
        "message": f"Agreement ACTIVE. tokenId={token_id}. Calling gateway...",
    })

    # Sign nonce and call gateway
    nonce = str(int(time.time()))
    message = encode_defunct(text=nonce)
    signed = w3.eth.account.sign_message(message, private_key=CONSUMER_PRIVATE_KEY)
    sig = signed.signature.hex()

    try:
        with httpx.Client() as client:
            resp = client.get(
                f"{GATEWAY_BASE_URL}/service",
                params={"tokenId": token_id},
                headers={"X-Nonce": nonce, "X-Signature": sig},
            )
            resp.raise_for_status()
        data = resp.json()
        inter_agent_log.append({"from": "provider", "message": f"Gateway: {data}"})
        return (
            f"Service ACTIVE. tokenId={token_id}, "
            f"{data['bandwidth_mbps']} Mbps, "
            f"{data['seconds_remaining']}s remaining."
        )
    except Exception as e:
        return f"Agreement ACTIVE but gateway check failed: {e}"


# ── LLM loop ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a bandwidth procurement agent. Help the user acquire
network bandwidth from a provider. Available tools:
- query_provider_catalog: Check available packages and prices.
- request_agreement_on_chain: Get a quote and lock ETH on-chain for a package.
- check_agreement_status: Check if an on-chain agreement is settled and the NFT delivered.

Always query the catalog first, then request the agreement, then check status.
Report the agreementId and final service status to the user."""


def run_consumer(user_message: str, model: str = DEFAULT_MODEL) -> tuple[str, list[dict]]:
    inter_agent_log.clear()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    tools = [query_provider_catalog, request_agreement_on_chain, check_agreement_status]

    TOOL_MAP = {
        "query_provider_catalog": query_provider_catalog,
        "request_agreement_on_chain": request_agreement_on_chain,
        "check_agreement_status": check_agreement_status,
    }

    while True:
        response = ollama.chat(model=model, messages=messages, tools=tools)
        msg = response.message

        if not msg.tool_calls:
            break

        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": msg.tool_calls})

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = tc.function.arguments or {}
            fn = TOOL_MAP.get(tool_name)
            if fn is None:
                result = f"ERROR: unknown tool {tool_name}"
            else:
                try:
                    result = fn(**args)
                except Exception as e:
                    result = f"ERROR in {tool_name}: {e}"
            messages.append({"role": "tool", "tool_name": tool_name, "content": str(result)})

    return msg.content or "", list(inter_agent_log)


# ── FastAPI endpoints ──────────────────────────────────────────────────────────
app = FastAPI(title="Consumer Agent")


class ChatRequest(BaseModel):
    message: str
    model: str = DEFAULT_MODEL


class ChatResponse(BaseModel):
    response: str
    log: list[dict]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    response_text, log = run_consumer(req.message, model=req.model)
    return ChatResponse(response=response_text, log=log)


@app.get("/log")
def get_log() -> list[dict]:
    return list(inter_agent_log)


@app.delete("/log")
def clear_log() -> dict:
    inter_agent_log.clear()
    return {"cleared": True}


if __name__ == "__main__":
    uvicorn.run("consumer.app:app", host="0.0.0.0", port=8001, reload=False)
```

- [ ] **Step 2: Write consumer/ui.py**

```python
# consumer/ui.py
"""
Streamlit thin-client UI — port 8501.
Delegates all logic to consumer/app.py over HTTP.
"""
import httpx
import streamlit as st

CONSUMER_BASE_URL = "http://localhost:8001"
GATEWAY_BASE_URL = "http://localhost:8003"
MODELS = ["ministral-3:3b", "qwen3:1.7b"]


def render_content(content: str) -> None:
    if "<think>" in content and "</think>" in content:
        think = content.split("</think>")[0].replace("<think>", "").strip()
        answer = content.split("</think>", 1)[1].strip()
        with st.expander("🧠 Thinking..."):
            st.write(think)
        if answer:
            st.write(answer)
    else:
        st.write(content)


st.set_page_config(page_title="Bandwidth Agent Simulation", layout="wide")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_log" not in st.session_state:
    st.session_state.agent_log = []

with st.sidebar:
    st.header("⚙️ Settings")
    selected_model = st.selectbox("Ollama model", MODELS, index=0)
    st.caption(f"Pull with: `ollama pull {selected_model}`")

    st.divider()
    st.header("🔑 Gateway Check")
    token_input = st.text_input("Token ID (integer)", placeholder="0")
    if st.button("Verify token") and token_input.strip():
        try:
            # For manual checks from UI, we call the consumer /check endpoint
            with httpx.Client() as client:
                resp = client.get(
                    f"{CONSUMER_BASE_URL}/check_token",
                    params={"tokenId": token_input.strip()},
                )
            if resp.status_code == 200:
                data = resp.json()
                st.success(
                    f"Active — {data['bandwidth_mbps']} Mbps | "
                    f"{data['seconds_remaining']}s remaining"
                )
            else:
                detail = resp.json().get("detail", resp.text)
                st.error(detail)
        except Exception as e:
            st.error(f"Could not reach consumer agent: {e}")

left_col, right_col = st.columns(2)

with left_col:
    st.title("🛒 Consumer Agent")

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            render_content(msg["content"])

    user_input = st.chat_input("Ask the consumer agent...")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Agents working..."):
            try:
                with httpx.Client(timeout=300.0) as client:
                    resp = client.post(
                        f"{CONSUMER_BASE_URL}/chat",
                        json={"message": user_input, "model": selected_model},
                    )
                    resp.raise_for_status()
                data = resp.json()
                response_text = data["response"]
                log_snapshot = data["log"]
            except Exception as e:
                response_text = f"Error reaching consumer agent: {e}"
                log_snapshot = []

        st.session_state.chat_history.append({"role": "assistant", "content": response_text})
        st.session_state.agent_log = log_snapshot
        st.rerun()

with right_col:
    st.title("📡 Provider")
    log_tab, catalog_tab = st.tabs(["Agent-to-Agent Log", "Catalog"])

    with log_tab:
        st.subheader("Consumer ↔ Provider interactions")
        if not st.session_state.agent_log:
            st.info("No agent communication yet.")
        else:
            for entry in st.session_state.agent_log:
                if entry["from"] == "consumer":
                    with st.chat_message("consumer", avatar="🛒"):
                        st.write(entry["message"])
                else:
                    with st.chat_message("provider", avatar="🏪"):
                        st.write(entry["message"])

        if st.button("🗑 Clear Log"):
            with httpx.Client() as client:
                client.delete(f"{CONSUMER_BASE_URL}/log")
            st.session_state.agent_log = []
            st.rerun()

    with catalog_tab:
        st.subheader("Live Bandwidth Catalog")
        if st.button("Refresh"):
            st.rerun()
        try:
            with httpx.Client() as client:
                resp = client.get(f"{CONSUMER_BASE_URL}/catalog_proxy")
                resp.raise_for_status()
            catalog = resp.json()
            for pkg in catalog:
                from web3 import Web3
                price_eth = float(Web3.from_wei(pkg["priceWei"], "ether"))
                st.markdown(
                    f"**{pkg['packageId'].capitalize()}** — "
                    f"{pkg['mbps']} Mbps / {pkg['durationSeconds']}s / "
                    f"`{price_eth} ETH`"
                )
                inv = pkg.get("inventoryAvailable", "?")
                st.caption(f"Inventory: {inv} available")
        except Exception as e:
            st.error(f"Could not reach consumer agent: {e}")
```

- [ ] **Step 3: Add proxy endpoints to consumer/app.py**

Add these two endpoints at the bottom of `consumer/app.py` (before `if __name__`):

```python
@app.get("/catalog_proxy")
def catalog_proxy() -> list[dict]:
    with httpx.Client() as client:
        resp = client.get(f"{PROVIDER_BASE_URL}/catalog")
        resp.raise_for_status()
    return resp.json()


@app.get("/address")
def get_address() -> dict:
    return {"address": CONSUMER_ADDRESS}
```

Also add to provider/app.py:

```python
@app.get("/address")
def provider_address() -> dict:
    return {"address": PROVIDER_ADDRESS}
```

- [ ] **Step 4: Write consumer/__init__.py**

```python
# consumer/__init__.py
```

- [ ] **Step 5: Commit**

```bash
git add consumer/
git commit -m "feat: add consumer FastAPI service and Streamlit thin client"
```

---

## Task 9: .env.example and environment wiring

**Files:**
- Create: `.env.example`
- Create: `.env`

Anvil's deterministic accounts (mnemonic: "test test test test test test test test test test test junk"):
- account[0]: `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` key `0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80`
- account[1]: `0x70997970C51812dc3A010C7d01b50e0d17dc79C8` key `0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d`
- account[2]: `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC` key `0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a`

- [ ] **Step 1: Create .env.example**

```bash
cat > .env.example << 'EOF'
# Anvil deterministic accounts
# account[0] = deployer/owner
DEPLOYER_PRIVATE_KEY=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
DEPLOYER_ADDRESS=0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266

# account[1] = provider EOA
PROVIDER_PRIVATE_KEY=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
PROVIDER_ADDRESS=0x70997970C51812dc3A010C7d01b50e0d17dc79C8

# account[2] = consumer EOA
CONSUMER_PRIVATE_KEY=0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a
CONSUMER_ADDRESS=0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC

# RPC
RPC_URL=http://localhost:8545

# Service URLs (for Docker: use container names)
PROVIDER_BASE_URL=http://localhost:8002
GATEWAY_BASE_URL=http://localhost:8003

# Ollama
OLLAMA_MODEL=ministral-3:3b
EOF
```

- [ ] **Step 2: Copy to .env**

```bash
cp .env.example .env
```

- [ ] **Step 3: Ensure .env is gitignored**

```bash
grep -q '^\.env$' .gitignore 2>/dev/null || echo ".env" >> .gitignore
echo ".python-version" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "contracts/out/" >> .gitignore
echo "contracts/cache/" >> .gitignore
```

- [ ] **Step 4: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example with Anvil deterministic accounts"
```

---

## Task 10: End-to-end local test (no Docker)

This task validates the whole flow locally before adding Docker.

- [ ] **Step 1: Start Anvil in background**

```bash
anvil --block-time 1 &
ANVIL_PID=$!
sleep 2
```

- [ ] **Step 2: Deploy contracts**

```bash
source .env
cd contracts
forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast \
  --private-key $DEPLOYER_PRIVATE_KEY
cd ..
```

Verify `contracts/deployments/local.json` contains two non-empty addresses.

- [ ] **Step 3: Copy ABI files**

```bash
python3 -c "
import json, pathlib
for name in ['BandwidthNFT', 'BandwidthEscrow']:
    src = pathlib.Path(f'contracts/out/{name}.sol/{name}.json')
    data = json.loads(src.read_text())
    pathlib.Path(f'shared/abi/{name}.json').write_text(json.dumps(data['abi'], indent=2))
"
```

- [ ] **Step 4: Start provider service**

```bash
source .env
uv run uvicorn provider.app:app --port 8002 &
PROVIDER_PID=$!
sleep 2
```

- [ ] **Step 5: Start gateway service**

```bash
source .env
uv run uvicorn provider.gateway:app --port 8003 &
GATEWAY_PID=$!
sleep 1
```

- [ ] **Step 6: Start consumer service**

```bash
source .env
uv run uvicorn consumer.app:app --port 8001 &
CONSUMER_PID=$!
sleep 2
```

- [ ] **Step 7: Run a smoke test via curl**

```bash
# Check catalog
curl -s http://localhost:8001/catalog_proxy | python3 -m json.tool

# Request quote + agreement
curl -s -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"I need 100 Mbps for 10 minutes","model":"ministral-3:3b"}' \
  | python3 -m json.tool
```

Observe: the response JSON should contain `response` and `log` fields. The log should show catalog query → quote → requestAgreement tx → deposit tx → gateway check.

- [ ] **Step 8: Kill background processes**

```bash
kill $CONSUMER_PID $GATEWAY_PID $PROVIDER_PID $ANVIL_PID 2>/dev/null || true
```

- [ ] **Step 9: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve issues found during local e2e test"
```

---

## Task 11: Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile.consumer`
- Create: `Dockerfile.provider`

- [ ] **Step 1: Write docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"

services:
  anvil:
    image: ghcr.io/foundry-rs/foundry:latest
    entrypoint: ["anvil", "--block-time", "1", "--host", "0.0.0.0"]
    ports:
      - "8545:8545"
    healthcheck:
      test: ["CMD-SHELL", "cast block-number --rpc-url http://localhost:8545 || exit 1"]
      interval: 3s
      timeout: 5s
      retries: 10

  deployer:
    image: ghcr.io/foundry-rs/foundry:latest
    depends_on:
      anvil:
        condition: service_healthy
    volumes:
      - ./contracts:/app/contracts
    working_dir: /app/contracts
    environment:
      - DEPLOYER_PRIVATE_KEY=${DEPLOYER_PRIVATE_KEY}
      - PROVIDER_ADDRESS=${PROVIDER_ADDRESS}
    entrypoint: >
      sh -c "
        forge script script/Deploy.s.sol
          --rpc-url http://anvil:8545
          --broadcast
          --private-key $$DEPLOYER_PRIVATE_KEY
      "
    restart: "no"

  provider-agent:
    build:
      context: .
      dockerfile: Dockerfile.provider
    depends_on:
      - deployer
    ports:
      - "8002:8002"
      - "8003:8003"
    environment:
      - RPC_URL=http://anvil:8545
      - PROVIDER_PRIVATE_KEY=${PROVIDER_PRIVATE_KEY}
      - PROVIDER_ADDRESS=${PROVIDER_ADDRESS}
    volumes:
      - ./contracts/deployments:/app/contracts/deployments:ro
      - ./provider/inventory.txt:/app/provider/inventory.txt

  consumer-agent:
    build:
      context: .
      dockerfile: Dockerfile.consumer
    depends_on:
      - provider-agent
    ports:
      - "8001:8001"
    environment:
      - RPC_URL=http://anvil:8545
      - CONSUMER_PRIVATE_KEY=${CONSUMER_PRIVATE_KEY}
      - PROVIDER_BASE_URL=http://provider-agent:8002
      - GATEWAY_BASE_URL=http://provider-agent:8003
      - OLLAMA_MODEL=${OLLAMA_MODEL:-ministral-3:3b}

  consumer-ui:
    build:
      context: .
      dockerfile: Dockerfile.consumer
    depends_on:
      - consumer-agent
    ports:
      - "8501:8501"
    environment:
      - CONSUMER_BASE_URL=http://consumer-agent:8001
    entrypoint: ["uv", "run", "streamlit", "run", "consumer/ui.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

- [ ] **Step 2: Write Dockerfile.provider**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY provider/ ./provider/
COPY shared/ ./shared/
COPY contracts/deployments/ ./contracts/deployments/
CMD ["sh", "-c", "uv run uvicorn provider.app:app --host 0.0.0.0 --port 8002 & uv run uvicorn provider.gateway:app --host 0.0.0.0 --port 8003 & wait"]
```

- [ ] **Step 3: Write Dockerfile.consumer**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY consumer/ ./consumer/
COPY shared/ ./shared/
COPY contracts/deployments/ ./contracts/deployments/
CMD ["uv", "run", "uvicorn", "consumer.app:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml Dockerfile.provider Dockerfile.consumer
git commit -m "chore: add Docker Compose and Dockerfiles for all services"
```

---

## Task 12: Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Write Makefile**

```makefile
.PHONY: up down demo contracts

up:
	docker compose up --build -d

down:
	docker compose down -v

contracts:
	source .env && cd contracts && forge script script/Deploy.s.sol \
		--rpc-url http://localhost:8545 \
		--broadcast \
		--private-key $$DEPLOYER_PRIVATE_KEY

demo:
	@echo "=== Step 1: Check catalog ==="
	curl -s http://localhost:8001/catalog_proxy | python3 -m json.tool
	@echo ""
	@echo "=== Step 2: Consumer negotiation (may take 30-60s for LLM + chain) ==="
	curl -s -X POST http://localhost:8001/chat \
		-H "Content-Type: application/json" \
		-d '{"message":"I need 100 Mbps for 10 minutes","model":"$(OLLAMA_MODEL)"}' \
		| python3 -m json.tool
	@echo ""
	@echo "=== Step 3: Provider inventory ==="
	curl -s http://localhost:8002/inventory | python3 -m json.tool
```

- [ ] **Step 2: Commit**

```bash
git add Makefile
git commit -m "chore: add Makefile with up/down/demo/contracts targets"
```

---

## Task 13: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README.md**

```markdown
# Bandwidth Agent Simulation

A proof-of-concept demonstrating autonomous agent-to-agent (A2A) negotiation and
on-chain settlement for tokenized network bandwidth services. Two Ollama-powered LLM
agents (consumer and provider) negotiate over HTTP; settlement is enforced by a
double-escrow Ethereum smart contract running locally on Anvil.

## Architecture

```
Consumer UI (Streamlit :8501)
        │  HTTP
        ▼
Consumer Agent (:8001)
  LLM tool calls ──► query_provider_catalog ──► Provider Agent (:8002) GET /catalog
                 └──► request_agreement_on_chain
                           │  POST /quote → agreementId
                           │  requestAgreement() ──► BandwidthEscrow (Anvil)
                           │                              │ AgreementRequested event
                           │                              ▼
                           │                       Provider Agent (event listener)
                           │                         mint NFT → BandwidthNFT
                           │                         approve escrow
                           │                         deposit() ──► BandwidthEscrow
                           │                                   atomic swap:
                           │                                   ETH → Provider
                           │                                   NFT → Consumer
                 └──► check_agreement_status
                           │  getAgreement() on-chain
                           │  signed nonce → Gateway (:8003) GET /service
                           ▼
                    "100 Mbps, 590s remaining"
```

## Quickstart

### Prerequisites

- [Foundry](https://getfoundry.sh/) (`forge`, `anvil`)
- [Docker + Docker Compose](https://docs.docker.com/get-docker/)
- [Ollama](https://ollama.com/) running locally with `ministral-3:3b` pulled
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Run

```bash
# 1. Copy environment (uses Anvil's deterministic accounts — no real ETH)
cp .env.example .env

# 2. Start all services (Anvil + deployer + provider + consumer + UI)
make up

# 3. Open the UI
open http://localhost:8501
# Type: "I need 100 Mbps for 10 minutes"

# 4. Watch the scripted demo (no UI required)
make demo
```

### Local development (no Docker)

```bash
# Terminal 1: Anvil
anvil --block-time 1

# Terminal 2: Deploy contracts
source .env
cd contracts && forge script script/Deploy.s.sol --rpc-url http://localhost:8545 \
  --broadcast --private-key $DEPLOYER_PRIVATE_KEY

# Terminal 3: Provider
source .env && uv run uvicorn provider.app:app --port 8002

# Terminal 4: Gateway
source .env && uv run uvicorn provider.gateway:app --port 8003

# Terminal 5: Consumer
source .env && uv run uvicorn consumer.app:app --port 8001

# Terminal 6: UI
source .env && uv run streamlit run consumer/ui.py
```

## What this PoC does and does not do

**Does:**
- Tier 1 provider-asserted bandwidth: the provider self-reports capacity; no hardware enforcement.
- Double-escrow atomic swap on a local EVM chain (Anvil).
- On-chain NFT entitlement: the token is the proof of service.
- LLM-driven negotiation: the consumer agent uses natural language to decide which package to buy.
- NFT-gated gateway: the gateway verifies on-chain ownership before responding.

**Does not:**
- Hardware or network enforcement (no QoS, no traffic shaping).
- Oracle attestation of actual bandwidth delivered.
- Multi-round price negotiation (one quote, accept or reject).
- ERC-20 token payments (native ETH only).
- Testnet or mainnet deployment.
- DID / verifiable credential identity (identity = Ethereum address).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with architecture, quickstart, and PoC scope"
```

---

## Task 14: Final verification — make demo

- [ ] **Step 1: Start Anvil + deploy contracts locally**

```bash
source .env
anvil --block-time 1 &
ANVIL_PID=$!
sleep 3
cd contracts && forge script script/Deploy.s.sol \
  --rpc-url http://localhost:8545 \
  --broadcast \
  --private-key $DEPLOYER_PRIVATE_KEY
cd ..
```

- [ ] **Step 2: Copy ABIs**

```bash
python3 -c "
import json, pathlib
for name in ['BandwidthNFT', 'BandwidthEscrow']:
    src = pathlib.Path(f'contracts/out/{name}.sol/{name}.json')
    data = json.loads(src.read_text())
    pathlib.Path(f'shared/abi/{name}.json').write_text(json.dumps(data['abi'], indent=2))
"
```

- [ ] **Step 3: Start all services**

```bash
source .env
uv run uvicorn provider.app:app --port 8002 &
sleep 2
uv run uvicorn provider.gateway:app --port 8003 &
sleep 1
uv run uvicorn consumer.app:app --port 8001 &
sleep 2
```

- [ ] **Step 4: Run make demo**

```bash
OLLAMA_MODEL=ministral-3:3b make demo
```

Expected: catalog JSON printed, then a settlement response with on-chain tx hashes, then inventory decremented by 1.

- [ ] **Step 5: Kill background processes and commit any final fixes**

```bash
kill $(lsof -t -i:8001,8002,8003,8545) 2>/dev/null || true
git add -u
git commit -m "fix: final adjustments from make demo verification"
```

---

## Self-Review Against Spec

### Spec Coverage Check

| Requirement | Task |
|---|---|
| BandwidthNFT ERC-721 with on-chain metadata struct | Task 2 |
| BandwidthEscrow double-escrow with REQUESTED/ACTIVE/CANCELLED | Task 3 |
| requestAgreement / deposit / cancel / getAgreement | Task 3 |
| Custom errors, checks-effects-interactions | Task 3 |
| Deploy script writing local.json | Task 4 |
| Forge build + fmt | Tasks 2, 3, 4 |
| Provider /catalog, /quote, event listener | Task 6 |
| Provider inventory with fcntl.flock | Task 6 |
| Mint → approve → deposit ordering | Task 6 |
| Gateway with signed nonce auth | Task 7 |
| Consumer /chat LLM tool-calling loop | Task 8 |
| Three structured tools (no LLM in chain path) | Task 8 |
| Streamlit thin client | Task 8 |
| .env.example with Anvil accounts | Task 9 |
| Docker Compose (anvil, deployer, provider, consumer, ui) | Task 11 |
| Makefile (up, down, demo) | Task 12 |
| README with ASCII diagram and PoC scope | Task 13 |
| Local e2e test before Docker | Task 10 |
| Final make demo verification | Task 14 |

### Decision Log (things not specified in the prompt)

1. **`catalog.txt` → `provider/inventory.txt`**: Existing `catalog.txt` had per-tier slot counts; new design uses a single integer. Kept old `catalog.txt` in place to avoid breaking the existing branch while new code uses `provider/inventory.txt`.
2. **Provider `/address` endpoint**: The consumer needs the provider's EOA address to call `requestAgreement(provider=...)`. Added a simple `/address` GET on the provider service.
3. **ABI extraction script**: ABIs are copied from `contracts/out/` rather than committed statically, so they always match the compiled contracts.
4. **Transfer event topic decoding for tokenId**: After minting, the tokenId is extracted from the ERC-721 `Transfer` event log rather than a return value (Solidity returns aren't exposed in tx receipts without event parsing).
5. **`check_agreement_status` polls by agreementId**: The LLM must remember and pass the agreementId it got from `request_agreement_on_chain`. If the LLM forgets, it will fail with an error — this is intentional (no LLM should guess chain state).
6. **Gateway `/check_token` proxy on consumer**: Added a `/check_token` endpoint on the consumer service so the Streamlit UI doesn't need to manage private key signing directly.
