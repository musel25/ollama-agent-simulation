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
    # NB10 — Smart Contracts & Tokens (from first principles)

    A **beginner-first, single-step-at-a-time** walkthrough. Every concept is
    introduced as a tiny code change you can inspect. After every action we
    dump the world state, the contract storage, or the event log so you can
    *see* what changed.

    Roadmap:

    1. The world: addresses and accounts.
    2. A pretty-printer so we can debug everything.
    3. Deploying = writing code at a fresh address.
    4. Calling: the meaning of `msg.sender`.
    5. The smallest possible contract: a `Counter`.
    6. Access control with `msg.sender`.
    7. Events / logs — how off-chain code "sees" what happened.
    8. Tokens, the raw idea: balances are just a dict.
    9. Wrapping the dict into an ERC-20 (`transfer`, errors, supply).
    10. Approvals: the permission-slip metaphor.
    11. `transferFrom`: how other contracts pull your tokens.
    12. NFTs (ERC-721) — same idea, different mapping.
    13. A `Vault` contract that holds your tokens.
    14. Edge cases for every flow (insufficient balance, missing approval, not-your-NFT).
    15. Recap.

    > Mental model up front: **a smart contract is an address whose `code` is
    > not empty. A token is a number stored in that contract's storage, keyed
    > by your address. Everything else is variations on that.**
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. The world: addresses and accounts

    On a real chain, every participant (wallets and contracts) is identified
    by a 20-byte address. The chain's state is one giant key/value store:

    ```
    address -> { balance, nonce, code, storage }
    ```

    * **EOA** ("externally owned account") = wallet. `code` is empty. Owned by
      whoever holds the matching private key.
    * **Contract** = same shape, but `code` is non-empty and `storage` is the
      contract's private mapping.

    Let's model that with one dataclass.
    """)
    return


@app.cell
def _():
    from dataclasses import dataclass, field

    @dataclass
    class Account:
        balance: int = 0            # native coin (think ETH, in "wei")
        nonce: int = 0              # tx counter (used for EOAs)
        code: bytes = b""           # empty == wallet, non-empty == contract
        storage: dict = field(default_factory=dict)  # the contract's private state

        @property
        def is_contract(self) -> bool:
            return len(self.code) > 0

    Account
    return (Account,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Now the **world**: a dict from address to `Account`. We give two human
    wallets some ETH so we can refer to them later.
    """)
    return


@app.cell
def _(Account):
    world = {}

    def get(addr):
        """Look up (or auto-create) an account. Real chains do the same — a
        never-touched address still has a logical balance of 0."""
        if addr not in world:
            world[addr] = Account()
        return world[addr]

    # Two human wallets.
    ALICE = "0xAAA...alice"
    BOB   = "0xBBB...bob"
    CAROL = "0xCCC...carol"

    get(ALICE).balance = 100
    get(BOB).balance   = 0
    get(CAROL).balance = 50

    # Quick snapshot: who exists, with how much ETH, are they contracts?
    [(a, acc.balance, "contract" if acc.is_contract else "wallet")
     for a, acc in world.items()]
    return ALICE, BOB, CAROL, get, world


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Alice, Bob, and Carol are all wallets (no `code`). The "world" right now
    is just three rows.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. A pretty-printer so we can debug everything

    Half the difficulty of learning smart contracts is that the state is
    invisible. Let's build one helper that prints **everything**: every
    account, its balance, whether it's a contract, and (for contracts) the
    keys in its storage.

    We'll call this after every interesting action.
    """)
    return


@app.cell
def _(world):
    def show_world(highlight: list[str] | None = None) -> str:
        """Pretty-print the entire world state. `highlight` underlines rows."""
        highlight = set(highlight or [])
        lines = ["WORLD STATE", "-" * 60]
        for addr, acc in world.items():
            marker = "*" if addr in highlight else " "
            kind   = "CONTRACT" if acc.is_contract else "wallet  "
            head   = f"{marker} {kind}  {addr:<22}  bal={acc.balance}"
            lines.append(head)
            if acc.is_contract:
                # Strip the impl pointer key for readability.
                visible = {k: v for k, v in acc.storage.items() if k != "__impl__"}
                for k, v in visible.items():
                    lines.append(f"      storage[{k!r}] = {v}")
        lines.append("-" * 60)
        return "\n".join(lines)

    print(show_world())
    return (show_world,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    From now on every section ends with a `show_world()` so you can confirm
    *exactly* what changed.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Deploying = writing code at a fresh address

    Let's do the dumbest possible "deploy" first: just create a new account
    and stamp some bytes into its `code` field. That's literally all a
    deployment is at the EVM level — the contract address didn't exist a
    moment ago, and now it has bytecode.
    """)
    return


