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
    # NB08 — Merkle-Patricia Trie

    Build a simplified MPT that hashes RLP-encoded nodes (closer to real
    Ethereum), produce a `stateRoot`, generate and verify inclusion proofs.

    **Dependencies:** `_lib/keccak.py`, `_lib/rlp_min.py`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Why a trie?

    Ethereum's state is a **map** from 20-byte addresses to account objects
    (balance, nonce, storage root, code hash). Three requirements drive the
    choice of data structure:

    1. **32-byte commitment** — the block header must commit to the *entire*
       state in 32 bytes so that other nodes can verify it without downloading
       the full state.

    2. **Inclusion proofs** — a light client must be able to prove
       "address X has balance Y at block N" using only the block header plus
       a small proof, without downloading the full state.

    3. **Efficient updates** — re-hashing the entire state on every block
       would be O(n) where n is the number of accounts. A trie makes it
       O(log n) because only the path from the changed leaf to the root
       needs to be rehashed.

    Ethereum uses a **Merkle-Patricia Trie (MPT)**: a radix-16 trie (each
    node has up to 16 children, one per hex nibble) where every node is
    hashed via `keccak256(rlp_encode(node))`.  The root hash of this
    structure is the `stateRoot` stored in every block header.
    """)
    return


@app.cell
def _():
    import sys, os

    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)

    from _lib.keccak import keccak256
    from _lib.rlp_min import rlp_encode
    print('imports OK')
    return keccak256, rlp_encode


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Binary Merkle tree warm-up

    Before building the full MPT, let's implement a **binary Merkle tree**
    over a list of leaves. This makes the core idea of hash-chaining and
    inclusion proofs easy to see.

    The proof for leaf at index `i` is the sequence of sibling hashes up
    the tree. A verifier can recompute the root by hashing the leaf together
    with each sibling in order, and compare to the known root.
    """)
    return


