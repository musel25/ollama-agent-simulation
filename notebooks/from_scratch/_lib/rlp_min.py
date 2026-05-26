"""Minimal RLP encoder — covers the four canonical cases.

This is a scratch-built implementation for pedagogical purposes.
It handles: int, bytes, list (recursively).  Matches the reference 'rlp' package.
"""


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
