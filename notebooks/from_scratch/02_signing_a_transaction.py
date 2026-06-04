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
    # NB02 — Signing a Transaction

    This notebook answers three questions that every Ethereum node implicitly
    answers thousands of times per second:

    1. **How is a transaction serialised to bytes** so every node agrees on the same canonical form?
    2. **What does "signing" actually mean** at the byte level?
    3. **How does anyone recover who sent it** without a user database?

    Prerequisites: NB01 (keys and addresses).  New concepts introduced here:
    RLP encoding, EIP-1559 typed transactions, ECDSA recoverable signatures.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1 — What is a transaction, byte-for-byte?

    A transaction is a plain struct of fields.  To hash and sign it, every node
    must turn that struct into exactly the same byte string — one canonical
    serialisation.  Ethereum uses **RLP** (Recursive Length Prefix) for that.

    For EIP-1559 ("type-2") transactions we prepend a single type byte `0x02`
    before the RLP-encoded field list.  The hash of that byte string is what
    the sender actually signs — the **sighash**.  The sighash is what gets signed.
    Anyone who wants to verify a transaction hashes the same bytes and checks the
    signature against the recovered public key.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2 — RLP from scratch: the four rules

    RLP has exactly four cases (no special integers, no schemas):

    | Case | Input | Encoding |
    |------|-------|----------|
    | 1 | Single byte `b` where `b < 0x80` | The byte itself |
    | 2 | Byte string of length 0..55 | `0x80 + len`, then the bytes |
    | 3 | Byte string of length > 55 | `0xb7 + len(len_bytes)`, `len_bytes`, then the bytes |
    | 4 | List | Encode each element, concatenate; apply cases 2/3 logic but with `0xc0`/`0xf7` instead of `0x80`/`0xb7` |

    Integers are not first-class in RLP: convert to big-endian bytes first
    (with `0` encoded as `b"\"` — the empty byte string).
    """)
    return


@app.cell
def _():
    def rlp_encode(item) -> bytes:
        if isinstance(item, int):
            if item == 0:
                return b"\x80"
            b = item.to_bytes((item.bit_length() + 7) // 8, "big")
            return rlp_encode(b)
        if isinstance(item, bytes):
            if len(item) == 1 and item[0] < 0x80:
                return item
            if len(item) <= 55:
                return bytes([0x80 + len(item)]) + item
            l = len(item).to_bytes((len(item).bit_length() + 7) // 8, "big")
            return bytes([0xb7 + len(l)]) + l + item
        if isinstance(item, list):
            body = b"".join(rlp_encode(x) for x in item)
            if len(body) <= 55:
                return bytes([0xc0 + len(body)]) + body
            l = len(body).to_bytes((len(body).bit_length() + 7) // 8, "big")
            return bytes([0xf7 + len(l)]) + l + body
        raise TypeError(item)

    print("rlp_encode defined")
    return (rlp_encode,)


@app.cell
def _(rlp_encode):
    import rlp as ref_rlp

    cases = [
        b"",
        b"dog",
        0,
        1024,
        [1, b"cat", b"dog"],
        [b"a" * 60],   # triggers long-string branch
    ]
    for c in cases:
        ours   = rlp_encode(c)
        theirs = ref_rlp.encode(c)
        assert ours == theirs, f"mismatch on {c!r}: {ours.hex()} vs {theirs.hex()}"
    print("all match reference rlp package")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3 — Export `rlp_encode` to `_lib/rlp_min.py`

    We export the function so other notebooks can do `from _lib.rlp_min import rlp_encode`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4 — Build an EIP-1559 transaction

    An EIP-1559 (type-2) transaction has nine fields:

    | Field | Meaning |
    |-------|---------|
    | `chainId` | Which network (1=mainnet, 11155111=Sepolia) |
    | `nonce` | How many txs this sender has sent before |
    | `maxPriorityFeePerGas` | Tip to the validator (wei) |
    | `maxFeePerGas` | Absolute maximum you will pay per gas unit (wei) |
    | `gasLimit` | Maximum gas units this tx may consume |
    | `to` | Recipient address (20 bytes) |
    | `value` | ETH to transfer (wei) |
    | `data` | Contract call data (empty for plain ETH transfers) |
    | `accessList` | EIP-2930 warm storage slots (empty list for simple txs) |

    The **unsigned payload** is `0x02 || RLP([chainId, nonce, ...])`.
    That is the exact byte string that gets keccak-hashed to produce the sighash.
    """)
    return


