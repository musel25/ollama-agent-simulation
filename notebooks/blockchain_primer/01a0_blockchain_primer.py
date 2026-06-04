import marimo

__generated_with = "0.23.6"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # 01a0 — Blockchain & smart contracts primer

    A ground-up, hands-on tour. We drive a real local Ethereum chain (`anvil`) through `cast` and `forge`, naming each concept after we've executed it. By the last section you'll be able to read [BandwidthEscrow.sol](../../contracts/src/BandwidthEscrow.sol) line by line.

    **Prereq:** `anvil`, `cast`, `forge` on PATH (Foundry installed). Run cells top to bottom — anvil is started in the next cell and killed in the very last cell.
    """)
    return


@app.cell
def _():
    # --- Notebook runtime setup ---------------------------------------
    import atexit, subprocess, time, shutil, sys, pathlib, json

    PRIMER_DIR = pathlib.Path(__file__).resolve().parent
    REPO_ROOT = PRIMER_DIR.parent.parent
    RPC = 'http://127.0.0.1:8545'

    def run(cmd, cwd=None, check=True):
        """Run a shell command, show it, return stdout."""
        print('$', ' '.join(str(c) for c in cmd))
        r = subprocess.run(cmd, cwd=cwd or PRIMER_DIR, capture_output=True, text=True)
        if r.stdout: print(r.stdout.rstrip())
        if r.returncode != 0:
            if r.stderr: print(r.stderr.rstrip(), file=sys.stderr)
            if check: raise SystemExit(f'command failed: {cmd}')
        return r.stdout.strip()

    for tool in ('anvil', 'cast', 'forge'):
        assert shutil.which(tool), f'{tool} not found on PATH'
    print('Foundry tools OK')
    return REPO_ROOT, RPC, atexit, json, run, subprocess, time


@app.cell
def _(RPC, atexit, run, subprocess, time):
    # --- Start anvil --------------------------------------------------
    anvil_proc = subprocess.Popen(
        ['anvil', '--host', '127.0.0.1', '--port', '8545', '--silent'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    atexit.register(anvil_proc.terminate)

    # Wait for RPC to respond.
    for _ in range(30):
        try:
            run(['cast', 'block-number', '--rpc-url', RPC], check=True)
            break
        except SystemExit:
            time.sleep(0.2)
    else:
        raise RuntimeError('anvil did not come up')
    print(f'anvil PID={anvil_proc.pid}')
    return (anvil_proc,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. What is a chain, really

    You already know the intuition: a blockchain is an append-only distributed database of transactions. Let's make that concrete.

    We started `anvil` — a process that pretends to be the entire Ethereum network. One node, no peers, no proof-of-stake. It exposes the same JSON-RPC interface mainnet does, on `http://127.0.0.1:8545`.

    The chain has two things we'll keep separate in our heads:

    1. **State** — current balances and contract storage (the "database").
    2. **History** — the ordered list of blocks, each containing the    transactions that produced the next state.

    Let's poke at both.
    """)
    return


@app.cell
def _(RPC, run):
    block_number = run(['cast', 'block-number', '--rpc-url', RPC])
    print(f'\ncurrent block number: {block_number}')
    return