@app.cell
def _(get, show_world):
    # The crudest deploy: make up an address, give it some "code".
    raw_contract_addr = "0xC000...raw_demo"
    acc = get(raw_contract_addr)
    acc.code = b"\x60\x01\x60\x02\x01"   # any non-empty bytes
    acc.storage["msg_of_the_day"] = "hello world"

    print(show_world(highlight=[raw_contract_addr]))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Notice the **only** difference between this row and Alice's row is that
    `code` is non-empty. That's the entire definition. The contract's
    "storage" is just a per-address dict that lives next to its code.

    On real Ethereum the address would be derived from
    `keccak256(deployer, deployer.nonce)` — deterministic but unique. We'll
    cheat with a counter in the next step.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. A proper `deploy` and a `call` with debug tracing

    Two helpers we'll use for the rest of the notebook. Real EVM stores
    bytecode in `code`; we cheat and stash a Python object so we can write
    contract logic in plain Python. The semantics we care about — storage
    persistence and `msg.sender` — are still real.

    Crucially, `call` **prints every invocation** so you can follow the
    control flow when contracts call each other.
    """)
    return


@app.cell
def _(get, world):
    _deploy_counter = {"n": 0}
    TRACE = {"on": True}            # flip to silence the call log

    def deploy(deployer: str, contract_obj) -> str:
        _deploy_counter["n"] += 1
        addr = f"0xC{_deploy_counter['n']:03d}...{type(contract_obj).__name__.lower()}"
        acc = get(addr)
        acc.code = b"<py>"          # any non-empty marker
        acc.storage["__impl__"] = contract_obj
        contract_obj.address = addr
        contract_obj.storage = acc.storage
        contract_obj.events = []     # per-contract event log
        # Solidity-style constructor hook.
        if hasattr(contract_obj, "__init__post__"):
            contract_obj.msg_sender = deployer
            contract_obj.__init__post__(deployer)
        if TRACE["on"]:
            print(f"[deploy] {deployer}  ->  {addr}  ({type(contract_obj).__name__})")
        return addr

    _call_depth = {"d": 0}

    def call(caller: str, contract_addr: str, method: str, *args, **kwargs):
        """Invoke a method on a contract. `caller` becomes msg.sender."""
        impl = world[contract_addr].storage["__impl__"]
        prev_sender = getattr(impl, "msg_sender", None)
        impl.msg_sender = caller
        if TRACE["on"]:
            indent = "  " * _call_depth["d"]
            arg_repr = ", ".join([repr(a) for a in args])
            print(f"[call]{indent} {caller}  ->  {contract_addr}.{method}({arg_repr})")
        _call_depth["d"] += 1
        try:
            result = getattr(impl, method)(*args, **kwargs)
        finally:
            _call_depth["d"] -= 1
            impl.msg_sender = prev_sender
        if TRACE["on"] and result is not None:
            indent = "  " * _call_depth["d"]
            print(f"[ret] {indent} -> {result!r}")
        return result

    deploy, call
    return call, deploy


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The `call` helper does three important things that mirror real EVM:

    1. It sets `msg.sender` on the contract before the method runs.
    2. It **restores** the previous `msg.sender` afterwards. That matters when
      contract A calls contract B which calls back into A — each frame has its
      own sender.
    3. It logs the call. We'll see indented traces later when the Vault calls
      back into the token contract.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. The smallest possible contract: a `Counter`

    Before tokens, the classic "hello world" of smart contracts. One state
    variable, one method to increment it, one method to read it.
    """)
    return


