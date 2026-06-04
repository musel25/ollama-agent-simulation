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
    # NB00 — Foundations

    **Series: Blockchain From Scratch**

    *Prerequisites: basic Python (variables, functions, loops). No prior cryptography required.*
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. Why this notebook

    Every concept in this series — private keys, addresses, digital signatures, transactions,
    Merkle trees — ultimately compiles down to four primitives:

    1. **Bytes and hex** — the raw material; data in memory is always bytes, and hex is just a
       convenient way to read or print them.
    2. **Hash functions** — deterministic one-way compression; the fingerprint mechanism behind
       every blockchain data structure.
    3. **Modular arithmetic** — ordinary arithmetic inside a finite "clock face"; the algebra
       that makes elliptic-curve cryptography work.
    4. **Secure randomness** — the only source of true entropy in the system; private keys are
       just random 256-bit numbers.

    Later notebooks (NB01 onward) add layers on top of these four. This notebook builds the
    vocabulary so the rest of the series can move quickly.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Bytes and hex

    A **byte** is an integer from 0 to 255. Python's `bytes` type is an immutable sequence of
    bytes. Hexadecimal (base-16) is the standard notation throughout blockchain code because one
    byte maps to exactly two hex digits — no ambiguity, no wasted characters.

    Knowing how to move between raw bytes, hex strings, and integers is the single most useful
    skill for reading blockchain source code. The three conversions below cover 90 % of what
    you will encounter.
    """)
    return


@app.cell
def _():
    # bytes <-> hex
    b = bytes([72, 105, 33])
    print(b)               # Python shows printable ASCII chars when it can
    print(b.hex())         # '486921'
    print(bytes.fromhex("486921"))  # back to bytes
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Notice that 0x48 = 72 (decimal) = 'H' (ASCII). Hex is just a more compact way to write the
    same number.
    """)
    return


@app.cell
def _():
    # integer <-> bytes  (256-bit / 32-byte values are everywhere in Ethereum)
    n = 12345
    print(n.to_bytes(32, "big").hex())
    print(int.from_bytes(bytes.fromhex("00" * 31 + "ff"), "big"))  # 255
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    `to_bytes(32, "big")` pads the number on the left so it always occupies exactly 32 bytes —
    the standard width for a 256-bit value. `"big"` means the most-significant byte comes first
    (more on this in section 6).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. Hash functions, intuitively

    A **hash function** takes an arbitrary-length input and returns a fixed-length output (the
    *digest*). Two properties make it useful in blockchains:

    - **Deterministic**: the same input always gives the same output.
    - **Avalanche effect**: changing even one bit of input produces a completely different
      output. This is what makes tampering detectable.

    SHA-256 is the hash function used by Bitcoin. Ethereum uses Keccak-256 (a variant of SHA-3),
    which we will introduce in NB01. For now, SHA-256 illustrates the ideas perfectly.
    """)
    return


@app.cell
def _():
    import hashlib

    h1 = hashlib.sha256(b"hello").hexdigest()
    h2 = hashlib.sha256(b"hellp").hexdigest()  # one letter different

    print("hello:", h1)
    print("hellp:", h2)
    print("Identical?", h1 == h2)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The two digests share no obvious structure despite the inputs differing by one letter. This
    is the avalanche effect. It means you cannot work backwards from the digest to reconstruct
    the input (pre-image resistance), and finding two inputs with the same digest is
    computationally infeasible (collision resistance).

    **Exercise:** hash your first name and a version with one letter changed. Observe that the
    outputs look completely unrelated.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 4. Modular arithmetic

    Modular arithmetic is ordinary arithmetic, but the result "wraps around" at a fixed number
    called the **modulus** (think of a 12-hour clock: 11 + 2 = 1). When the modulus is a prime
    number `p`, every non-zero element has a multiplicative inverse — a number that, multiplied
    by the original, gives 1. This property is what lets us define division in a finite set of
    numbers, which is the algebraic foundation of elliptic-curve cryptography.
    """)
    return