@app.cell
def _(RPC, run):
    # The block itself. Block 0 is the genesis block — empty, no parent.
    run(['cast', 'block', '0', '--rpc-url', RPC])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Notice the fields: `number`, `timestamp`, `parentHash`, `stateRoot`, `transactionsRoot`. Each block points to its parent by hash — that's the "chain" part. The `stateRoot` is a Merkle root summarising the entire state at this block — change one balance, the root changes, and so does the block hash.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Accounts & keys

    An Ethereum **account** is just a keypair. Anvil generates 10 funded accounts deterministically on startup — same mnemonic every time, so the addresses and private keys are stable across runs.

    We'll use these two throughout:

    | Role | Address | Private key |
    |---|---|---|
    | Alice (acct 0) | `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` | `0xac0974...ff80` |
    | Bob (acct 1) | `0x70997970C51812dc3A010C7d01b50e0d17dc79C8` | `0x59c699...690d` |

    (Full keys are below — these are well-known test keys. **Never use them on a real network.**)
    """)
    return


@app.cell
def _(run):
    ALICE = '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266'
    ALICE_PK = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
    BOB   = '0x70997970C51812dc3A010C7d01b50e0d17dc79C8'
    BOB_PK = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'

    # Derive Alice's address from her private key to prove the link.
    derived = run(['cast', 'wallet', 'address', ALICE_PK])
    assert derived.lower().endswith(ALICE[2:].lower()), (derived, ALICE)
    print('derived address matches Alice')
    return ALICE, ALICE_PK, BOB, BOB_PK


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    **How the address is derived:** take the public key, hash it with `keccak256`, keep the last 20 bytes. That's it. No central registry, no certificate authority. Whoever holds the private key controls the account because only they can produce signatures that verify against the public key.

    The private key never leaves the holder. Signing happens locally; only the signature goes on-chain.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. A transaction, the smallest unit

    A transaction is the only way to change state. Even deploying a contract or running a function is just "send a tx."

    We're going to send 1 ETH from Alice to Bob. Three things happen:

    1. Alice signs the tx **locally** with her private key.
    2. The signed bytes are sent to anvil over JSON-RPC.
    3. anvil includes the tx in a block. The tx now exists forever; the    state (balances) is updated accordingly.
    """)
    return


@app.cell
def _(ALICE_PK, BOB, RPC, json, run):
    # Send 1 ETH from Alice to Bob. --private-key tells cast which key to sign with.
    tx_hash = run(['cast', 'send', BOB, '--value', '1ether', '--private-key', ALICE_PK, '--rpc-url', RPC, '--json'])
    receipt = json.loads(tx_hash)
    tx_hash = receipt['transactionHash']
    print(f'\ntx hash: {tx_hash}')
    return (tx_hash,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The **transaction hash** is `keccak256(rlp(signed_tx))` — a content-addressed fingerprint. Changing any field of the tx changes the hash; that's how the network refers to txs without trusting any label.

    Let's pull the tx itself, then its receipt.
    """)
    return


@app.cell
def _(RPC, run, tx_hash):
    run(['cast', 'tx', tx_hash, '--rpc-url', RPC])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Field-by-field:

    - **`from`** — recovered from the signature `(v, r, s)`, not sent explicitly.
    - **`to`** — Bob's address. If empty, this would be a contract deployment.
    - **`value`** — wei being transferred (1 ETH = 10¹⁸ wei).
    - **`nonce`** — counter per sender; prevents replay. Alice's first tx is nonce 0.
    - **`gas`, `gasPrice`** — the fee budget.
    - **`input`** — empty for a plain transfer; we'll see it filled later.
    - **`r`, `s`, `yParity`** — the ECDSA signature fields. (Type-2 / EIP-1559 transactions use `yParity` instead of the legacy `v`.)

    The **receipt** is the post-execution summary.
    """)
    return


