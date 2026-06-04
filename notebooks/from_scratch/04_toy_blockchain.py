import marimo

__generated_with = "0.23.8"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # NB04 — Toy Blockchain (Single Node)

    We now have all the cryptographic primitives we need — hashing, signing,
    address derivation — from NB01/NB02.  In this notebook we assemble them
    into a **minimum viable blockchain**: an in-process, single-node chain that
    enforces real signatures, nonces, and balance accounting, and chains blocks
    together via parent-hash linking.

    **What we KEEP (because they are fundamental):**
    - Recoverable ECDSA signatures — every transaction is authenticated
    - Sender nonces — replay protection; you cannot send the same transaction twice
    - Balance accounting — you cannot spend what you do not have
    - Parent-hash linking — each block cryptographically commits to the previous one

    **What we CUT (to keep this notebook ~300 lines):**
    - Proof-of-stake / proof-of-work consensus (no networking until NB05/NB06)
    - Gas metering (NB07 adds that)
    - Merkle root over state trie (NB08 adds that)
    - Merkle root over transactions — we use a simple concatenation of tx hashes in
      the block header for now; NB08 replaces this with the full Merkle tree

    Prerequisites: NB01 (keys), NB02 (signing).  All crypto comes from `_lib`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2 — `Account` dataclass and `State`

    A blockchain's **world state** is a mapping from address to account.  Each
    account records two numbers: `balance` (how many tokens it holds) and `nonce`
    (how many transactions it has sent).  The nonce starts at 0 and increments by 1
    each time a transaction from this account is applied.

    We represent state as a plain Python `dict` — the key is a lowercase
    `0x`-prefixed address string, the value is an `Account`.  `get_account` returns
    the existing entry or creates a zero-balance/zero-nonce account on first access.
    """)
    return


@app.cell
def _():
    from dataclasses import dataclass, field

    @dataclass
    class Account:
        balance: int = 0
        nonce: int = 0

    # State is a dict from 0x-prefixed lowercase address string -> Account
    State = dict  # type alias

    def get_account(state: State, addr: str) -> Account:
        if addr not in state:
            state[addr] = Account()
        return state[addr]

    print("Account:", Account())
    print("get_account auto-creates:", get_account({}, "0x" + "ab" * 20))
    return Account, State, dataclass, field, get_account


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3 — `Tx` dataclass and `make_tx` helper

    A transaction carries:

    | Field | Meaning |
    |-------|---------|
    | `sender` | 0x-prefixed address of the signing account |
    | `to` | 0x-prefixed recipient address |
    | `value` | Token amount to transfer |
    | `nonce` | Sender's current nonce (replay protection) |
    | `r`, `s`, `y_parity` | ECDSA recoverable signature components |

    `unsigned_bytes()` RLP-encodes the four payload fields — this is the canonical
    byte representation that gets hashed and signed.  `hash()` hashes the full
    transaction (payload + signature) so blocks can reference transactions by hash.

    `make_tx(priv, to, value, nonce)` is the high-level helper: it computes the
    sighash, signs it, and fills in `r`, `s`, `y_parity`.
    """)
    return


@app.cell
def _(dataclass, field):
    import sys, os
    # ensure _lib is importable from the notebook's directory
    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)

    from _lib.rlp_min import rlp_encode
    from _lib.keccak import keccak256
    from _lib.ecdsa import sign_digest, recover_address, priv_to_address

    @dataclass
    class Tx:
        sender: str
        to: str
        value: int
        nonce: int
        r: bytes = field(default=b"")
        s: bytes = field(default=b"")
        y_parity: int = 0

        def unsigned_bytes(self) -> bytes:
            return rlp_encode([
                bytes.fromhex(self.sender.removeprefix("0x")),
                bytes.fromhex(self.to.removeprefix("0x")),
                self.value,
                self.nonce,
            ])

        def hash(self) -> bytes:
            return keccak256(self.unsigned_bytes() + self.r + self.s + bytes([self.y_parity]))


    def make_tx(priv: bytes, to: str, value: int, nonce: int) -> Tx:
        sender = priv_to_address(priv)
        t = Tx(sender, to, value, nonce)
        digest = keccak256(t.unsigned_bytes())
        t.r, t.s, t.y_parity = sign_digest(priv, digest)
        return t

    print("Tx and make_tx defined")
    return Tx, keccak256, make_tx, priv_to_address, recover_address, rlp_encode


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4 — `apply_tx(state, tx)`

    `apply_tx` is the heart of the chain.  It takes the current world state and one
    transaction, validates everything, then mutates state.

    The four checks, in order:

    1. **Signature** — recover the sender address from the signature and the
       unsigned bytes.  If it does not match `tx.sender`, someone tampered with the
       transaction or lied about the sender.
    2. **Nonce** — the transaction's nonce must equal the sender's current nonce
       exactly.  Too low means a replay; too high means a gap (out-of-order).
    3. **Balance** — the sender must have at least `tx.value` to transfer.
    4. **Apply** — deduct from sender, credit recipient, increment sender nonce.

    If any check fails, `apply_tx` raises `AssertionError` and leaves state
    unchanged.  The `Chain.propose` method wraps calls to `apply_tx` in a
    snapshot/rollback so the entire block is atomic.
    """)
    return


@app.cell
def _(State, Tx, get_account, keccak256, recover_address):
    def apply_tx(state: State, tx: Tx) -> None:
        # 1. Verify signature recovers the claimed sender
        digest = keccak256(tx.unsigned_bytes())
        recovered = recover_address(digest, tx.r, tx.s, tx.y_parity)
        assert recovered == tx.sender, f"bad signature: recovered {recovered}, claims {tx.sender}"
        # 2. Nonce check
        sender = get_account(state, tx.sender)
        assert tx.nonce == sender.nonce, f"bad nonce: got {tx.nonce}, want {sender.nonce}"
        # 3. Balance check
        assert sender.balance >= tx.value, f"insufficient: have {sender.balance}, need {tx.value}"
        # 4. Apply
        sender.balance -= tx.value
        get_account(state, tx.to).balance += tx.value
        sender.nonce += 1

    print("apply_tx defined")
    return (apply_tx,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 5 — `Block` dataclass

    A block binds together:

    | Field | Meaning |
    |-------|---------|
    | `number` | Block height (genesis = 0) |
    | `parent_hash` | Hash of the previous block's header |
    | `txs` | Ordered list of transactions |
    | `timestamp` | Unix timestamp (integer seconds) |

    `header_bytes()` RLP-encodes those four fields into a canonical byte string.
    For the "tx commitment" we concatenate all transaction hashes — simple and good
    enough for this notebook.  NB08 replaces this concatenation with a proper
    Merkle root so you can produce compact proofs that a single tx is in the block
    without revealing the full list.

    `hash()` is keccak256 of `header_bytes()` — this is what the next block will
    store as `parent_hash`, forming the chain.
    """)
    return