@app.cell
def _(rlp_encode):
    def addr_to_bytes(addr: str) -> bytes:
        return bytes.fromhex(addr.removeprefix('0x'))
    tx = {'chainId': 11155111, 'nonce': 0, 'maxPriorityFeePerGas': 2 * 10 ** 9, 'maxFeePerGas': 30 * 10 ** 9, 'gasLimit': 21000, 'to': addr_to_bytes('0x000000000000000000000000000000000000dEaD'), 'value': 10 ** 15, 'data': b'', 'accessList': []}
    unsigned_fields = [tx['chainId'], tx['nonce'], tx['maxPriorityFeePerGas'], tx['maxFeePerGas'], tx['gasLimit'], tx['to'], tx['value'], tx['data'], tx['accessList']]
    unsigned_payload = b'\x02' + rlp_encode(unsigned_fields)
    print('unsigned payload:', unsigned_payload.hex())  # Sepolia  # 2 gwei  # 0.001 ETH
    return tx, unsigned_fields, unsigned_payload


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 5 — Hash and sign

    **The sighash is what gets signed** — not the raw transaction bytes and not
    any human-readable text.  The sighash is the keccak256 of the unsigned payload.

    `PrivateKey.sign_recoverable(digest, hasher=None)` produces a 65-byte signature:
    `r (32 bytes) || s (32 bytes) || v (1 byte)`.

    `hasher=None` is required: we pass an already-hashed digest, so coincurve must
    not re-hash it.  Without this flag coincurve would hash a hash, producing a
    completely wrong signature.

    `v` is the *recovery id* (0 or 1).  It encodes which of the two possible
    public keys on the curve corresponds to this signature.  Nodes need it to
    recover the sender's public key without it being transmitted explicitly.
    """)
    return


@app.cell
def _(unsigned_payload):
    from _lib.keccak import keccak256
    from _lib.ecdsa import gen_private_key, priv_to_address
    from coincurve.keys import PrivateKey

    priv = gen_private_key()
    print("from:", priv_to_address(priv))

    sighash = keccak256(unsigned_payload)
    print("sighash:", sighash.hex())

    sig = PrivateKey(priv).sign_recoverable(sighash, hasher=None)  # 65 bytes: r||s||v
    r        = sig[0:32]
    s        = sig[32:64]
    y_parity = sig[64]
    print("y_parity:", y_parity)
    return keccak256, priv, priv_to_address, r, s, sig, sighash, y_parity


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 6 — Assemble the signed transaction

    The signed fields append `y_parity`, `r`, `s` to the unsigned field list.
    The resulting raw transaction is what you broadcast to the network.
    `tx_hash` is the identifier that gets confirmed in a block explorer.
    """)
    return


@app.cell
def _(keccak256, r, rlp_encode, s, unsigned_fields, y_parity):
    signed_fields  = unsigned_fields + [y_parity, r, s]
    signed_payload = b"\x02" + rlp_encode(signed_fields)
    tx_hash        = keccak256(signed_payload)
    print("txHash:  ", "0x" + tx_hash.hex())
    print("raw tx:  ", "0x" + signed_payload.hex())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 7 — Recover the signer

    Given the 65-byte signature and the sighash, anyone can reconstruct the sender's
    public key — and from that, the address.

    **This is what every Ethereum node does.**  They do not store who you are.
    They recover you from the signature.  No user database.  No login.  The
    signature itself is the identity proof.
    """)
    return


@app.cell
def _(keccak256, priv, priv_to_address, sig, sighash):
    from coincurve import PublicKey

    recovered_pub    = PublicKey.from_signature_and_message(sig, sighash, hasher=None)
    recovered_pub_xy = recovered_pub.format(compressed=False)[1:]
    recovered_addr   = "0x" + keccak256(recovered_pub_xy)[-20:].hex()

    assert recovered_addr == priv_to_address(priv)
    print("signer recovered:", recovered_addr)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 8 — Export `sign_digest` and `recover_address` to `_lib/ecdsa.py`

    We append to the existing file — the original keygen functions stay intact.
    """)
    return