@app.cell
def _():
    class Counter:
        def __init__(self):
            self.msg_sender = None
            self.address    = None
            self.storage    = None  # filled in by deploy()
            self.events     = []

        def __init__post__(self, deployer):
            # Solidity constructor: runs once at deployment.
            self.storage["count"] = 0
            self.storage["deployer"] = deployer

        def increment(self):
            self.storage["count"] += 1

        def get_count(self) -> int:
            return self.storage["count"]

    Counter
    return (Counter,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 5.1 — deploy it. Watch the trace:
    """)
    return


@app.cell
def _(ALICE, Counter, deploy, show_world):
    counter_addr = deploy(ALICE, Counter())
    print()
    print(show_world(highlight=[counter_addr]))
    return (counter_addr,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The Counter contract now exists at its own address. Its storage already
    has `count = 0` and `deployer = Alice`, because the constructor ran.

    Step 5.2 — three calls, then inspect:
    """)
    return


@app.cell
def _(ALICE, BOB, CAROL, call, counter_addr, show_world):
    call(ALICE, counter_addr, "increment")
    call(BOB,   counter_addr, "increment")
    call(CAROL, counter_addr, "increment")
    final = call(ALICE, counter_addr, "get_count")
    print()
    print("final count =", final)
    print()
    print(show_world(highlight=[counter_addr]))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Three things to internalise:

    * The *same code* lives at exactly one address. Anyone calls that address
      to interact.
    * `storage` survives between calls. After three increments it's
      permanently 3 (until someone decrements). This is what makes contracts
      *stateful*.
    * The contract didn't care **who** incremented it — but it easily could
      have, by checking `self.msg_sender`. That single field is the source of
      all access control on a blockchain. We'll use it now.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. Access control with `msg.sender`

    Let's add a "reset" function that only the deployer can call. In Solidity
    you'd write `require(msg.sender == owner)`. In Python: `if ... raise`.

    We'll also catch the revert explicitly so you can see what a *failed*
    transaction looks like.
    """)
    return


@app.cell
def _():
    class OwnedCounter:
        def __init__(self):
            self.msg_sender = None
            self.address    = None
            self.storage    = None
            self.events     = []

        def __init__post__(self, deployer):
            self.storage["count"] = 0
            self.storage["owner"] = deployer

        def increment(self):
            self.storage["count"] += 1

        def reset(self):
            if self.msg_sender != self.storage["owner"]:
                # Real EVM: this would REVERT the whole tx and roll back state.
                raise PermissionError("only owner can reset")
            self.storage["count"] = 0

        def get_count(self) -> int:
            return self.storage["count"]

    OwnedCounter
    return (OwnedCounter,)


@app.cell
def _(ALICE, BOB, OwnedCounter, call, deploy):
    owned_addr = deploy(ALICE, OwnedCounter())
    for _ in range(5):
        call(BOB, owned_addr, "increment")
    print()
    print("count after 5 increments =", call(ALICE, owned_addr, "get_count"))
    return (owned_addr,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 6.1 — Bob tries to reset. He's not the owner; the contract reverts:
    """)
    return


@app.cell
def _(BOB, call, owned_addr):
    try:
        call(BOB, owned_addr, "reset")
    except PermissionError as _err:
        print()
        print(f"REVERT: {_err}")
    print()
    print("count is still =", call(BOB, owned_addr, "get_count"))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 6.2 — Alice resets. Allowed:
    """)
    return


@app.cell
def _(ALICE, call, owned_addr):
    call(ALICE, owned_addr, "reset")
    print()
    print("count after Alice's reset =", call(ALICE, owned_addr, "get_count"))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Big-picture takeaway: every "permission" in the entire token ecosystem
    (only-owner mints, only-bridge burns, governance-only upgrades) is some
    contract checking `self.msg_sender` against a stored address. There is no
    other access-control primitive.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. Events — how the outside world "sees" what happened

    On Ethereum, **events** are append-only log entries that contracts emit.
    Wallets, block explorers, and dapp frontends index these logs to render
    "your USDC balance" and "transaction history." Without events, off-chain
    UIs would have to replay every state read against every block.

    Our model is dead simple: each contract has an `events` list, and we
    `.append(...)` to it. That's it.

    Step 7.1 — add a `LoggedCounter` that emits an event each time it changes:
    """)
    return