@app.cell
def _():
    p = 23  # small prime for intuition

    print("7 + 19 mod 23 =", (7 + 19) % p)             # 3
    print("7 * 19 mod 23 =", (7 * 19) % p)             # 18
    print("inverse of 7  =", pow(7, -1, p))             # 10
    print("7 * inv(7) mod 23 =", (7 * pow(7, -1, p)) % p)  # 1
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    `pow(7, -1, p)` is Python 3.8+ syntax for the modular inverse. Multiplying 7 by its inverse
    (10) gives 1 mod 23 — the same role that a fraction plays in ordinary arithmetic.
    """)
    return


@app.cell
def _():
    # The secp256k1 field prime used by Bitcoin and Ethereum
    p_secp = 2**256 - 2**32 - 977
    print(hex(p_secp))
    print("bit length:", p_secp.bit_length())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    All elliptic-curve arithmetic for Bitcoin and Ethereum keys happens modulo this 256-bit prime.
    The number is close to (but slightly less than) 2^256, which is why keys are 32 bytes wide.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 5. Randomness

    A private key is a random integer between 1 and the curve order (a number close to `p_secp`).
    "Random" here means cryptographically unpredictable — an attacker must not be able to guess
    it even after observing all your other outputs.

    Python's `random` module is *not* cryptographically secure: its state can be reconstructed
    from 624 consecutive outputs. Always use `secrets` for anything security-sensitive.
    """)
    return


@app.cell
def _():
    import secrets

    # A 256-bit random integer — the raw material for a private key
    priv = secrets.randbits(256)
    print("random int:", priv)

    # Equivalently, 32 random bytes expressed in hex
    raw = secrets.token_bytes(32)
    print("as hex:    ", raw.hex())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Each run produces a different value. NB02 will show how to clamp this integer to the valid
    key range and derive a public key from it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 6. Endianness, briefly

    Multi-byte integers can be stored with the most-significant byte first (**big-endian**) or
    last (**little-endian**). Ethernet frames and IP packets use big-endian ("network byte
    order"). Ethereum's RLP encoding and ABI encoding also use big-endian. Bitcoin's internal
    transaction format uses little-endian for some fields. Mixing them up produces silent bugs
    that are very hard to trace, so it pays to know what you are looking at.

    This detail becomes important in NB05 when we parse raw Ethereum transactions from bytes.
    """)
    return


@app.cell
def _():
    import struct

    big    = struct.pack(">I", 1234)  # ">I" = big-endian unsigned 32-bit int
    little = struct.pack("<I", 1234)  # "<I" = little-endian

    print("big-endian   :", big.hex())    # 000004d2  (high byte first)
    print("little-endian:", little.hex()) # d2040000  (low byte first)
    print("same integer?", int.from_bytes(big, "big") == int.from_bytes(little, "little"))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    1234 in hex is 0x4D2. In big-endian the bytes are `00 00 04 d2`; in little-endian they are
    reversed: `d2 04 00 00`. The underlying integer is the same — only the byte layout differs.
    When you are parsing a binary protocol, always check the spec for which convention it uses.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. Summary

    | Primitive | Python tools | Where it appears |
    |---|---|---|
    | Bytes / hex | `bytes`, `.hex()`, `bytes.fromhex()` | everywhere — keys, addresses, transactions |
    | Hash functions | `hashlib.sha256` (SHA-256), keccak in NB01 | block IDs, Merkle trees, addresses |
    | Modular arithmetic | `%`, `pow(a, -1, p)` | elliptic-curve key math (NB02) |
    | Secure randomness | `secrets.randbits`, `secrets.token_bytes` | private key generation (NB02) |
    | Endianness | `struct.pack`, `int.to_bytes` | transaction parsing (NB05) |

    **Next:** NB01 introduces Keccak-256 and shows how Ethereum derives an address from 20 bytes
    of a hash.
    """)
    return


if __name__ == "__main__":
    app.run()