@app.cell
def _(keccak256):
    def merkle_root(leaves: list) -> bytes:
        if not leaves:
            return b'\x00' * 32
        layer = [keccak256(l) for l in leaves]
        while len(layer) > 1:
            if len(layer) % 2:
                layer.append(layer[-1])  # duplicate last to make even
            layer = [keccak256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
        return layer[0]

    def merkle_proof(leaves: list, idx: int) -> list:
        proof = []
        layer = [keccak256(l) for l in leaves]
        while len(layer) > 1:
            if len(layer) % 2:
                layer.append(layer[-1])
            sibling = idx ^ 1
            proof.append(layer[sibling])
            layer = [keccak256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
            idx //= 2
        return proof

    def verify_proof(leaf: bytes, idx: int, proof: list, root: bytes) -> bool:
        h = keccak256(leaf)
        for sibling in proof:
            if idx % 2 == 0:
                h = keccak256(h + sibling)
            else:
                h = keccak256(sibling + h)
            idx //= 2
        return h == _root
    leaves = [f'leaf-{i}'.encode() for i in range(8)]
    _root = merkle_root(leaves)
    print('root:', _root.hex())
    proof_3 = merkle_proof(leaves, 3)
    # Demo: 8 leaves
    print(f'proof for idx 3 has {len(proof_3)} sibling hashes')
    assert verify_proof(leaves[3], 3, proof_3, _root)
    print('proof for leaf 3 verifies')
    assert not verify_proof(b'tampered', 3, proof_3, _root)
    # Build proof for index 3, verify
    # Tamper: try to prove a different leaf at the same index
    print('tampered leaf fails verification')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Why MPT instead of a binary Merkle tree?

    > Binary Merkle trees commit to **lists**; Ethereum state is a **map**
    > (address -> account). We need a Merkle structure keyed by arbitrary bytes.
    > MPT = radix-16 trie + Merkle hashing at every node.

    Key differences:

    | Property | Binary Merkle | MPT |
    |----------|--------------|-----|
    | Key space | ordered integers | arbitrary bytes |
    | Lookup | O(log n) by index | O(key length) |
    | Proof size | O(log n) hashes | O(key length * 16) hashes |
    | Updates | O(log n) | O(key length) |

    In Ethereum, keys are 32-byte (256-bit) keccak hashes of addresses, so
    the depth is at most 64 nibbles. Each node stores up to 16 child hashes.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Simplified MPT — radix-16 trie

    First, a helper to split any byte string into hex nibbles (4-bit units).
    A 20-byte address becomes 40 nibbles; a 32-byte hash becomes 64 nibbles.
    """)
    return


@app.cell
def _():
    def nibbles(key: bytes) -> list:
        """Split bytes into a list of 4-bit nibbles (values 0..15)."""
        out = []
        for b in key:
            out.append(b >> 4)
            out.append(b & 0x0F)
        return out


    print(nibbles(b'\xab\xcd'))  # [10, 11, 12, 13]
    print(f'20-byte address -> {len(nibbles(bytes(20)))} nibbles')
    return (nibbles,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Trie node and trie classes

    We use a single uniform **branch-only** structure: each `Node` has
    a `children` dict (nibble -> Node) and an optional `value` bytes field.
    This is simpler than the full MPT which has leaf/extension/branch node
    types with HP-encoded path prefixes — we sacrifice wire efficiency for
    pedagogical clarity.
    """)
    return


@app.cell
def _(nibbles):
    class Node:
        __slots__ = ('children', 'value')

        def __init__(self):
            self.children: dict = {}  # int nibble -> Node
            self.value = None  # bytes | None

    class Trie:

        def __init__(self):
            self.root = Node()

        def put(self, key: bytes, value: bytes) -> None:
            n = self.root
            for nib in nibbles(key):
                n = n.children.setdefault(nib, Node())
            n.value = value

        def get(self, key: bytes):
            n = self.root
            for nib in nibbles(key):
                if nib not in n.children:
                    return None
                n = n.children[nib]
            return n.value
    _t = Trie()
    _t.put(b'hello', b'world')
    # Quick sanity check
    assert _t.get(b'hello') == b'world'
    assert _t.get(b'hell') is None
    print('Trie put/get OK')
    return Node, Trie


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Hash nodes via RLP

    The key improvement over a simple hash tree: each node is serialized
    with RLP before hashing. This is exactly what Ethereum does.

    For each node:
    1. Compute the hash of each child recursively.
    2. Build a list of 16 child hashes (empty bytes `b''` for absent children).
    3. Append the node's value (or `b''` for internal nodes).
    4. `rlp_encode([children_list, value])` then `keccak256` the result.
    """)
    return


@app.cell
def _(Node, keccak256, rlp_encode):
    def hash_node(node: Node) -> bytes:
        """Recursively hash a trie node using RLP encoding."""
        children = [
            hash_node(node.children[i]) if i in node.children else b''
            for i in range(16)
        ]
        encoded = rlp_encode([children, node.value or b''])
        return keccak256(encoded)


    print('hash_node defined')
    return (hash_node,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    > **Note on divergence from mainnet MPT:** Real Ethereum's MPT has four
    > node types (empty, leaf, extension, branch) with Hex-Prefix (HP) encoded
    > path prefixes. We have collapsed that to a single uniform branch-only
    > structure. Our hashes won't match mainnet, but the IDEA — RLP-encode each
    > node, keccak it, propagate hashes up — is correct and the proofs work.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. Build a state trie

    Simulate two accounts keyed by their 20-byte address. The `stateRoot`
    is `hash_node(trie.root)`. Mutating one account's balance must change
    the root.
    """)
    return


