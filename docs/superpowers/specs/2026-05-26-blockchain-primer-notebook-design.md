# Blockchain & Smart Contracts Primer Notebook — Design

**Date:** 2026-05-26
**Status:** Draft for review
**Audience:** Blockchain beginner who already understands "blockchain ≈ distributed append-only database." Needs to reach the point of reading [contracts/src/BandwidthEscrow.sol](../../../contracts/src/BandwidthEscrow.sol) line by line.

## Goal

A self-contained, hands-on notebook that builds blockchain and Solidity intuition from first principles using Foundry's local toolchain (`anvil`, `cast`, `forge`), culminating in a guided read of the project's actual smart contracts.

The notebook teaches by *doing*: every concept is first executed against a real local chain, then named.

## Non-goals

- Gas optimization, MEV, L2s, rollups, proxies/upgradeability, consensus mechanisms, mempool dynamics.
- Replacing the existing reference-style [notebooks/01a_chain_contract_model.ipynb](../../../notebooks/01a_chain_contract_model.ipynb). The new notebook sits *before* it; 01a remains the compact field reference.
- Teaching Solidity exhaustively. Only the subset needed to read `BandwidthEscrow.sol` and `BandwidthNFT.sol`.

## Folder layout

```
notebooks/blockchain_primer/
├── 01a0_blockchain_primer.ipynb     # The notebook
├── contracts/
│   ├── Counter.sol                  # Used in §5–6 (deploy + call mechanics)
│   └── HelloWorld.sol               # Used in §7 (Solidity syntax tour)
├── foundry.toml                     # Minimal config so `forge build` works locally
└── README.md                        # One-paragraph pointer back to the notebook
```

Rationale for the folder: keeps all beginner artifacts (notebook + toy contracts + foundry config) in one place, isolated from the production `contracts/` project so a `forge build` here can't disturb the main build.

## Section outline

Each section = 1 markdown cell explaining the concept + 1–3 code cells executing it.

### 1. What is a chain, really
Start `anvil` via `subprocess.Popen`, capture the PID. Run `cast block-number`, `cast block latest`. Observation: a chain is a process holding state + an ordered list of blocks. Anvil is a stand-in for the entire Ethereum network — single node, no peers, no PoS, instant blocks.

### 2. Accounts & keys
Anvil prints 10 deterministic funded accounts with their private keys. Show `cast wallet address <pk>`. Explain: an account = a keypair; the 20-byte address is derived as `keccak256(pubkey)[12:]`. The private key signs transactions and never leaves the holder.

### 3. A transaction, the smallest unit
Send 1 ETH between two anvil accounts with `cast send --private-key …`. Inspect with `cast tx <hash>` and `cast receipt <hash>`. Name every field: `from`, `to`, `value`, `nonce`, `gas`, `gasPrice`, `input`, `v/r/s`.

**Answers user's direct questions here:**
- Yes — every tx is signed with the sender's private key.
- The tx hash is `keccak256(rlp(signed_tx))` — a content-addressed identifier.
- Yes — the chain stores both the tx and a receipt (logs, status, gas used) forever in the block.

### 4. State vs history
Run `cast balance` for both accounts before and after a transfer. Observation: balances are **state** (mutable, current snapshot in the state trie); the tx that changed them is **history** (immutable, in a block). Both coexist; the state trie is what the EVM reads/writes, the chain of blocks is what makes it auditable and replayable.

### 5. From transactions to code: deploying `Counter.sol`
Introduce `Counter.sol`: a contract with one `uint256 count` and an `increment()` function. Deploy with `forge create`. Show:
- `cast code <addr>` on the deployed contract → returns runtime bytecode.
- `cast code <eoa>` on a regular account → returns `0x`.

Statement: **a smart contract is just an account whose `code` field is non-empty. When you send a tx to it, the EVM executes that code.**

### 6. EVM execution: `send` vs `call`, gas, revert
- `cast send counter "increment()"` — state-changing, mined into a block, costs gas.
- `cast call counter "number()(uint256)"` — read-only local simulation, free, returns the value.
- Demonstrate gas: show `gasUsed` in the receipt.
- Demonstrate revert: add a `require(count < 5)` line to a variant or call a non-existent function; show the tx still gets mined but with `status: 0` and all state changes undone.

### 7. Solidity syntax via `HelloWorld.sol` → mapped to BandwidthEscrow
`HelloWorld.sol` is intentionally minimal but exercises every feature `BandwidthEscrow` uses:

```solidity
// HelloWorld.sol (sketch)
pragma solidity ^0.8.20;

contract HelloWorld {
    address public owner;
    mapping(address => uint256) public greetings;
    event Greeted(address indexed who, uint256 count);
    error NotOwner();

    constructor() { owner = msg.sender; }

    function greet() external payable {
        if (msg.value == 0) revert("send something");
        greetings[msg.sender] += 1;
        emit Greeted(msg.sender, greetings[msg.sender]);
    }

    function withdraw() external {
        if (msg.sender != owner) revert NotOwner();
        (bool ok,) = msg.sender.call{value: address(this).balance}("");
        require(ok);
    }
}
```

