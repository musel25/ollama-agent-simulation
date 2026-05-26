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

from coincurve import PublicKey


def sign_digest(priv: bytes, digest: bytes) -> tuple[bytes, bytes, int]:
    """Sign an already-hashed 32-byte digest.  Returns (r, s, y_parity)."""
    sig = PrivateKey(priv).sign_recoverable(digest, hasher=None)
    return sig[0:32], sig[32:64], sig[64]


def recover_address(digest: bytes, r: bytes, s: bytes, y_parity: int) -> str:
    """Recover the Ethereum address from a (r, s, y_parity) signature."""
    sig = r + s + bytes([y_parity])
    pub = PublicKey.from_signature_and_message(sig, digest, hasher=None)
    pub_xy = pub.format(compressed=False)[1:]
    return "0x" + keccak256(pub_xy)[-20:].hex()