@app.cell
def _(RPC, run, tx_hash):
    run(['cast', 'receipt', tx_hash, '--rpc-url', RPC])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    `status` `1` means success. `gasUsed` is what Alice actually paid for in computational work. `logs` is empty here (a transfer emits none) — we'll see logs in §8 when we discuss events.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. State vs history

    Two clocks tick in parallel:

    - **State** — the current snapshot. "Alice has X wei." Mutable.   Read via `cast balance`, `cast storage`, contract view calls.
    - **History** — the chain of blocks, each containing the txs that produced   the next state. Immutable. Read via `cast block`, `cast tx`, `cast receipt`.

    The state is *derived* from the history: replay every tx from genesis and you get the current state. That's why the chain is auditable.
    """)
    return


@app.cell
def _(ALICE, BOB, RPC, run):
    # Current balances
    alice_bal = run(['cast', 'balance', ALICE, '--rpc-url', RPC])
    bob_bal   = run(['cast', 'balance', BOB,   '--rpc-url', RPC])
    print(f'\nAlice: {alice_bal} wei')
    print(f'Bob:   {bob_bal} wei')
    return


@app.cell
def _(ALICE, BOB, RPC, run):
    # Same question, but as of block 0 (before the transfer in §3).
    alice_bal0 = run(['cast', 'balance', ALICE, '--block', '0', '--rpc-url', RPC])
    bob_bal0   = run(['cast', 'balance', BOB,   '--block', '0', '--rpc-url', RPC])
    print(f'\nAlice @ block 0: {alice_bal0} wei')
    print(f'Bob   @ block 0: {bob_bal0} wei')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Notice: the *historical* balances differ from the current ones. That's the point — the chain remembers every state it ever held, because it remembers every tx.

    (Anvil keeps full archive state by default. Real Ethereum nodes can drop historical state to save disk, but the txs themselves never go away.)
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. From transactions to code: deploying `Counter.sol`

    Until now, our txs only moved ETH. The next leap: a tx can also **deploy code**. A *smart contract* is just an account whose `code` field is non-empty. When you send a tx to it, the EVM runs that code.

    We'll deploy this tiny contract (see `contracts/Counter.sol`):

    ```solidity
    contract Counter {
        uint256 public number;
        function increment() external { number += 1; }
        function incrementBounded() external {
            require(number < 5, "max reached");
            number += 1;
        }
    }
    ```

    First, compile it with `forge build`.
    """)
    return


@app.cell
def _(run):
    run(['forge', 'build'])
    return


@app.cell
def _(ALICE_PK, RPC, run):
    # Deploy. `forge create` sends a creation tx (no `to`, code in `input`).
    _output = run(['forge', 'create', 'contracts/Counter.sol:Counter', '--private-key', ALICE_PK, '--rpc-url', RPC, '--broadcast'])
    import re
    _m = re.search('Deployed to:\\s*(0x[0-9a-fA-F]{40})', _output)
    assert _m, _output
    COUNTER = _m.group(1)
    # Extract the deployed address from forge's output.
    print(f'\nCounter deployed at: {COUNTER}')
    return COUNTER, re


@app.cell
def _(ALICE, COUNTER, RPC, run):
    # Confirm: the deployed account has CODE. A regular EOA does not.
    counter_code = run(['cast', 'code', COUNTER, '--rpc-url', RPC])
    alice_code   = run(['cast', 'code', ALICE,   '--rpc-url', RPC])
    print(f'\nCounter code length: {len(counter_code)} chars')
    print(f'Alice code:          {alice_code!r}  (empty)')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    That's it. **A smart contract is an account with code.** The code is EVM bytecode — a stack-machine instruction stream. When the network sees a tx whose `to` is this address, every node runs the bytecode against the input, applies the resulting state changes, and agrees on the outcome (because the EVM is deterministic).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. EVM execution: `send` vs `call`, gas, revert

    Two ways to interact with a deployed contract:

    - **`cast send`** — sends a real, signed tx. State changes. Costs gas.   Mined into a block.
    - **`cast call`** — a *local simulation*. The node runs the function   against current state but discards the result. No tx, no block, no   gas paid. Used for reading view functions or previewing a call's   return value.

    Let's increment, then read.
    """)
    return


@app.cell
def _(ALICE_PK, COUNTER, RPC, run):
    run(['cast', 'send', COUNTER, 'increment()',
         '--private-key', ALICE_PK, '--rpc-url', RPC])
    return


@app.cell
def _(COUNTER, RPC, run):
    _n = run(['cast', 'call', COUNTER, 'number()(uint256)', '--rpc-url', RPC])
    print(f'\nnumber() = {_n}')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The receipt for the `increment` tx had a `gasUsed` field — that's the EVM measuring how much computational work the function did. Every opcode (ADD, SSTORE, etc.) has a fixed gas cost; the tx's gas budget must cover the total.

    **Revert.** When a contract calls `require(...)` or `revert(...)` and the condition fails, all state changes from that tx are undone. The tx still gets mined and consumes gas, but its receipt has `status: 0`. Let's see it.
    """)
    return


