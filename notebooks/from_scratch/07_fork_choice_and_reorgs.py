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
    # NB07 — Fork Choice & Reorgs

    Extend NB04's chain and NB06's P2P node to support competing chains,
    the longest-chain rule, and live reorg debugging.

    **Dependencies:** `_lib/chain.py` (NB04), `_lib/peer.py` (NB06),
    `_lib/rlp_min.py`, `_lib/keccak.py`, `_lib/ecdsa.py`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. What is a fork?

    Two nodes can each build a different block at the same height (network
    latency, validator disagreement, partition). Both look valid locally.
    The protocol must pick a winner **deterministically**.

    Pre-Merge Ethereum used the **longest-chain rule** (Nakamoto consensus):
    the chain with the most blocks wins. Post-Merge Ethereum uses
    **LMD-GHOST + Casper FFG**: validators vote on chain tips with weighted
    attestations, and finality is checkpoint-based — more than two thirds of
    stake must vote before a checkpoint is locked irreversibly (with slashing
    for equivocators).

    We implement the simple longest-chain rule and watch a **reorg** happen
    live: one node discards its tip and adopts a competing (longer) chain.
    The structural primitive — blocks forming a parent-hash tree, with a
    selectable tip — is the same in both schemes; the consensus rule is just
    a function over that tree.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Extended protocol — new message types

    NB06 established:

    | Type | Code | Payload |
    |------|------|---------|
    | HELLO | `0x01` | `node_id (8 bytes) \|\| port (2 bytes BE)` |
    | ANNOUNCE_TX | `0x04` | `tx_hash (32 bytes)` |
    | GET_TX | `0x05` | `tx_hash (32 bytes)` |
    | TX | `0x06` | `tx_bytes (arbitrary)` |

    NB07 adds four block-sync messages:

    | Type | Code | Payload |
    |------|------|---------|
    | GET_HEAD | `0x10` | (none) |
    | HEAD | `0x11` | `number(4 BE) \|\| hash(32)` |
    | GET_BLOCK | `0x12` | `number(4 BE)` |
    | BLOCK | `0x13` | `block_bytes (RLP-encoded)` |

    These four messages form a minimal **sync sub-protocol**: ask a peer for
    its best head, walk back to find the common ancestor, then download and
    replay the peer's branch.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Block + Tx serialization (extend `_lib/chain.py`)

    We need to ship blocks over TCP, so every `Block` and `Tx` must know how
    to serialize itself to bytes and reconstruct from bytes.

    We re-use the `rlp` package (already installed) for decoding — its
    `rlp.decode` returns raw `bytes` lists that we can interpret field-by-field.
    Our existing `rlp_encode` from `_lib/rlp_min.py` handles encoding.

    We also add `replay_chain_from_genesis(blocks, genesis_state)` which is
    required by the reorg path: when we rewind to a common ancestor we must
    rebuild the state from scratch rather than un-apply transactions (which
    would require inverse operations).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Verify round-trip serialization

    Build a block with a real signed transaction, serialize it, deserialize it,
    and confirm that `Block.from_bytes(blk.to_bytes()).hash() == blk.hash()`.
    This proves the wire format preserves all header fields exactly.
    """)
    return


@app.cell
def _():
    import importlib, sys, os
    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    import _lib.chain
    importlib.reload(_lib.chain)
    from _lib.chain import Account, Tx, Block, Chain, apply_tx, make_tx, get_account
    from _lib.ecdsa import gen_private_key, priv_to_address
    alice_priv = gen_private_key()
    alice = priv_to_address(alice_priv)
    _bob_priv = gen_private_key()
    # Build a signed transaction
    bob = priv_to_address(_bob_priv)
    tx = make_tx(alice_priv, bob, 42, nonce=0)
    _tx2 = Tx.from_bytes(tx.to_bytes())
    assert _tx2.sender == tx.sender, f'sender mismatch: {_tx2.sender!r} != {tx.sender!r}'
    assert _tx2.to == tx.to
    assert _tx2.value == tx.value
    assert _tx2.nonce == tx.nonce
    # Verify Tx round-trip
    assert _tx2.r == tx.r
    assert _tx2.s == tx.s
    assert _tx2.y_parity == tx.y_parity
    print('Tx round-trip OK')
    genesis = Block(0, b'\x00' * 32, [], 1700000000)
    blk = Block(1, genesis.hash(), [tx], 1700000001)
    blk2 = Block.from_bytes(blk.to_bytes())
    assert blk2.hash() == blk.hash(), f'hash mismatch after round-trip:\n  original  {blk.hash().hex()}\n  roundtrip {blk2.hash().hex()}'
    print(f'Block round-trip OK  hash={blk.hash().hex()[:16]}...')
    # Build a Block wrapping that tx
    # Verify Block round-trip
    print(f'  number={blk2.number}  txs={len(blk2.txs)}  parent={blk2.parent_hash.hex()[:8]}')
    return (
        Account,
        Block,
        Chain,
        gen_private_key,
        get_account,
        importlib,
        make_tx,
        os,
        priv_to_address,
        sys,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Extend `_lib/peer.py` — chain integration

    Three changes to `Node`:

    1. **Optional `chain` / `genesis_state` arguments** — so a node can hold
       a live chain and respond to block-sync messages.
    2. **`_peer_loop` handles `GET_HEAD`, `GET_BLOCK`, and `BLOCK`** —
       the server side of the sync protocol.
    3. **`_handle_block`, `try_sync`, `gossip_block` methods** —
       the client side: receive a pushed block, pull a peer's chain, broadcast.

    **Socket isolation for sync requests:** `try_sync` opens a *fresh*
    TCP connection to the peer rather than reusing the shared gossip socket.
    This avoids a race between the background `_peer_loop` reader and the
    synchronous request/response pattern that `try_sync` needs.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. Demo setup

    Two helpers: `fresh_chain()` returns a new chain seeded from the same
    genesis state, and `fresh_node(port)` bundles chain + node together.
    Both alice and bob are deterministic so every run starts from the same
    initial balances.
    """)
    return


