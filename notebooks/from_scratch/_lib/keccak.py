from Crypto.Hash import keccak


def keccak256(data: bytes) -> bytes:
    """Return the 32-byte Keccak-256 digest of *data*.

    Uses the original Keccak padding (pre-NIST), which is what Ethereum specifies.
    Do NOT substitute hashlib.sha3_256 — it produces different output.
    """
    k = keccak.new(digest_bits=256)
    k.update(data)
    return k.digest()
