"""framing.py — length-prefixed binary framing for raw TCP sockets.

Every message is transmitted as:
    [4-byte big-endian length][N bytes payload]

Functions
---------
send_msg(sock, payload)  — frame and send a bytes payload
recv_exact(sock, n)      — read exactly n bytes (handles short reads)
recv_msg(sock)           — read one framed message; enforces MAX_FRAME_SIZE
"""

import struct

MAX_FRAME_SIZE = 10_000_000  # 10 MB hard cap — prevents 4 GB allocation attacks


def send_msg(sock, payload: bytes) -> None:
    """Send *payload* as a length-prefixed frame."""
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def recv_exact(sock, n: int) -> bytes:
    """Read exactly *n* bytes from *sock*, looping over short reads."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf


def recv_msg(sock) -> bytes:
    """Read one length-prefixed message from *sock*.

    Raises ValueError if the announced length exceeds MAX_FRAME_SIZE.
    """
    header = recv_exact(sock, 4)
    (length,) = struct.unpack(">I", header)
    if length > MAX_FRAME_SIZE:
        raise ValueError(f"message too large: {length} bytes (cap {MAX_FRAME_SIZE})")
    return recv_exact(sock, length)