@app.cell
def _(Account, Chain, gen_private_key, importlib, os, priv_to_address, sys):
    import copy, time
    _HERE2 = os.path.dirname(os.path.abspath(__file__))
    if _HERE2 not in sys.path:
        sys.path.insert(0, _HERE2)
    import _lib.chain, _lib.peer
    importlib.reload(_lib.chain)
    importlib.reload(_lib.peer)
    from _lib.peer import Node
    alice_priv_1 = gen_private_key()
    alice_1 = priv_to_address(alice_priv_1)
    _bob_priv = gen_private_key()
    bob_1 = priv_to_address(_bob_priv)
    print('alice:', alice_1)
    print('bob:  ', bob_1)
    GENESIS_STATE = {alice_1: Account(balance=10000, nonce=0)}

    def fresh_chain():
        return Chain(copy.deepcopy(GENESIS_STATE))

    def fresh_node(port):
        return Node(port, chain=fresh_chain(), genesis_state=GENESIS_STATE)

    return alice_1, alice_priv_1, bob_1, fresh_node, time


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. Naive sync: two nodes, no fork

    Node 1 proposes a block. Node 2 starts empty (only genesis). When they
    connect, we call `n2.try_sync(n1.port)` — node 2 detects that node 1 is
    one block ahead, fetches it, and both heads converge.
    """)
    return


@app.cell
def _(alice_priv_1, bob_1, fresh_node, make_tx, time):
    n1 = fresh_node(5601)
    n2 = fresh_node(5602)
    n1.start()
    n2.start()
    time.sleep(0.2)
    tx_a = make_tx(alice_priv_1, bob_1, 100, nonce=0)
    blk1 = n1.chain.propose([tx_a])
    print(f'node 1 head: #{n1.chain.head.number} {n1.chain.head.hash().hex()[:8]}')
    # Connect the nodes (gossip channel -- separate from the sync socket)
    n1.connect('127.0.0.1', n2.port)
    time.sleep(0.2)
    n2.try_sync(n1.port)
    # Explicit sync: node 2 asks node 1 for its head via a fresh socket
    print(f'node 2 head: #{n2.chain.head.number} {n2.chain.head.hash().hex()[:8]}')
    assert n1.chain.head.hash() == n2.chain.head.hash(), f'heads differ: n1={n1.chain.head.hash().hex()[:8]} n2={n2.chain.head.hash().hex()[:8]}'
    print('nodes agree on head')
    n1.stop()
    n2.stop()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8. `dump_chain` helper

    A quick ASCII view of a node's chain, used to make the reorg visible.
    """)
    return


