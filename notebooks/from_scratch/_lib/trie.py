"""trie.py — simplified Merkle-Patricia Trie (radix-16, branch-only).

This is a pedagogical implementation. It uses the same hash construction
as real Ethereum MPT (keccak256(rlp_encode(node))) but collapses leaf,
extension, and branch nodes into a single uniform branch-only structure.
Hashes produced here will NOT match mainnet MPT hashes.

Exported symbols: nibbles, Node, Trie, hash_node
"""

from .keccak import keccak256
from .rlp_min import rlp_encode


def nibbles(key: bytes) -> list:
    """Split bytes into a list of 4-bit nibbles (values 0..15)."""
    out = []
    for b in key:
        out.append(b >> 4)
        out.append(b & 0x0F)
    return out


class Node:
    __slots__ = ('children', 'value')

    def __init__(self):
        self.children: dict = {}  # int nibble -> Node
        self.value = None         # bytes | None


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


def hash_node(node: Node) -> bytes:
    """Recursively hash a trie node using RLP encoding.

    Each node is serialized as RLP([children_hashes_16, value]) and then
    hashed with keccak256. Empty child slots are encoded as b''.
    """
    children = [
        hash_node(node.children[i]) if i in node.children else b''
        for i in range(16)
    ]
    encoded = rlp_encode([children, node.value or b''])
    return keccak256(encoded)