@app.cell
def _(Trie, hash_node):
    def addr_to_bytes(a: str) -> bytes:
        return bytes.fromhex(a.removeprefix('0x'))
    _t = Trie()
    _t.put(addr_to_bytes('0x' + 'a' * 40), 100 .to_bytes(8, 'big'))
    _t.put(addr_to_bytes('0x' + 'b' * 40), 250 .to_bytes(8, 'big'))
    root_v1 = hash_node(_t.root)
    print('stateRoot v1:', root_v1.hex())
    _t.put(addr_to_bytes('0x' + 'a' * 40), 101 .to_bytes(8, 'big'))
    root_v2 = hash_node(_t.root)
    print('stateRoot v2:', root_v2.hex())
    # Mutate one value -> root must change
    assert root_v1 != root_v2
    print('root changed after edit')
    return (addr_to_bytes,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. Inclusion proof

    An inclusion proof for key K consists of, at each level of the path
    from root to leaf, the 15 sibling hashes (the 16 slots minus the one
    slot we descend into). The verifier can reconstruct each node hash
    bottom-up and confirm it matches the known root.

    We use a simple, clearly-correct representation:
    - `prove()` returns a list of 16-element rows (one per nibble depth).
      In each row, the slot for the nibble we descended is `None`;
      all other slots are the child hashes at that depth.
    - `verify_inclusion()` fills in the `None` slot at each level with the
      hash reconstructed from the level below, then hashes the whole node
      and checks it matches the root.
    """)
    return


@app.cell
def _(Trie, hash_node, keccak256, nibbles, rlp_encode):
    def prove(trie: Trie, key: bytes) -> list:
        """Return one 16-element row per nibble depth along the path.

        Each row is a list of 16 entries: child hashes for the siblings,
        and None for the slot we descended into at that depth.
        """
        proof = []
        n = trie.root
        for nib in nibbles(key):
            row = [None if i == nib else hash_node(n.children[i]) if i in n.children else b'' for i in range(16)]
            proof.append(row)
            if nib not in n.children:
                break
            n = n.children[nib]
        return proof

    def verify_inclusion(key: bytes, value: bytes, proof: list, root: bytes) -> bool:
        """Reconstruct nodes bottom-up and confirm the root matches.

        The deepest node is a leaf with the claimed value and no children.
        Each parent is an internal node whose child slot is filled with the
        hash of the level below.
        """
        nibs = nibbles(key)
        if len(proof) != len(nibs):
            return False
        leaf_children = [b''] * 16
        cur_hash = keccak256(rlp_encode([leaf_children, value]))
        for depth in range(len(proof) - 1, -1, -1):
            row = proof[depth]
            nib = nibs[depth]
            if row[nib] is not None:
                return False  # The leaf node: no children, value = claimed value
            children = list(row)
            children[nib] = cur_hash
            node_value = b''
            cur_hash = keccak256(rlp_encode([children, node_value]))  # Walk from the deepest level UP to the root
        return cur_hash == _root
    print('prove and verify_inclusion defined')  # The slot for this nibble was marked None in prove(); fill it in  # copy so we don't mutate the proof  # Internal nodes (not the leaf) have empty value
    return prove, verify_inclusion


@app.cell
def _(Trie, addr_to_bytes, hash_node, nibbles, prove, verify_inclusion):
    # Build a trie with 6 accounts
    _t = Trie()
    keys = [addr_to_bytes('0x' + c * 40) for c in 'abcdef']
    for i, k in enumerate(keys):
        _t.put(k, (i * 100 + 1).to_bytes(8, 'big'))
    _root = hash_node(_t.root)
    print('stateRoot:', _root.hex())
    key_to_prove = keys[2]
    # Prove inclusion for key[2] (address cccc...)
    val = (2 * 100 + 1).to_bytes(8, 'big')
    p = prove(_t, key_to_prove)
    print(f'proof depth: {len(p)} levels (= {len(nibbles(key_to_prove))} nibbles)')
    ok = verify_inclusion(key_to_prove, val, p, _root)
    print(f'proof verifies for correct value: {ok}')
    assert ok
    bad = verify_inclusion(key_to_prove, b'\x00\x00\x00\x00\x00\x00\x00\xff', p, _root)
    print(f'proof for tampered value verifies: {bad}')
    assert not bad
    # Tamper: claim the wrong value
    print('tampered proof rejected')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8. Conceptual: wiring `stateRoot` into the toy chain

    In NB04's `Block.header_bytes()` we concatenated tx hashes into the
    header. Real Ethereum stores a **Merkle-Patricia root over the STATE**
    in the header (`stateRoot`). With the `Trie` you just built, you could:

    1. After each block applies its transactions, build a trie from
       `chain.state`: `trie.put(addr_to_bytes(addr), encode_account(acc))`
       for each account.
    2. Use `hash_node(trie.root)` as the `stateRoot` field in the block
       header.
    3. Light clients can then verify "address X has balance Y at block N"
       with just the block header + a Merkle proof — no full state needed.

    Wiring this into NB04 is left as an exercise; it would invalidate
    already-mined blocks since the header bytes would change.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 9. Export `_lib/trie.py`

    The core trie primitives are written to `_lib/trie.py` for reuse by
    future notebooks. The proof helpers (`prove`, `verify_inclusion`) are
    kept in this notebook for study — they are notebook-specific utilities.
    """)
    return


@app.cell
def _(hash_node):
    import importlib
    import _lib.trie
    importlib.reload(_lib.trie)
    from _lib.trie import nibbles as _nibbles, Node as _Node, Trie as _Trie, hash_node as _hash_node

    # Quick smoke test via the imported lib
    t2 = _Trie()
    t2.put(b'key', b'value')
    assert t2.get(b'key') == b'value'
    assert _hash_node(t2.root) == hash_node(t2.root)
    print('_lib/trie.py exports verified')
    return


if __name__ == "__main__":
    app.run()