@app.cell
def _():
    class LoggedCounter:
        def __init__(self):
            self.msg_sender = None
            self.address    = None
            self.storage    = None
            self.events     = []

        def __init__post__(self, deployer):
            self.storage["count"] = 0
            self.events.append(("Created", deployer))

        def increment(self):
            self.storage["count"] += 1
            self.events.append(("Incremented", self.msg_sender, self.storage["count"]))

    LoggedCounter
    return (LoggedCounter,)


@app.cell
def _(ALICE, BOB, CAROL, LoggedCounter, call, deploy, world):
    logged_addr = deploy(ALICE, LoggedCounter())
    call(BOB,   logged_addr, "increment")
    call(CAROL, logged_addr, "increment")
    call(BOB,   logged_addr, "increment")

    print()
    print("EVENT LOG for", logged_addr)
    for _ev in world[logged_addr].storage["__impl__"].events:
        print(" ", _ev)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Two things to note:

    * Events are append-only. A reorg would roll some back, but normal calls
      never edit existing log entries.
    * Events are *not* state — contracts can't read them. They exist solely
      for off-chain consumers. Token transfers, NFT mints, governance votes —
      every block explorer feature you've used is reading event logs.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8. Tokens — the raw idea, without any class

    Forget contracts for a second. What is "Alice has 100 WOOD"?

    Answer: a number `100` stored in a dictionary `balances`, under key
    `Alice`. That's the *whole* essence of fungible tokens. Let's literally
    do that with a bare dict — no class, no contract — to convince ourselves.
    """)
    return


@app.cell
def _(ALICE, BOB):
    raw_balances = {ALICE: 1_000, BOB: 0}
    print("before:", raw_balances)

    # Alice "sends" 200 to Bob — just two arithmetic updates.
    amount = 200
    raw_balances[ALICE] -= amount
    raw_balances[BOB]   += amount

    print("after: ", raw_balances)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    That's the entire mechanic. Nothing moved, no object travelled. Two
    counter updates and the total is preserved.

    What's missing for it to be a real token? Three things:

    1. **A home** — the dict needs to live inside a contract's storage so it
      can't be edited arbitrarily.
    2. **A guard** — only "Alice" should be allowed to decrement
      `balances[Alice]`. That's what `msg.sender` is for.
    3. **A standard interface** — wallets and exchanges need to know which
      function names to call. That standard is ERC-20.

    Let's add all three.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 9. Wrapping the dict into an ERC-20

    Below is a fungible token contract. It exposes the ERC-20 function names
    (snake_case here for Pythonicness; real Solidity uses `balanceOf`,
    `transferFrom` etc.). Wallets recognise a token because it implements
    these exact functions; "ERC-20 compliance" is just "has these methods."
    """)
    return


@app.cell
def _():
    class ERC20:
        def __init__(self, name: str, symbol: str, initial_supply: int):
            self.name = name
            self.symbol = symbol
            self._initial = initial_supply
            self.msg_sender = None
            self.address    = None
            self.storage    = None
            self.events     = []

        def __init__post__(self, deployer):
            self.storage["balances"]   = {deployer: self._initial}
            self.storage["allowances"] = {}   # (owner, spender) -> int
            self.storage["total"]      = self._initial
            # The "mint from nowhere to deployer" event — by convention the
            # zero address is the source.
            self.events.append(("Transfer", "0x000...zero", deployer, self._initial))

        # ---- view (read-only) ----
        def balance_of(self, who: str) -> int:
            return self.storage["balances"].get(who, 0)

        def total_supply(self) -> int:
            return self.storage["total"]

        def allowance(self, owner: str, spender: str) -> int:
            return self.storage["allowances"].get((owner, spender), 0)

        # ---- state-changing ----
        def transfer(self, to: str, amount: int) -> bool:
            sender = self.msg_sender
            bals = self.storage["balances"]
            if bals.get(sender, 0) < amount:
                raise ValueError(
                    f"REVERT: {sender} has {bals.get(sender, 0)} {self.symbol}, "
                    f"can't send {amount}"
                )
            bals[sender] = bals.get(sender, 0) - amount
            bals[to]     = bals.get(to, 0) + amount
            self.events.append(("Transfer", sender, to, amount))
            return True

        def approve(self, spender: str, amount: int) -> bool:
            self.storage["allowances"][(self.msg_sender, spender)] = amount
            self.events.append(("Approval", self.msg_sender, spender, amount))
            return True

        def transfer_from(self, owner: str, to: str, amount: int) -> bool:
            spender = self.msg_sender
            allow = self.storage["allowances"]
            bals  = self.storage["balances"]
            current = allow.get((owner, spender), 0)
            if current < amount:
                raise ValueError(
                    f"REVERT: allowance({owner}->{spender}) = {current}, "
                    f"can't spend {amount}"
                )
            if bals.get(owner, 0) < amount:
                raise ValueError(f"REVERT: {owner} has insufficient {self.symbol}")
            allow[(owner, spender)] = current - amount
            bals[owner]            -= amount
            bals[to]                = bals.get(to, 0) + amount
            self.events.append(("Transfer", owner, to, amount))
            return True

    ERC20
    return (ERC20,)


