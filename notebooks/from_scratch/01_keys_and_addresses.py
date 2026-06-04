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
    # NB01 — Keys and Addresses

    **Series: Blockchain From Scratch**

    *Prerequisites: NB00 (bytes, hex, hashing, modular arithmetic, secure randomness).*

    In this notebook you will learn how Ethereum turns a random 256-bit number into a public
    address — with no registration, no server, and no authority's permission.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1 — What is an Ethereum account?

    An Ethereum "account" is nothing more than a 20-byte identifier — the **address**.
    You do not register it anywhere. There is no server, no username, no sign-up form.
    An account springs into existence the moment you derive it from a random number.

    The derivation chain is three steps long:

    ```
    random 256-bit integer  (private key)
            │
            │  secp256k1 scalar multiplication
            ▼
        64-byte point on the elliptic curve  (public key, X‖Y)
            │
            │  keccak256 hash, last 20 bytes
            ▼
        20-byte address  (e.g. 0x71C7…)
    ```

    You can generate as many accounts as you like — the supply of 256-bit integers
    (≈ 10^77) is so large that the chance of two people picking the same one is less
    than winning a lottery a trillion consecutive times.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2 — Keccak-256

    Ethereum uses **Keccak-256**, which is related to — but *not identical to* — the
    standard SHA-3 defined by NIST in 2015. The difference is in the padding applied
    before the permutation. Ethereum was designed before NIST finalized SHA-3, and kept
    the original submission padding. If you use `hashlib.sha3_256` you will get a
    different result.

    `pycryptodome` exposes the original Keccak under `Crypto.Hash.keccak`.
    """)
    return


@app.cell
def _():
    from Crypto.Hash import keccak

    def keccak256(data: bytes) -> bytes:
        k = keccak.new(digest_bits=256)
        k.update(data)
        return k.digest()

    # Canonical test vector: keccak256 of the empty string.
    # This is published in the Ethereum Yellow Paper and widely referenced in implementations.
    # Matching it confirms your setup uses the pre-NIST padding, not the NIST SHA-3 padding.
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470", \
        "Wrong digest — you may be using NIST SHA-3 instead of Keccak"
    print("keccak256(b'') =", keccak256(b"").hex())
    return (keccak256,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The empty-string digest above is a **known test vector**: a value that the entire
    Ethereum ecosystem agrees on. Matching it is a fast sanity check that your
    implementation uses the same Keccak variant as every Ethereum node on the planet.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3 — Export keccak256 to `_lib/keccak.py`

    We write the function to a reusable module so every later notebook can import it
    without copy-pasting.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4 — secp256k1: the curve Ethereum signs with

    Ethereum uses **ECDSA** (Elliptic Curve Digital Signature Algorithm) over the curve
    **secp256k1**. Here is the minimal mental model:

    - A curve is a set of points `(x, y)` satisfying `y² = x³ + 7` over a finite field.
    - One of those points is the **generator G**, a specific point baked into the curve
      standard.
    - The **private key** `d` is a random integer in `[1, n-1]` where `n` is the curve order
      (a 256-bit prime close to 2^256).
    - The **public key** is the point `d * G` — scalar multiplication of `G` by `d`.

    Scalar multiplication on an elliptic curve is a one-way function: multiplying `G` by `d`
    is fast; inverting the result to recover `d` is computationally infeasible with current
    hardware (this is the elliptic-curve discrete logarithm problem).

    **We will not implement EC point multiplication by hand.** That is a separate (excellent)
    topic involving point-doubling and point-addition formulas; it is not what this series is
    about. We delegate the curve math to the `coincurve` library, which wraps `libsecp256k1`
    — the same C library used by Bitcoin Core and many Ethereum clients. This is an
    intentional and unapologetic design choice: our goal is to understand the *protocol*,
    not to build a cryptographic primitive library from scratch.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 5 — Generating a private key

    A private key is a random integer in `[1, n-1]` where `n` is the secp256k1 curve order.
    We use rejection sampling: draw 256 random bits; if the result falls outside the valid
    range, discard it and try again. The probability of rejection on any single draw is
    approximately `2^256 / n - 1 ≈ 3.7 × 10^-39` — negligible for all practical purposes.
    """)
    return