@app.cell
def _(ALICE_PK, COUNTER, RPC, run):
    # Push number up to 5, then try a 6th increment which should revert.
    for _ in range(4):
        run(['cast', 'send', COUNTER, 'incrementBounded()', '--private-key', ALICE_PK, '--rpc-url', RPC])
    _n = run(['cast', 'call', COUNTER, 'number()(uint256)', '--rpc-url', RPC])
    print(f'\nnumber() = {_n}  (expect 5)')
    return


@app.cell
def _(ALICE_PK, COUNTER, RPC, run):
    # The 6th call should revert with "max reached".
    # We pass check=False because we expect a non-zero exit.
    run(['cast', 'send', COUNTER, 'incrementBounded()',
         '--private-key', ALICE_PK, '--rpc-url', RPC], check=False)
    return


@app.cell
def _(COUNTER, RPC, run):
    # State unchanged — still 5.
    _n = run(['cast', 'call', COUNTER, 'number()(uint256)', '--rpc-url', RPC])
    print(f'\nnumber() after revert = {_n}  (still 5)')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Revert is the contract's safety hatch: any invalid condition unwinds the whole tx atomically. You'll see `BandwidthEscrow` use this extensively — every state-machine violation is a `revert WrongStatus(...)`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. Solidity syntax via `HelloWorld.sol`

    Time to read Solidity, not just call it. `HelloWorld.sol` is tiny but uses every feature `BandwidthEscrow` does. We'll deploy it, exercise each feature, and map it to where the same feature appears in the real escrow contract.

    ```solidity
    contract HelloWorld {
        address public owner;
        mapping(address => uint256) public greetings;

        event Greeted(address indexed who, uint256 count);
        error NotOwner();
        error SendSomething();

        constructor() { owner = msg.sender; }

        function greet() external payable {
            if (msg.value == 0) revert SendSomething();
            greetings[msg.sender] += 1;
            emit Greeted(msg.sender, greetings[msg.sender]);
        }

        function withdraw() external {
            if (msg.sender != owner) revert NotOwner();
            (bool ok, ) = msg.sender.call{value: address(this).balance}("\");
            require(ok, "transfer failed");
        }
    }
    ```
    """)
    return


@app.cell
def _(ALICE_PK, RPC, re, run):
    _output = run(['forge', 'create', 'contracts/HelloWorld.sol:HelloWorld', '--private-key', ALICE_PK, '--rpc-url', RPC, '--broadcast'])
    _m = re.search('Deployed to:\\s*(0x[0-9a-fA-F]{40})', _output)
    assert _m, _output
    HELLO = _m.group(1)
    print(f'\nHelloWorld at: {HELLO}')
    return (HELLO,)


@app.cell
def _(ALICE, ALICE_PK, HELLO, RPC, run):
    # Alice greets twice, paying 0.1 ETH each time.
    for _ in range(2):
        run(['cast', 'send', HELLO, 'greet()', '--value', '0.1ether',
             '--private-key', ALICE_PK, '--rpc-url', RPC])

    # Read her greet count from the mapping.
    count = run(['cast', 'call', HELLO, 'greetings(address)(uint256)',
                 ALICE, '--rpc-url', RPC])
    print(f'\nAlice greeted {count} times')
    return


@app.cell
def _(BOB_PK, HELLO, RPC, run):
    # Owner check: Bob tries to withdraw, should revert NotOwner.
    run(['cast', 'send', HELLO, 'withdraw()',
         '--private-key', BOB_PK, '--rpc-url', RPC], check=False)
    print('(Bob failed as expected)')
    return


@app.cell
def _(ALICE_PK, HELLO, RPC, run):
    # Alice withdraws successfully.
    run(['cast', 'send', HELLO, 'withdraw()',
         '--private-key', ALICE_PK, '--rpc-url', RPC])
    bal = run(['cast', 'balance', HELLO, '--rpc-url', RPC])
    print(f'\nHelloWorld balance: {bal} wei (should be 0)')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Feature map: HelloWorld → BandwidthEscrow

    | Concept | In HelloWorld | In BandwidthEscrow |
    |---|---|---|
    | `pragma solidity ^0.8.20;` | line 2 | line 2 |
    | `mapping(K => V)` | `greetings` | `_agreements` (id → Agreement) |
    | `struct` | — | `Agreement`, `TokenMetadata` |
    | `enum` | — | `Status { NONE, REQUESTED, ACTIVE, CLOSED, CANCELLED }` |
    | `event ... indexed` | `Greeted(address indexed who, uint256)` | `AgreementRequested(uint256 indexed, address indexed, address indexed, ...)` |
    | custom `error` + `revert Foo()` | `NotOwner`, `SendSomething` | `NotProvider`, `WrongStatus`, `MetadataMismatch`, … |
    | `msg.sender` | `withdraw()` ownership check | every function's authorization check |
    | `msg.value` + `payable` | `greet() external payable` | `requestAgreement(...) external payable` |
    | `block.timestamp` | — | `requestDeadline = block.timestamp + 1 hours` |
    | `external` vs `public` | both | all entry points `external` |
    | Low-level `call{value: ...}("\")` | `withdraw()` | `ag.provider.call{value: ag.priceWei}("\")` |
    | Constructor | sets `owner` | sets `nftContract` (immutable) |

    **Storage vs memory** (not exercised here, used in escrow): `storage` is a *reference* to on-chain state (writes persist). `memory` is a scratch copy for the duration of the call. In `deposit()` you'll see `Agreement storage ag = _agreements[id];` — writes to `ag.status` actually mutate the mapping.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8. Events: how off-chain code listens

    A contract can't push data anywhere — it has no network access. What it *can* do is emit an **event** during execution. Events become **logs** attached to the tx receipt and are indexed in a Bloom filter per block. Off-chain code subscribes to these logs over the JSON-RPC WebSocket interface (`eth_subscribe`) or polls them with `eth_getLogs`.

    We already emitted `Greeted` events in §7. Let's read them.
    """)
    return