@app.cell
def _(ALICE, ERC20, deploy):
    # Alice deploys WOOD: 1000 units, minted to herself by the constructor.
    wood = deploy(ALICE, ERC20("Wood", "WOOD", 1_000))
    return (wood,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 9.1 — a helper that prints balances side-by-side. We'll reuse this
    every time anything moves.
    """)
    return


@app.cell
def _(world):
    def show_balances(token_addr: str, who: list[str], label: str = ""):
        impl = world[token_addr].storage["__impl__"]
        title = f"{impl.symbol} balances" + (f"  ({label})" if label else "")
        print(title)
        print("-" * len(title))
        for w in who:
            print(f"  {w:<22}  {impl.balance_of(w):>6}")
        print(f"  {'TOTAL SUPPLY':<22}  {impl.total_supply():>6}")
        print()

    show_balances
    return (show_balances,)


@app.cell
def _(ALICE, BOB, CAROL, show_balances, wood):
    show_balances(wood, [ALICE, BOB, CAROL], label="initial state")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 9.2 — Alice transfers 200 WOOD to Bob:
    """)
    return


@app.cell
def _(ALICE, BOB, CAROL, call, show_balances, wood):
    call(ALICE, wood, "transfer", BOB, 200)
    print()
    show_balances(wood, [ALICE, BOB, CAROL], label="after Alice -> Bob 200")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 9.3 — edge case. Carol tries to send 999 WOOD she doesn't have. The
    contract **reverts** and balances are unchanged:
    """)
    return


@app.cell
def _(ALICE, BOB, CAROL, call, show_balances, wood):
    try:
        call(CAROL, wood, "transfer", ALICE, 999)
    except ValueError as _err:
        print()
        print(_err)
    print()
    show_balances(wood, [ALICE, BOB, CAROL], label="unchanged after revert")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 9.4 — inspect the event log so far. Notice the constructor's
    "Transfer from 0x000... to Alice 1000" — that's the on-chain birth
    certificate of every WOOD token in existence.
    """)
    return


@app.cell
def _(wood, world):
    print("WOOD events:")
    for _ev in world[wood].storage["__impl__"].events:
        print(" ", _ev)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Re-read what just happened end-to-end:

    * The WOOD contract is the **only** place WOOD ownership exists. Alice's
      underlying ETH wallet has no awareness of WOOD. If we deleted this
      contract, all WOOD would vanish.
    * "Sending" 200 WOOD was two arithmetic updates inside a dict. No object
      travels.
    * If Alice deployed a *second* WOOD-named contract, it would be a
      different token at a different address. Wallets identify "the real WOOD"
      by trusting a specific address.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 10. Approvals — the "permission slip"

    Real protocols (DEXes, lending pools, games) live in *their own contract*
    and need to **hold your tokens** on your behalf. But the WOOD contract
    only lets *you* move *your* balance. Carol can't just take 50 WOOD from
    Alice.

    The standard ERC-20 workaround is a two-step dance:

    1. **Owner calls `approve(spender, amount)` on the token.** This records a
      permission slip: "spender may move up to `amount` of my tokens."
    2. **Spender calls `transferFrom(owner, recipient, amount)`.** The token
      checks the slip, decrements it, then moves the tokens.

    Step 10.1 — Alice approves Bob to spend up to 300 WOOD. Then Bob spends 100:
    """)
    return


@app.cell
def _(ALICE, BOB, call, show_balances, wood):
    call(ALICE, wood, "approve", BOB, 300)
    print()
    print("allowance(Alice -> Bob) =", call(BOB, wood, "allowance", ALICE, BOB))

    # Now Bob "pulls" 100 WOOD from Alice to Carol.
    print()
    call(BOB, wood, "transfer_from", ALICE, "0xCCC...carol", 100)
    print()
    show_balances(wood, [ALICE, BOB, "0xCCC...carol"], label="after Bob pulled 100 from Alice")
    print("remaining allowance =", call(BOB, wood, "allowance", ALICE, BOB))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 10.2 — edge case. Bob tries to spend more than his allowance:
    """)
    return