@app.cell
def _(dataclass, keccak256, rlp_encode):
    @dataclass
    class Block:
        number: int
        parent_hash: bytes
        txs: list
        timestamp: int

        def header_bytes(self) -> bytes:
            # Simple tx commitment: concatenate all tx hashes.
            # NB08 replaces this with a Merkle root.
            tx_hashes_concat = b"".join(t.hash() for t in self.txs)
            return rlp_encode([
                self.number,
                self.parent_hash,
                self.timestamp,
                tx_hashes_concat,
            ])

        def hash(self) -> bytes:
            return keccak256(self.header_bytes())

    print("Block defined")
    return (Block,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 6 — `Chain` class

    `Chain` wraps the growing list of blocks and the current world state.

    Key points:

    - The genesis block (block 0) carries an empty tx list and a synthetic
      `parent_hash` of 32 zero bytes — there is no block before it.
    - `propose(txs)` applies the transaction list to the state **atomically**:
      it snapshots the state via `copy.deepcopy` before attempting any tx.
      If even one tx raises an `AssertionError`, the whole block is rolled back
      and the exception propagates.  The chain either advances cleanly or not at
      all — there is no partial-block state.
    - On success, a new `Block` is constructed, appended to `self.blocks`, and
      returned.

    The entire chain is therefore just a **sequence of state transitions**,
    each cryptographically tied to the previous block by `parent_hash`.
    """)
    return


@app.cell
def _(Block, State, apply_tx):
    import time
    import copy

    class Chain:
        def __init__(self, genesis_state: State):
            self.state = genesis_state
            genesis = Block(0, b"\x00" * 32, [], int(time.time()))
            self.blocks = [genesis]

        @property
        def head(self) -> Block:
            return self.blocks[-1]

        def propose(self, txs: list) -> Block:
            # Snapshot state — if any tx fails we roll back to this snapshot.
            # We catch both AssertionError (validation failure) and ValueError
            # (e.g. coincurve cannot deserialise a corrupted signature).
            snap = copy.deepcopy(self.state)
            try:
                for t in txs:
                    apply_tx(self.state, t)
            except (AssertionError, ValueError):
                self.state = snap
                raise
            blk = Block(self.head.number + 1, self.head.hash(), txs, int(time.time()))
            self.blocks.append(blk)
            return blk

    print("Chain defined")
    return (Chain,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 7 — Demo: Alice pays Bob

    We create two wallets, fund Alice in the genesis state, then build and propose
    a single-transaction block transferring 250 tokens from Alice to Bob.
    """)
    return