@app.cell
def _(HELLO, RPC, run):
    # Fetch all logs for HelloWorld since genesis.
    raw = run(['cast', 'logs',
               '--address', HELLO,
               '--from-block', '0',
               '--rpc-url', RPC])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Each log has:

    - **`address`** — contract that emitted it (`HELLO`).
    - **`topics[0]`** — `keccak256("Greeted(address,uint256)")`. The event   *signature hash*. This is how you filter by event type without   knowing the contract's ABI.
    - **`topics[1..]`** — the `indexed` arguments (here: `who`). Indexed   args are stored as topics so they're searchable; non-indexed args   go in `data` and aren't.
    - **`data`** — ABI-encoded non-indexed args (here: `count`).

    Filter by indexed arg — "give me only Greeted events where `who` is Alice":
    """)
    return


@app.cell
def _(ALICE, HELLO, RPC, run):
    # topics[0] = signature, topics[1] = padded Alice address.
    sig = run(['cast', 'keccak', 'Greeted(address,uint256)'])
    alice_topic = '0x' + '0' * 24 + ALICE[2:].lower()
    run(['cast', 'logs',
         '--address', HELLO,
         '--from-block', '0',
         sig, alice_topic, '--rpc-url', RPC])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Why this matters for BandwidthEscrow

    `BandwidthEscrow` emits `AgreementRequested(uint256 indexed agreementId, address indexed consumer, address indexed provider, uint256 bandwidthMbps, uint256 durationSeconds, uint256 priceWei)`.

    Three fields are `indexed` — the EVM allows up to three (plus the signature) topics per log. The choice tells you what the contract expects to be *filtered on*:

    - `agreementId` — "give me events for this specific agreement."
    - `consumer` — "give me every request from this consumer."
    - `provider` — "give me every request directed at this provider."

    This is exactly what the provider service in this repo does: it subscribes to `AgreementRequested` filtered on its own provider address, then reacts to each match by calling `deposit()`. That's the bridge between on-chain state and the off-chain agents — and now you know how the listening side actually works at the protocol level.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 9. Foundry toolkit recap

    We've been using three tools without naming them properly:

    | Tool | What it is | Used in |
    |---|---|---|
    | **`anvil`** | Local Ethereum node — instant blocks, deterministic accounts. | §1 (background process) |
    | **`cast`** | RPC client + signing tool. Anything you can do over JSON-RPC, `cast` has a subcommand for. | §2–§8 |
    | **`forge`** | Build/test/deploy. Compiles Solidity, runs tests, scripts deployments. | §5, §7 |

    `forge` also runs Solidity-native tests. The real project hasn't added any yet, so the next cell will print `No tests found in project!` — that's `forge` telling you the test directory is empty, not an error. Once tests exist in `contracts/test/*.t.sol`, the same command runs them.
    """)
    return