@app.cell
def _(ALICE, BOB, call, wood):
    try:
        call(BOB, wood, "transfer_from", ALICE, BOB, 9_999)
    except ValueError as _err:
        print()
        print(_err)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The allowance is the **whole** access model for "let someone else move my
    tokens." Wallets warn loudly about "infinite approvals" because granting
    `approve(spender, 2**256-1)` to a buggy contract lets it drain you forever.

    Important nuance: the *spender* doesn't have to be a human. It's usually a
    contract — like the Vault we'll build next.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 11. Putting it together — a `Vault` that "accepts deposits"

    A vault wants to hold tokens *for* you and credit you internally so you
    can withdraw later. The flow:

    1. You `approve(vault, n)` on the token.
    2. You call `vault.deposit(n)`. The vault, **acting as msg.sender**, calls
      `token.transfer_from(you, vault, n)`. The token checks the allowance,
      moves the balance, decrements the slip.
    3. The vault records `deposits[you] += n` in its own storage.

    Step 11 — the contract:
    """)
    return


@app.cell
def _(call):
    class Vault:
        """A toy protocol that holds one specific token and tracks deposits."""
        def __init__(self, token_addr: str):
            self.token = token_addr
            self.msg_sender = None
            self.address    = None
            self.storage    = None
            self.events     = []

        def __init__post__(self, deployer):
            self.storage["deposits"] = {}

        def deposit(self, amount: int):
            user = self.msg_sender
            # CRITICAL: when the vault calls the token, *the vault* is msg.sender.
            # That's why the approval has to be `Owner -> Vault`, not `Owner -> Owner`.
            call(self.address, self.token, "transfer_from", user, self.address, amount)
            d = self.storage["deposits"]
            d[user] = d.get(user, 0) + amount
            self.events.append(("Deposit", user, amount))

        def withdraw(self, amount: int):
            user = self.msg_sender
            d = self.storage["deposits"]
            if d.get(user, 0) < amount:
                raise ValueError(f"REVERT: {user} has no deposit of {amount}")
            d[user] -= amount
            # Vault pays itself out by calling the token's plain `transfer`.
            call(self.address, self.token, "transfer", user, amount)
            self.events.append(("Withdraw", user, amount))

        def deposit_of(self, user: str) -> int:
            return self.storage["deposits"].get(user, 0)

    Vault
    return (Vault,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 11.1 — edge case first. What happens if Alice forgets to approve?
    """)
    return


@app.cell
def _(ALICE, Vault, call, deploy, wood):
    vault = deploy(ALICE, Vault(token_addr=wood))
    try:
        call(ALICE, vault, "deposit", 50)
    except ValueError as _err:
        print()
        print("Deposit failed — expected:")
        print(_err)
    return (vault,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The vault tried to pull tokens it had no permission for. The token's
    `transfer_from` reverted, and that revert propagated up through the
    vault's `deposit`. **Reverts bubble.** Nothing partial commits.

    Step 11.2 — do it properly. Approve, then deposit. Watch the indented
    trace — you'll see the Vault calling back into WOOD:
    """)
    return


@app.cell
def _(ALICE, BOB, call, show_balances, vault, wood):
    # Alice gives Vault a 300 WOOD allowance, then deposits 250.
    call(ALICE, wood, "approve", vault, 300)
    print()
    call(ALICE, vault, "deposit", 250)
    print()
    show_balances(wood, [ALICE, BOB, vault], label="after Alice deposited 250")
    print("vault.deposit_of(Alice) =", call(ALICE, vault, "deposit_of", ALICE))
    print("remaining allowance     =", call(ALICE, wood, "allowance", ALICE, vault))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Look at the trace above. The vault's `deposit` made a *nested* call into
    WOOD's `transfer_from`. The token sees `msg.sender = vault.address`. That
    is exactly why Alice approved the *vault*, not herself.

    Step 11.3 — Alice withdraws 100 WOOD:
    """)
    return