@app.function
def dump_chain(label, node):
    print(f'\n{label} (head = #{node.chain.head.number}):')
    for b in node.chain.blocks:
        print(f'  #{b.number}  hash={b.hash().hex()[:8]}'
              f'  parent={b.parent_hash.hex()[:8]}  txs={len(b.txs)}')


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 9. Cause a fork

    Both nodes are isolated (not yet connected). Each proposes its own block
    at height 1, but with **different transactions**, so the blocks have
    different hashes — a real fork.

    Then node 2 extends its chain to height 2 with a second block.
    At this point:

    * Node 1: height 1 (fork-A tip)
    * Node 2: height 2 (fork-B tip, longer)
    """)
    return


@app.cell
def _(alice_priv_1, bob_1, fresh_node, make_tx, time):
    n1_1 = fresh_node(5611)
    n2_1 = fresh_node(5612)
    n1_1.start()
    n2_1.start()
    time.sleep(0.2)
    tx1 = make_tx(alice_priv_1, bob_1, 100, nonce=0)
    _tx2 = make_tx(alice_priv_1, bob_1, 200, nonce=0)
    n1_1.chain.propose([tx1])
    n2_1.chain.propose([_tx2])
    dump_chain('BEFORE CONNECT -- node 1', n1_1)
    dump_chain('BEFORE CONNECT -- node 2', n2_1)
    tx3 = make_tx(alice_priv_1, bob_1, 50, nonce=1)
    n2_1.chain.propose([tx3])
    dump_chain('AFTER node 2 extends -- node 2', n2_1)
    print(f'\nnode 1 chain length: {len(n1_1.chain.blocks)}')
    print(f'node 2 chain length: {len(n2_1.chain.blocks)}')
    assert n1_1.chain.head.hash() != n2_1.chain.head.hash(), 'expected different heads'
    print('fork confirmed: heads differ')
    return n1_1, n2_1


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 10. Connect and trigger the reorg

    Node 1 calls `try_sync(n2.port)`. It detects node 2 is ahead by one
    block, walks back to find the common ancestor (genesis), unwinds its own
    fork-A tip, replays state from genesis through node 2's two blocks, and
    adopts node 2's head. This is a **reorg** — node 1's previously-canonical
    block is now orphaned.
    """)
    return


@app.cell
def _(alice_1, get_account, n1_1, n2_1):
    print('--- node 1 syncing from node 2 ---')
    result = n1_1.try_sync(n2_1.port)
    print(f'try_sync returned: {result}')
    dump_chain('AFTER REORG -- node 1', n1_1)
    dump_chain('AFTER REORG -- node 2', n2_1)
    assert n1_1.chain.head.hash() == n2_1.chain.head.hash(), f'reorg failed: n1={n1_1.chain.head.hash().hex()[:8]} n2={n2_1.chain.head.hash().hex()[:8]}'
    print('\nfork resolved by longest-chain rule')
    alice_bal = get_account(n1_1.chain.state, alice_1).balance
    assert alice_bal == 9750, f'expected alice 9750 after reorg, got {alice_bal}'
    print(f'alice balance after reorg: {alice_bal} (correct)')
    n1_1.stop()
    # State consistency: alice should have 10_000 - 200 - 50 = 9_750
    n2_1.stop()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 11. Debugging exercise — invalid-block defense

    What happens when a malicious peer sends a block with a tampered
    transaction signature? We flip one byte in the `r` field and call
    `_handle_block` directly. The node must **reject** the block and keep
    its head at genesis.

    This is the same defense used by real Ethereum clients: every transaction
    is signature-checked before the block is accepted.
    """)
    return


@app.cell
def _(Block, alice_priv_1, bob_1, fresh_node, make_tx, time):
    import time as _t
    n3 = fresh_node(5621)
    n3.start()
    time.sleep(0.1)
    good_tx = make_tx(alice_priv_1, bob_1, 10, nonce=0)
    good_tx.r = bytes([good_tx.r[0] ^ 1]) + good_tx.r[1:]
    evil_blk = Block(number=1, parent_hash=n3.chain.head.hash(), txs=[good_tx], timestamp=int(_t.time()))
    # Build a well-formed tx, then tamper with it BEFORE wrapping in a block
    n3._handle_block(evil_blk.to_bytes())
    print(f'node 3 head: #{n3.chain.head.number} (expected 0 -- tampered block rejected)')  # flip one bit in r
    assert n3.chain.head.number == 0, f'node accepted a tampered block! head is now #{n3.chain.head.number}'
    print('tampered-block defense confirmed')
    n3.stop()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 12. Why real Ethereum is harder

    We implemented the simplest possible fork-choice rule: most blocks wins.
    Real Ethereum post-Merge uses **LMD-GHOST** (Latest Message Driven,
    Greedy Heaviest Observed Sub-Tree) combined with **Casper FFG** finality:

    * **LMD-GHOST**: at each fork, pick the sub-tree with the most validator
      vote weight, not merely the most blocks. This makes it harder to attack
      with a minority of stake.
    * **Casper FFG**: every 32 slots a *checkpoint* is eligible for
      finalization. Once more than two thirds of stake has voted for a
      checkpoint's *source* and *target*, the checkpoint is **justified**;
      a subsequent supermajority finalizes it. Finalized blocks can never be
      reorged without *slashing* the violating validators (burning their stake).

    What we have built is the **structural spine** used by both schemes:

    * Blocks form a parent-hash tree (`parent_hash` field).
    * State is derived by replaying transactions from genesis.
    * A *fork-choice function* selects the canonical tip.
    * A *reorg* rewinds to a common ancestor and replays the winning branch.

    Swapping in LMD-GHOST means replacing the `peer_num > my_head_num` check
    in `try_sync` with a weighted-attestation comparison — everything else
    stays the same.
    """)
    return


if __name__ == "__main__":
    app.run()