@app.cell
def _(REPO_ROOT, run):
    # Run from REPO_ROOT/contracts where the real project lives.
    run(['forge', 'test', '-vv'], cwd=REPO_ROOT / 'contracts')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    When tests exist, each one is a Solidity function in `contracts/test/*.t.sol` that runs against a fresh EVM instance. `forge` reports pass/fail, gas used, and decoded revert reasons. The same `anvil` we've been using is what powers these tests under the hood.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 10. Reading `BandwidthEscrow` end-to-end

    You now have every piece. Let's read the real contract. Open [`contracts/src/BandwidthEscrow.sol`](../../contracts/src/BandwidthEscrow.sol) in a split view and follow along.

    The contract mediates a swap: a consumer locks ETH, a provider deposits an NFT, and the contract atomically hands the NFT to the consumer and the ETH to the provider. State machine:

    ```
    NONE  --requestAgreement(payable)-->  REQUESTED
    REQUESTED  --deposit(NFT)-->  ACTIVE
    REQUESTED  --cancel()-->  CANCELLED
    ```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 10.1 `requestAgreement` — consumer locks ETH

    ```solidity
    function requestAgreement(
        uint256 agreementId, address provider,
        uint256 bandwidthMbps, uint256 durationSeconds
    ) external payable {
        if (_agreements[agreementId].status != Status.NONE)
            revert AgreementAlreadyExists(agreementId);
        if (msg.value == 0) revert ZeroPriceNotAllowed();

        _agreements[agreementId] = Agreement({
            consumer: msg.sender, provider: provider,
            bandwidthMbps: bandwidthMbps, durationSeconds: durationSeconds,
            priceWei: msg.value,
            requestDeadline: block.timestamp + 1 hours,
            tokenId: 0, status: Status.REQUESTED
        });
        emit AgreementRequested(agreementId, msg.sender, provider, bandwidthMbps, durationSeconds, msg.value);
    }
    ```

    Line by line, every keyword should now be familiar:

    - `external payable` — only callable from outside; accepts ETH (§7).
    - `_agreements[agreementId].status != Status.NONE` — mapping lookup (§7); the default value of a missing key is the zero struct, whose `status` is `NONE` (the first enum variant), so this rejects duplicates.
    - `revert AgreementAlreadyExists(agreementId)` — custom error with parameters; cheaper than `require` with a string (§7, §6).
    - `msg.value == 0` — the ETH the caller sent (§7); zero would mean a free agreement, disallowed.
    - `msg.sender` — the consumer's address, recovered from the tx signature (§3, §7).
    - `block.timestamp + 1 hours` — anvil/EVM time in seconds; `1 hours = 3600` (§4 timestamps in blocks).
    - `emit AgreementRequested(...)` — writes a log so the provider can react off-chain (§8).

    **Why the deadline?** If the provider never deposits, the consumer's ETH would be stuck. After `requestDeadline`, *anyone* can call `cancel()` (see 10.3) — a permissionless escape hatch.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 10.2 `deposit` — provider settles, atomic swap

    ```solidity
    function deposit(uint256 agreementId, uint256 tokenId) external {
        Agreement storage ag = _agreements[agreementId];

        // ── Checks ────────────────────────────────────────────────────
        if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);
        if (msg.sender != ag.provider) revert NotProvider();
        if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);

        BandwidthNFT.TokenMetadata memory meta = nftContract.getTokenMetadata(tokenId);
        if (meta.agreementId != agreementId || ...) revert MetadataMismatch();

        // ── Effects ───────────────────────────────────────────────────
        ag.status = Status.ACTIVE;
        ag.tokenId = tokenId;

        // ── Interactions ──────────────────────────────────────────────
        nftContract.safeTransferFrom(msg.sender, address(this), tokenId);
        nftContract.safeTransferFrom(address(this), ag.consumer, tokenId);
        (bool ok,) = ag.provider.call{value: ag.priceWei}("\");
        if (!ok) revert ETHTransferFailed();

        emit AgreementActive(agreementId, tokenId, ag.consumer, ag.provider);
    }
    ```

    Two things to notice:

    **1. `Agreement storage ag = ...` is a reference.** Writes to `ag.status` mutate the mapping entry directly. If you'd written `Agreement memory ag` you'd be modifying a local copy and the state change would be lost.

    **2. Checks → Effects → Interactions.** Status flips to `ACTIVE` *before* any external call. Why? The low-level `call{value: ...}` hands control to the provider. If the provider is itself a contract, its `receive()` function could re-enter `deposit()` for the same `agreementId`. Because we already set `status = ACTIVE`, the re-entered call hits `WrongStatus` and reverts. This is the **reentrancy guard** baked into the function's structure — no extra library needed.

    The atomic swap is the two `safeTransferFrom` calls + the ETH `call`: either everything happens or nothing happens (any revert undoes the whole tx, §6).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 10.3 `cancel` — refund path

    ```solidity
    function cancel(uint256 agreementId) external {
        Agreement storage ag = _agreements[agreementId];
        if (ag.status == Status.NONE) revert AgreementNotFound(agreementId);
        if (ag.status != Status.REQUESTED) revert WrongStatus(ag.status, Status.REQUESTED);

        bool isConsumer = msg.sender == ag.consumer;
        bool deadlinePassed = block.timestamp > ag.requestDeadline;
        if (!isConsumer && !deadlinePassed) revert DeadlineNotPassed();

        address consumer = ag.consumer;
        uint256 refund = ag.priceWei;
        ag.status = Status.CANCELLED;            // effect before interaction
        (bool ok,) = consumer.call{value: refund}("\");
        if (!ok) revert ETHTransferFailed();
        emit AgreementCancelled(agreementId, consumer);
    }
    ```

    Two-tier authorization: the consumer can always cancel while `REQUESTED`; anyone else only after the deadline. Same CEI ordering — status flipped to `CANCELLED` before the refund leaves the contract.

    ---

    **You're done.** The reference doc you'll want open while reading future contracts is [01a — chain contract model](../01a_chain_contract_model.py), and the lifecycle walkthrough is [01b — escrow lifecycle](../01b_chain_escrow_lifecycle.py).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Teardown

    Kill the anvil process. Re-run this notebook from the top to start fresh.
    """)
    return


@app.cell
def _(anvil_proc):
    if anvil_proc.poll() is None:
        anvil_proc.terminate()
        anvil_proc.wait(timeout=5)
        print('anvil stopped')
    else:
        print('anvil was already stopped')
    return


if __name__ == "__main__":
    app.run()
