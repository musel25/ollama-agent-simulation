"""chain.py — minimal single-node blockchain primitives.

Provides Account, Tx, Block, Chain and the helpers get_account, apply_tx,
make_tx.  Imported by NB05+ notebooks.

Design notes:
- Block headers commit to transactions via concatenated tx hashes.
  NB08 replaces this with a Merkle root.
- No gas, no consensus, no networking.  Those come in NB07/NB05+.
"""

import copy
import time
from dataclasses import dataclass, field

from .rlp_min import rlp_encode
from .keccak import keccak256
from .ecdsa import sign_digest, recover_address, priv_to_address


# ---------------------------------------------------------------------------
# Account and State
# ---------------------------------------------------------------------------

@dataclass
class Account:
    balance: int = 0
    nonce: int = 0


State = dict  # addr (str) -> Account


def get_account(state: State, addr: str) -> Account:
    """Return account for *addr*, auto-creating a zero account if absent."""
    if addr not in state:
        state[addr] = Account()
    return state[addr]


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

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
    """Build and sign a Tx from a private key."""
    sender = priv_to_address(priv)
    t = Tx(sender, to, value, nonce)
    digest = keccak256(t.unsigned_bytes())
    t.r, t.s, t.y_parity = sign_digest(priv, digest)
    return t


# ---------------------------------------------------------------------------
# apply_tx
# ---------------------------------------------------------------------------

def apply_tx(state: State, tx: Tx) -> None:
    """Validate and apply *tx* to *state* (mutates in place).

    Raises AssertionError on any validation failure; caller is responsible
    for rolling back state if atomicity is required.
    """
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


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------

@dataclass
class Block:
    number: int
    parent_hash: bytes
    txs: list
    timestamp: int

    def header_bytes(self) -> bytes:
        tx_hashes_concat = b"".join(t.hash() for t in self.txs)
        return rlp_encode([
            self.number,
            self.parent_hash,
            self.timestamp,
            tx_hashes_concat,
        ])

    def hash(self) -> bytes:
        return keccak256(self.header_bytes())


# ---------------------------------------------------------------------------
# Chain
# ---------------------------------------------------------------------------

class Chain:
    """Single-node, in-process blockchain."""

    def __init__(self, genesis_state: State):
        self.state = genesis_state
        genesis = Block(0, b"\x00" * 32, [], int(time.time()))
        self.blocks = [genesis]

    @property
    def head(self) -> Block:
        return self.blocks[-1]

    def propose(self, txs: list) -> Block:
        """Apply *txs* atomically and append a new block.

        If any transaction fails validation the state is rolled back and the
        exception (AssertionError or ValueError) propagates to the caller.
        """
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