@app.cell
def _(ALICE, BOB, call, show_balances, vault, wood):
    call(ALICE, vault, "withdraw", 100)
    print()
    show_balances(wood, [ALICE, BOB, vault], label="after Alice withdrew 100")
    print("vault.deposit_of(Alice) =", call(ALICE, vault, "deposit_of", ALICE))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 11.4 — multiple users. Carol deposits 30, then over-withdraws:
    """)
    return


@app.cell
def _(ALICE, BOB, CAROL, call, show_balances, vault, wood):
    # First mint Carol some WOOD by having Alice send her some.
    call(ALICE, wood, "transfer", CAROL, 80)
    call(CAROL, wood, "approve", vault, 30)
    call(CAROL, vault, "deposit", 30)
    print()
    show_balances(wood, [ALICE, BOB, CAROL, vault], label="after Carol deposited 30")
    print("vault.deposit_of(Carol) =", call(CAROL, vault, "deposit_of", CAROL))

    try:
        call(CAROL, vault, "withdraw", 9_999)
    except ValueError as _err:
        print()
        print("Over-withdraw fails:", _err)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The key insight from this whole section:

    > **Tokens never leave their home contract.** They just move between rows
    > inside the token's `balances` dict. The vault doesn't *store* WOOD; the
    > vault is itself a row inside WOOD's balances. The vault's own storage
    > only stores *who deposited how much*, so it knows what to return.

    Two contracts, two storage spaces, one user-visible "deposit." That's the
    pattern behind every yield aggregator, AMM, and staking pool you've ever
    seen.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 12. NFTs (ERC-721) — same idea, different mapping

    Fungible tokens store `address -> count`. Non-fungible tokens store
    `tokenId -> address`. Each numbered item has exactly one owner slot.

    | Token kind | Mapping              | "Are units interchangeable?" |
    |------------|----------------------|------------------------------|
    | ERC-20     | `address -> uint`    | yes — 1 WOOD == 1 WOOD       |
    | ERC-721    | `tokenId -> address` | no — token #7 ≠ token #8     |

    We also keep `token_uri[tokenId]` so each NFT can point at metadata
    (image, JSON). That's why every NFT contract takes IPFS URLs.
    """)
    return


@app.cell
def _():
    class ERC721:
        def __init__(self, name: str, symbol: str):
            self.name, self.symbol = name, symbol
            self.msg_sender = None
            self.address    = None
            self.storage    = None
            self.events     = []

        def __init__post__(self, deployer):
            self.storage["owners"]    = {}      # tokenId -> address
            self.storage["token_uri"] = {}      # tokenId -> str
            self.storage["minter"]    = deployer
            self.storage["next_id"]   = 1

        def mint(self, to: str, uri: str) -> int:
            if self.msg_sender != self.storage["minter"]:
                raise PermissionError("REVERT: only minter can mint")
            tid = self.storage["next_id"]
            self.storage["next_id"] += 1
            self.storage["owners"][tid]    = to
            self.storage["token_uri"][tid] = uri
            self.events.append(("Transfer", "0x000...zero", to, tid))
            return tid

        def owner_of(self, tid: int) -> str:
            if tid not in self.storage["owners"]:
                raise KeyError(f"REVERT: token {tid} does not exist")
            return self.storage["owners"][tid]

        def token_uri(self, tid: int) -> str:
            return self.storage["token_uri"][tid]

        def transfer(self, to: str, tid: int) -> None:
            if self.storage["owners"].get(tid) != self.msg_sender:
                raise PermissionError(f"REVERT: token {tid} is not yours")
            self.storage["owners"][tid] = to
            self.events.append(("Transfer", self.msg_sender, to, tid))

    ERC721
    return (ERC721,)