@app.cell
def _(priv, priv_to_address, sighash):
    import importlib
    import _lib.ecdsa as _e
    importlib.reload(_e)
    from _lib.ecdsa import sign_digest, recover_address

    r2, s2, v2 = sign_digest(priv, sighash)
    assert recover_address(sighash, r2, s2, v2) == priv_to_address(priv)
    print("lib sign+recover round-trip OK")
    return (recover_address,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 9 — Tampering exercises

    ### Exercise A — alter the transaction value

    Change a single field in the transaction and recompute the sighash.
    Because keccak256 is a one-way avalanche function, every output bit changes
    unpredictably.  The original `(r, s, y_parity)` then recovers a completely
    different (effectively random) address — not the original signer.

    The signature cryptographically binds the **exact bytes** that were signed.
    The tiniest change makes verification fail.  This is what makes Ethereum
    tamper-evident.
    """)
    return


@app.cell
def _(
    keccak256,
    priv,
    priv_to_address,
    r,
    recover_address,
    rlp_encode,
    s,
    sighash,
    tx,
    y_parity,
):
    tx_evil = dict(tx)
    tx_evil["value"] = tx["value"] + 1   # one wei more

    unsigned_evil = b"\x02" + rlp_encode([
        tx_evil["chainId"], tx_evil["nonce"], tx_evil["maxPriorityFeePerGas"],
        tx_evil["maxFeePerGas"], tx_evil["gasLimit"], tx_evil["to"],
        tx_evil["value"], tx_evil["data"], tx_evil["accessList"],
    ])
    evil_sighash = keccak256(unsigned_evil)

    print("original sighash:", sighash.hex())
    print("tampered sighash:", evil_sighash.hex())

    wrong_addr = recover_address(evil_sighash, r, s, y_parity)
    print("wrong signer recovered:", wrong_addr)
    print("matches original?      ", wrong_addr == priv_to_address(priv))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Exercise B — corrupt the signature itself

    Flipping a single bit in `r` may produce an invalid secp256k1 curve point —
    not every 32-byte value corresponds to a valid point.  In that case recovery
    raises a `ValueError` immediately (no valid public key can be derived).
    Even when the tampered `r` does happen to land on a valid point, the recovered
    address is a junk address unrelated to the original signer.  Either way,
    a node rejects the transaction: the recovered address has zero balance/nonce.

    The signature cryptographically binds the exact bytes.  There is no way to
    forge or modify it without breaking the signature.
    """)
    return


@app.cell
def _(priv, priv_to_address, r, recover_address, s, sighash, y_parity):
    r_evil = bytes([r[0] ^ 0x01]) + r[1:]
    try:
        wrong_addr2 = recover_address(sighash, r_evil, s, y_parity)
        print("address recovered from tampered r:", wrong_addr2)
        print("matches original?", wrong_addr2 == priv_to_address(priv))
    except ValueError as exc:
        print("tampered r produced an invalid curve point — recovery failed:", exc)
        print("matches original? False  (recovery impossible)")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Summary

    | Concept | One-line takeaway |
    |---------|-------------------|
    | RLP | Four simple rules turn any nested byte structure into a unique, canonical byte string |
    | Sighash | keccak256 of the typed (0x02-prefixed) RLP payload — **this is what gets signed** |
    | Recoverable signature | 65 bytes: `r \| s \| y_parity`.  `y_parity` lets nodes recover the public key |
    | Recovery | `PublicKey.from_signature_and_message` gives back the public key → address — no database needed |
    | Tamper evidence | One bit change anywhere invalidates the signature and recovers a wrong address |

    Next: NB03 — deploying a contract and reading its state.
    """)
    return


if __name__ == "__main__":
    app.run()