Two-column treatment per feature:

| Concept | In HelloWorld | In BandwidthEscrow |
|---|---|---|
| `pragma solidity ^0.8.20` | Line 1 | Line 2 |
| `mapping(K => V)` | `greetings` | `_agreements` |
| `struct` | (not in HelloWorld; mentioned) | `Agreement`, `TokenMetadata` |
| `enum` | (mentioned) | `Status` |
| `event ... indexed` | `Greeted` | `AgreementRequested` |
| `error Foo()` + `revert Foo()` | `NotOwner` | `NotProvider`, `WrongStatus`, … |
| `msg.sender` | `withdraw()` | every function |
| `msg.value` + `payable` | `greet()` | `requestAgreement()` |
| `block.timestamp` | (not in HelloWorld; mentioned) | `requestDeadline = block.timestamp + 1 hours` |
| `external` vs `public` | Both shown | All entry points are `external` |
| Low-level `call{value: …}` | `withdraw()` | `ag.provider.call{value: ag.priceWei}("")` |
| Checks-effects-interactions | (mentioned) | `deposit()` walkthrough (§10) |

Deploy `HelloWorld`, send it ETH via `greet()`, read `greetings(<addr>)`, withdraw.

### 8. Events: how off-chain code listens
Use the `Greeted` event from §7. Show:
- `cast logs --address <hello> --from-block 0` — raw logs.
- Each log has `topics[0]` = `keccak256("Greeted(address,uint256)")` (the event signature), `topics[1..]` = indexed args, `data` = non-indexed args ABI-encoded.
- Filter by topic: `cast logs ... 'Greeted(address,uint256)' <indexed_address>`.

Tie back to the project: the provider service subscribes to `AgreementRequested` to drive its state machine — this is the bridge between on-chain transactions and the rest of the system. Point at the `indexed` fields in the actual `AgreementRequested` event and explain why those three (agreementId, consumer, provider) are indexed and the rest aren't.

### 9. Foundry toolkit recap
Name the three tools we've already used:
- `anvil` — local chain (`§1`)
- `cast` — RPC client (`§2–8`)
- `forge` — build/test/deploy (`§5`)

Run `forge build` and `forge test` against the *real* `contracts/` directory (not the primer folder) to show the project's actual test suite passing.

### 10. Reading BandwidthEscrow end-to-end
Walk three functions in order. For each: who can call, what state changes, what events fire, what reverts are possible.

1. **`requestAgreement`** — entry point, `payable`, creates a `REQUESTED` agreement.
2. **`deposit`** — provider settles by depositing the NFT; atomic swap; emphasize checks-effects-interactions ordering (status updated *before* ETH transfer to prevent reentrancy).
3. **`cancel`** — consumer can always cancel while `REQUESTED`; anyone can after `requestDeadline`. Refund path.

End with a pointer to [01a_chain_contract_model.ipynb](../../../notebooks/01a_chain_contract_model.ipynb) as the reference doc to keep open while reading later code.

## Practical setup

**anvil lifecycle:** The notebook starts anvil via `subprocess.Popen` in an early cell, stores the PID, and registers an `atexit` handler + a final teardown cell that calls `proc.terminate()`. Anvil's default port is 8545; the notebook checks if it's already in use and fails loudly if so (rather than silently attaching to an unknown chain).

**Shell calls:** All `cast`/`forge` invocations go through a small `run(cmd: list[str]) -> str` helper that wraps `subprocess.run(..., capture_output=True, check=True, text=True)` and pretty-prints the command + output. Keeps the cells readable and the output reproducible.

**Determinism:** Anvil's `--mnemonic` default produces deterministic accounts. The notebook hardcodes the first two account addresses and the first private key so values shown in markdown match what executes. Re-runs are reproducible.

**Foundry config (`notebooks/blockchain_primer/foundry.toml`):**
```toml
[profile.default]
src = "contracts"
out = "out"
libs = []
solc = "0.8.20"
```
No OpenZeppelin imports needed for the toy contracts, keeping the primer folder self-contained.

## Acceptance criteria

A reader who runs the notebook top to bottom (with `anvil`, `cast`, `forge` installed) should be able to:

1. Explain in their own words what an account, a transaction, a block, and a contract are.
2. Read a simple Solidity contract and identify: state variables, functions, events, errors, `msg.sender`/`msg.value` usage, modifiers like `external`/`payable`.
3. Open [BandwidthEscrow.sol](../../../contracts/src/BandwidthEscrow.sol) and trace the happy path (`requestAgreement` → `deposit`) and the cancel path without needing to look up any keyword.
4. Understand why the provider service can listen for `AgreementRequested` events and react to them off-chain.

## Open decisions deferred to implementation

- Exact wording of each markdown cell (drafted during writing-plans → implementation).
- Whether `Counter.sol` needs a `require` for the revert demo, or whether we synthesize a failing call (e.g. wrong selector) instead. Decide while writing §6.