@app.cell
def _(Account, Chain, make_tx, priv_to_address):
    from _lib.ecdsa import gen_private_key

    alice_priv = gen_private_key()
    bob_priv   = gen_private_key()
    alice = priv_to_address(alice_priv)
    bob   = priv_to_address(bob_priv)
    print("alice:", alice)
    print("bob:  ", bob)

    # Fund alice in genesis state
    genesis_state = {alice: Account(balance=1000, nonce=0)}
    chain = Chain(genesis_state)

    tx1 = make_tx(alice_priv, bob, 250, nonce=0)
    blk = chain.propose([tx1])
    print(f"block #{blk.number} hash: {blk.hash().hex()[:16]}...")
    print(f"  alice: balance={chain.state[alice].balance} nonce={chain.state[alice].nonce}")
    print(f"  bob:   balance={chain.state[bob].balance} nonce={chain.state[bob].nonce}")
    return alice, alice_priv, bob, chain


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 8 — Validation: reject bad transactions

    Three separate cells, each probing one of the three guard checks in `apply_tx`.
    After each failure the chain state must remain unchanged — this is the
    snapshot/rollback guarantee of `Chain.propose`.
    """)
    return


@app.cell
def _(alice_priv, bob, chain, make_tx):
    # Wrong nonce (alice's nonce is now 1 after the successful tx, but we pass 99)
    try:
        bad = make_tx(alice_priv, bob, 10, nonce=99)
        chain.propose([bad])
    except AssertionError as e:
        print("REJECTED (wrong nonce):", e)
    return


@app.cell
def _(alice, alice_priv, bob, chain, make_tx):
    # Insufficient balance (alice has 750, trying to send 10 000)
    try:
        huge = make_tx(alice_priv, bob, 10_000, nonce=chain.state[alice].nonce)
        chain.propose([huge])
    except AssertionError as e:
        print("REJECTED (insufficient balance):", e)
    return


@app.cell
def _(alice, alice_priv, bob, chain, make_tx):
    # Tampered signature — flip one bit of r.
    # coincurve raises ValueError when the corrupted bytes cannot be deserialized
    # as a valid secp256k1 curve point; apply_tx lets that propagate.
    # We catch both ValueError and AssertionError: the former means recovery failed
    # outright; the latter means recovery produced a different (wrong) address.
    ok = make_tx(alice_priv, bob, 5, nonce=chain.state[alice].nonce)
    ok.r = bytes([ok.r[0] ^ 0x01]) + ok.r[1:]   # corrupt r
    try:
        chain.propose([ok])
    except (AssertionError, ValueError) as e:
        print("REJECTED (bad sig):", type(e).__name__, e)
    return


@app.cell
def _(alice, chain):
    # Confirm chain state is exactly where we left it after the one good block
    print(f"post-rejection alice balance: {chain.state[alice].balance}  (still 750)")
    print(f"post-rejection chain length:   {len(chain.blocks)}  (still 2 -- genesis + the one good block)")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 9 — `verify_chain` exercise

    An independent auditor can verify the entire chain by:
    1. Starting from a known genesis state
    2. Walking every block from genesis to head in order
    3. Re-applying every transaction
    4. Asserting parent-hash links are unbroken
    5. Comparing the reconstructed final state to the chain's current state

    If anything was tampered with — a transaction modified, a block removed, a hash
    recomputed incorrectly — at least one assertion will fail.
    """)
    return


@app.cell
def _(Account, Chain, State, alice, apply_tx, chain):
    def verify_chain(chain: Chain) -> None:
        # Start from the same genesis state that was passed to Chain()
        state: State = {}
        state[alice] = Account(balance=1000, nonce=0)

        prev_hash = b"\x00" * 32
        for i, blk in enumerate(chain.blocks):
            assert blk.parent_hash == prev_hash, f"broken link at block {i}"
            if i > 0:
                for t in blk.txs:
                    apply_tx(state, t)
            prev_hash = blk.hash()

        # Reconstructed state must match chain.state exactly
        for addr, acct in chain.state.items():
            assert state.get(addr, Account()) == acct, f"state mismatch for {addr}"

        print("chain verified -- every block re-applied cleanly, state matches")

    verify_chain(chain)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 10 — Export everything to `_lib/chain.py`

    NB05, NB06, and later notebooks will `from _lib.chain import Chain, make_tx, ...`
    rather than redefining these classes.  We write the module out now using
    `%%writefile`.

    Note the relative imports inside the file (`from .keccak import ...`) — these
    are package-style imports suitable for use when `_lib` is a package (it has an
    `__init__.py`).  The notebook uses `sys.path` insertion instead, which is why
    the imports look different at the top of this notebook.
    """)
    return


@app.cell
def _(alice, alice_priv, bob):
    import importlib
    import _lib.chain as _c
    importlib.reload(_c)
    from _lib.chain import Chain as LibChain, Account as LibAccount, make_tx as lib_make_tx

    lc = LibChain({alice: LibAccount(balance=500)})
    lc.propose([lib_make_tx(alice_priv, bob, 100, nonce=0)])
    print("lib chain head:", lc.head.hash().hex()[:16], "alice balance:", lc.state[alice].balance)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Summary

    | Concept | One-line takeaway |
    |---------|-------------------|
    | `Account` | Balance + nonce.  The entire world state is `dict[address, Account]` |
    | `apply_tx` | Four guards: sig check, nonce check, balance check, then mutate |
    | `Block` | Header = RLP(number, parent_hash, timestamp, tx_hashes_concat) |
    | `Chain` | Sequential state transitions tied together by parent_hash |
    | Atomic block | Snapshot/rollback: either all txs in a block succeed or none do |
    | `verify_chain` | Re-walk from genesis; any tampering breaks a hash or balance assertion |

    Next: NB05 — peer-to-peer networking and block propagation.
    """)
    return


if __name__ == "__main__":
    app.run()
