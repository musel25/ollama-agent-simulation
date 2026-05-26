import secrets

from coincurve.keys import PrivateKey

from .keccak import keccak256

SECP256K1_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def gen_private_key() -> bytes:
    """Return a cryptographically random 32-byte secp256k1 private key."""
    while True:
        k = secrets.randbits(256)
        if 1 <= k < SECP256K1_N:
            return k.to_bytes(32, "big")


def priv_to_pub(priv: bytes) -> bytes:
    """Return the 64-byte uncompressed public-key point (X‖Y) for *priv*."""
    return PrivateKey(priv).public_key.format(compressed=False)[1:]


def priv_to_address(priv: bytes) -> str:
    """Return the checksumless Ethereum address for *priv* (lowercase hex, 0x-prefixed)."""
    return "0x" + keccak256(priv_to_pub(priv))[-20:].hex()