@app.cell
def _():
    import secrets

    SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

    def gen_private_key() -> bytes:
        """Return a random 32-byte private key in the valid secp256k1 range [1, n-1]."""
        while True:
            k = secrets.randbits(256)
            if 1 <= k < SECP256K1_N:
                return k.to_bytes(32, "big")

    priv = gen_private_key()
    print("priv:", priv.hex())
    return gen_private_key, priv


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Each call to `gen_private_key()` yields a fresh, cryptographically unpredictable key.
    The bound `[1, n-1]` excludes `0` (degenerate case) and values `≥ n` (outside the
    group order, which would cause the corresponding public key to be invalid).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 6 — Deriving the public key

    `coincurve.keys.PrivateKey` wraps `libsecp256k1`. Calling `.public_key.format(compressed=False)`
    returns the **uncompressed** form of the public-key point: a 65-byte sequence
    `0x04 ‖ X ‖ Y` where `X` and `Y` are the 32-byte big-endian coordinates of the point
    `d * G`.

    The `0x04` prefix is a tag defined by SEC 1 (Standards for Efficient Cryptography) to
    signal an uncompressed point. Ethereum always hashes the raw `X ‖ Y` (64 bytes) for
    address derivation — it drops the prefix.
    """)
    return


@app.cell
def _(priv):
    from coincurve.keys import PrivateKey

    pk = PrivateKey(priv)
    pub = pk.public_key.format(compressed=False)  # 65 bytes: 0x04 || X || Y
    print("pub:", pub.hex())

    pub_xy = pub[1:]  # drop the 0x04 prefix → 64 bytes of raw coordinates
    print("len(pub_xy):", len(pub_xy))
    return PrivateKey, pub_xy


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    `coincurve` performed the EC scalar multiplication `d * G` inside `libsecp256k1`.
    We received back the point as (X, Y) coordinates. The `pub_xy` variable holds those
    64 bytes — this is the input to address derivation.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 7 — Deriving the address

    Ethereum address derivation is defined in the Yellow Paper (Appendix F) and in
    EIP-55. The algorithm is:

    1. Keccak-256 hash the 64-byte uncompressed public-key point (X ‖ Y).
    2. Take the **last 20 bytes** of the 32-byte hash.
    3. Hex-encode the result and prepend `0x`.

    That 20-byte slice is the Ethereum address. The choice of the *last* 20 bytes is
    conventional; what matters is that it is consistent across the entire ecosystem.
    """)
    return


@app.cell
def _(keccak256, pub_xy):
    def to_address(pub_xy: bytes) -> str:
        """Derive an Ethereum address from a 64-byte uncompressed public-key point (X‖Y)."""
        assert len(pub_xy) == 64, f'Expected 64 bytes, got {len(pub_xy)}'
        return '0x' + keccak256(pub_xy)[-20:].hex()
    addr = to_address(pub_xy)
    print('address:', addr)
    return (to_address,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Notice that `to_address` is a pure function: same input always produces the same
    output. The address is not stored anywhere — you can recompute it from the private key
    at any time. Losing the private key means losing access to the account permanently.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 8 — Sanity check against a known vector

    It is easy to introduce a subtle bug (wrong byte offset, wrong prefix handling, wrong
    hash variant) that produces addresses which *look* valid but are wrong. A known test
    vector provides a definitive check.

    The vector below uses private key `0x00…01` (the integer 1). Its expected Ethereum address
    is `0x7e5f4552091a69125d5dfcb7b8c2659029395bdf`, derived from the generator point G
    itself (since `1 * G = G`). This vector appears in multiple Ethereum test suites.
    """)
    return


@app.cell
def _(PrivateKey, to_address):
    KNOWN_PRIV = (1).to_bytes(32, "big")
    KNOWN_ADDR = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"

    pk_check = PrivateKey(KNOWN_PRIV)
    pub_xy_check = pk_check.public_key.format(compressed=False)[1:]
    derived = to_address(pub_xy_check)

    assert derived == KNOWN_ADDR, f"Vector mismatch: got {derived}"
    print("Known-vector check passed:", derived)
    return KNOWN_ADDR, KNOWN_PRIV


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 9 — Export key generation and derivation to `_lib/ecdsa.py`

    We export the three reusable functions to `_lib/ecdsa.py`. Signing (ECDSA `sign` and
    `verify`) will be added in NB02 — the module name anticipates that expansion.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Verification: import from `_lib.ecdsa` and re-run the known-vector check
    """)
    return


@app.cell
def _(KNOWN_ADDR, KNOWN_PRIV):
    import importlib, sys
    for mod in list(sys.modules.keys()):
    # Reload in case the module was cached from an earlier import
        if mod.startswith('_lib'):
            del sys.modules[mod]
    from _lib.ecdsa import priv_to_pub, priv_to_address
    assert priv_to_address(KNOWN_PRIV) == KNOWN_ADDR, 'ecdsa.py known-vector check failed'
    print('_lib.ecdsa known-vector check passed')
    return (priv_to_address,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 10 — Exercises

    1. **Generate 5 keypairs** and print their addresses. Observe that each is unique and
       apparently uncorrelated with the others.

    2. **(Optional / advanced)** Import a MetaMask dev-account private key (a 32-byte hex
       string), derive the address with `priv_to_address`, and confirm it matches what
       MetaMask displays. **Only use a throwaway or dedicated dev account for this — never
       paste the private key of any account holding real funds.**
    """)
    return


@app.cell
def _(gen_private_key, priv_to_address):
    # Exercise 1: generate 5 keypairs and print their addresses
    print("Five fresh Ethereum keypairs:")
    for i in range(5):
        k = gen_private_key()
        a = priv_to_address(k)
        print(f"  [{i+1}] priv={k.hex()[:16]}...  addr={a}")
    return


if __name__ == "__main__":
    app.run()