@app.cell
def _(ALICE, BOB, ERC721, call, deploy, world):
    nft = deploy(ALICE, ERC721("CraftItems", "CRAFT"))

    sword_id  = call(ALICE, nft, "mint", ALICE, "ipfs://sword.json")
    shield_id = call(ALICE, nft, "mint", BOB,   "ipfs://shield.json")
    potion_id = call(ALICE, nft, "mint", ALICE, "ipfs://potion.json")

    print()
    print("After minting:")
    print("  owners =", world[nft].storage["owners"])
    return nft, shield_id, sword_id


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 12.1 — Alice transfers the sword to Bob; the owners map updates:
    """)
    return


@app.cell
def _(ALICE, BOB, call, nft, sword_id, world):
    call(ALICE, nft, "transfer", BOB, sword_id)
    print()
    print("owners now =", world[nft].storage["owners"])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Step 12.2 — edge cases. Carol tries to take the shield she doesn't own;
    and Bob tries to mint without permission.
    """)
    return


@app.cell
def _(BOB, CAROL, call, nft, shield_id):
    try:
        call(CAROL, nft, "transfer", CAROL, shield_id)
    except PermissionError as _err:
        print()
        print(_err)

    try:
        call(BOB, nft, "mint", BOB, "ipfs://fake.json")
    except PermissionError as _err:
        print()
        print(_err)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    "Uniqueness" of an NFT is always scoped by **(contract address, tokenId)**.
    Token #1 on this CRAFT contract has nothing to do with token #1 on any
    other contract — they're unrelated rows in unrelated dicts.

    The ERC-721 spec also has `approve` / `transferFrom` analogues for letting
    marketplaces move your NFTs (`OpenSea` lists an item by getting an
    approval, then `transferFrom`-ing on sale). Same pattern as ERC-20; we
    skip them for brevity.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 13. Final dump — see the entire world

    One last `show_world()` so you can confirm every contract, every balance
    slot, and every storage variable that exists in our universe:
    """)
    return


@app.cell
def _(show_world):
    print(show_world())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 14. Recap — what is a token, really?

    | Question                          | Answer                                                                 |
    |-----------------------------------|------------------------------------------------------------------------|
    | What is a contract?               | An address with non-empty `code` and its own `storage`.                |
    | What is a token?                  | A number (or owner record) inside a contract's storage, keyed by address. |
    | How do you "create" a token?      | Deploy one contract exposing the ERC-20 (or 721) function names.       |
    | Where do the tokens "live"?       | Only inside that one contract. Nowhere else.                           |
    | What makes a token unique?        | The contract address. Two contracts named "WOOD" are different tokens. |
    | What makes an NFT unit unique?    | `(contract address, tokenId)` — that ID has one owner slot in storage. |
    | How does "transfer" work?         | Two arithmetic updates + a Transfer event. No object moves anywhere.   |
    | How does "deposit into X" work?   | `approve(X, n)` on the token, then `X.deposit(n)` calls `transferFrom`. |
    | Where does access control come from? | The contract checking `msg.sender` against stored addresses (owner, minter, allowances). |
    | What's a revert?                  | The contract `raise`s; the whole call's state changes are rolled back. |
    | Why events?                       | Wallets and explorers index the log to render balances/history.        |

    ### Things we glossed over (but you've earned the vocabulary for)

    * **Gas.** Every storage write costs gas, paid by the caller in ETH.
      That's why production contracts pack storage tightly.
    * **Bytecode.** A real contract's `code` is EVM bytecode from `solc`.
      [NB09](09_toy_evm.py) implements an interpreter that actually runs some.
    * **Reentrancy.** Contract A calls B which calls back into A mid-execution.
      Famous source of hacks (The DAO, 2016). Mitigated by checks-effects-
      interactions and reentrancy guards.
    * **Upgradeability.** Contract code is immutable; "upgradeable" contracts
      use a proxy pattern that forwards calls to a swappable implementation.
    * **Real ERC-20/721 implementations.** OpenZeppelin's contracts have the
      exact shape we built, plus the safety checks and gas optimisations.

    ### Where to look next

    * Re-read [NB09 — Toy EVM](09_toy_evm.py) now that you know *why* you care
      about `SSTORE` / `SLOAD` / `CALL` — they implement everything above.
    * Read an actual OpenZeppelin ERC-20 source. Almost every line will be
      familiar.
    """)
    return


if __name__ == "__main__":
    app.run()
