"""peer.py — toy Ethereum-style P2P node over TCP.

Message types
-------------
HELLO        0x01  -- node_id (8 bytes) || port (2 bytes BE)
ANNOUNCE_TX  0x04  -- tx_hash (32 bytes)
GET_TX       0x05  -- tx_hash (32 bytes)
TX           0x06  -- tx_bytes (arbitrary)
GET_HEAD     0x10  -- (none)
HEAD         0x11  -- number(4 BE) || hash(32)
GET_BLOCK    0x12  -- number(4 BE)
BLOCK        0x13  -- block_bytes (RLP)

Codes 0x02 (GETPEERS) and 0x03 (PEERS) are reserved for a future session.
"""

import copy
import math
import random
import secrets
import socket
import struct
import threading

from .framing import send_msg, recv_msg
from .keccak import keccak256

# ---------------------------------------------------------------------------
# Message type constants
# ---------------------------------------------------------------------------

HELLO       = 0x01
ANNOUNCE_TX = 0x04
GET_TX      = 0x05
TX          = 0x06
GET_HEAD    = 0x10
HEAD        = 0x11
GET_BLOCK   = 0x12
BLOCK       = 0x13


# ---------------------------------------------------------------------------
# Encode / decode helpers
# ---------------------------------------------------------------------------

def encode_msg(msg_type: int, body: bytes) -> bytes:
    """Prepend the single-byte type code to *body*."""
    return bytes([msg_type]) + body


def decode_msg(payload: bytes) -> tuple:
    """Split a received payload into (msg_type, body)."""
    return payload[0], payload[1:]


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------

class Node:
    """A dual-role (listener + dialer) P2P node.

    Each node:
    * Listens on *port* for inbound peers.
    * Can dial out to known peers via :meth:`connect`.
    * Gossips new transactions using sqrt-fanout (the eth/68 pattern).
    * Optionally holds a Chain; supports block-sync via try_sync.
    """

    def __init__(self, port: int, chain=None, genesis_state=None):
        self.port = port
        self.node_id = secrets.token_bytes(8)
        self.peers: dict = {}  # peer_id -> socket
        self.seen_tx: set = set()
        self.tx_pool: dict = {}  # hash -> raw bytes
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._listener_sock = None
        self.chain = chain
        self.genesis_state = copy.deepcopy(genesis_state) if genesis_state is not None else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start the background listener thread."""
        threading.Thread(target=self._listen, daemon=True).start()

    def stop(self):
        """Signal all threads to exit and close all sockets."""
        self._stop.set()
        with self.lock:
            for pid, conn in list(self.peers.items()):
                try:
                    conn.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    conn.close()
                except OSError:
                    pass
            self.peers.clear()
        if self._listener_sock is not None:
            try:
                self._listener_sock.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Listener
    # ------------------------------------------------------------------

    def _listen(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.port))
        srv.listen(20)
        srv.settimeout(0.5)  # allows _stop checks
        self._listener_sock = srv
        while not self._stop.is_set():
            try:
                conn, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handshake_inbound,
                args=(conn,),
                daemon=True,
            ).start()

    # ------------------------------------------------------------------
    # Handshake -- inbound direction
    # ------------------------------------------------------------------

    def _handshake_inbound(self, conn):
        try:
            conn.settimeout(2.0)
            payload = recv_msg(conn)
            mt, body = decode_msg(payload)
            if mt != HELLO:
                conn.close()
                return
            peer_id = body[:8]
            peer_port = struct.unpack(">H", body[8:10])[0]
            with self.lock:
                if peer_id == self.node_id or peer_id in self.peers:
                    conn.close()
                    return
                self.peers[peer_id] = conn
            send_msg(conn, encode_msg(HELLO, self.node_id + struct.pack(">H", self.port)))
            print(f"[{self.port}] inbound peer {peer_id.hex()} from :{peer_port}")
            self._peer_loop(peer_id, conn)
        except Exception:
            conn.close()

    # ------------------------------------------------------------------
    # Handshake -- outbound direction
    # ------------------------------------------------------------------

    def connect(self, host: str, port: int) -> bool:
        """Dial *host:port*, exchange HELLO, and start a peer loop."""
        try:
            conn = socket.socket()
            conn.settimeout(2.0)
            conn.connect((host, port))
            send_msg(conn, encode_msg(HELLO, self.node_id + struct.pack(">H", self.port)))
            payload = recv_msg(conn)
            mt, body = decode_msg(payload)
            if mt != HELLO:
                conn.close()
                return False
            peer_id = body[:8]
            with self.lock:
                if peer_id == self.node_id or peer_id in self.peers:
                    conn.close()
                    return False
                self.peers[peer_id] = conn
            print(f"[{self.port}] outbound peer {peer_id.hex()} -> :{port}")
            threading.Thread(
                target=self._peer_loop,
                args=(peer_id, conn),
                daemon=True,
            ).start()
            return True
        except (OSError, ConnectionError):
            return False

    # ------------------------------------------------------------------
    # Per-peer message loop
    # ------------------------------------------------------------------

    def _peer_loop(self, peer_id: bytes, conn: socket.socket):
        try:
            while not self._stop.is_set():
                try:
                    payload = recv_msg(conn)
                except socket.timeout:
                    continue
                mt, body = decode_msg(payload)
                if mt == ANNOUNCE_TX:
                    self._handle_announce(peer_id, body)
                elif mt == GET_TX:
                    with self.lock:
                        tx_body = self.tx_pool.get(body)
                    if tx_body is not None:
                        try:
                            send_msg(conn, encode_msg(TX, tx_body))
                        except OSError:
                            pass
                elif mt == TX:
                    self._handle_tx(body)
                elif mt == GET_HEAD:
                    if self.chain is not None:
                        with self.lock:
                            head = self.chain.head
                        try:
                            send_msg(conn, encode_msg(HEAD,
                                struct.pack(">I", head.number) + head.hash()))
                        except OSError:
                            pass
                elif mt == GET_BLOCK:
                    n = struct.unpack(">I", body[:4])[0]
                    with self.lock:
                        if self.chain is not None and 0 <= n < len(self.chain.blocks):
                            blk_bytes = self.chain.blocks[n].to_bytes()
                        else:
                            blk_bytes = None
                    if blk_bytes is not None:
                        try:
                            send_msg(conn, encode_msg(BLOCK, blk_bytes))
                        except OSError:
                            pass
                elif mt == BLOCK:
                    self._handle_block(body)
        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            with self.lock:
                self.peers.pop(peer_id, None)

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def _handle_announce(self, peer_id: bytes, tx_hash: bytes):
        with self.lock:
            if tx_hash in self.seen_tx:
                return
            conn = self.peers.get(peer_id)
        if conn is not None:
            try:
                send_msg(conn, encode_msg(GET_TX, tx_hash))
            except OSError:
                pass

    def _handle_tx(self, tx_bytes: bytes):
        h = keccak256(tx_bytes)
        with self.lock:
            if h in self.seen_tx:
                return
            self.seen_tx.add(h)
            self.tx_pool[h] = tx_bytes
        print(f"[{self.port}] got tx {h.hex()[:8]}...")
        self._gossip(h)

    def _handle_block(self, blk_bytes: bytes):
        """Called when an unsolicited BLOCK arrives -- extend chain if it fits on head."""
        from .chain import Block, apply_tx
        blk = Block.from_bytes(blk_bytes)
        with self.lock:
            if self.chain is None:
                return
            if blk.number != self.chain.head.number + 1:
                return
            if blk.parent_hash != self.chain.head.hash():
                return
            snap = copy.deepcopy(self.chain.state)
            try:
                for t in blk.txs:
                    apply_tx(self.chain.state, t)
                self.chain.blocks.append(blk)
                print(f"[{self.port}] extended chain to height {blk.number}")
            except (AssertionError, ValueError) as e:
                self.chain.state = snap
                print(f"[{self.port}] rejected block {blk.number}: {e}")

    # ------------------------------------------------------------------
    # Block sync
    # ------------------------------------------------------------------

    def try_sync(self, peer_port: int) -> bool:
        """Open a fresh connection to *peer_port* and sync if the peer is longer.

        Uses a dedicated short-lived socket so the sync request/response
        sequence does not race with the background _peer_loop reader.
        Returns True if a reorg was performed, False otherwise.
        """
        from .chain import Block, apply_tx, replay_chain_from_genesis
        if self.chain is None:
            return False

        # Open a fresh socket just for sync
        try:
            sock = socket.socket()
            sock.settimeout(3.0)
            sock.connect(('127.0.0.1', peer_port))
            # Use a fresh ephemeral node_id so the server does not reject
            # this socket as a duplicate of our existing gossip connection.
            ephemeral_id = secrets.token_bytes(8)
            send_msg(sock, encode_msg(HELLO, ephemeral_id + struct.pack(">H", self.port)))
            hello_payload = recv_msg(sock)
            mt, _ = decode_msg(hello_payload)
            if mt != HELLO:
                sock.close()
                return False
        except (OSError, ConnectionError, socket.timeout):
            return False

        try:
            # Ask for peer's best head
            send_msg(sock, encode_msg(GET_HEAD, b''))
            payload = recv_msg(sock)
            mt, body = decode_msg(payload)
            if mt != HEAD:
                return False
            peer_num = struct.unpack(">I", body[:4])[0]

            with self.lock:
                my_head_num = self.chain.head.number
            if peer_num <= my_head_num:
                return False

            # Walk back from peer's head until we find a common ancestor
            needed = []  # reversed: peer's head first
            cur_num = peer_num
            while True:
                send_msg(sock, encode_msg(GET_BLOCK, struct.pack(">I", cur_num)))
                payload = recv_msg(sock)
                mt, body = decode_msg(payload)
                if mt != BLOCK:
                    return False
                blk = Block.from_bytes(body)
                needed.append(blk)
                with self.lock:
                    local_len = len(self.chain.blocks)
                    if cur_num < local_len and self.chain.blocks[cur_num].hash() == blk.hash():
                        # Found common ancestor
                        break
                if cur_num == 0:
                    break
                cur_num -= 1

            # needed[-1] is the common-ancestor block at height cur_num
            # new_blocks is everything above the common ancestor, forward order
            common_num = needed[-1].number
            new_blocks = list(reversed(needed[:-1]))

            with self.lock:
                rewound = self.chain.blocks[common_num + 1:]
                self.chain.blocks = self.chain.blocks[:common_num + 1]
                # Rebuild state from genesis through the common ancestor
                self.chain.state = replay_chain_from_genesis(
                    self.chain.blocks, self.genesis_state
                )
                # Apply peer's branch
                for b in new_blocks:
                    for t in b.txs:
                        apply_tx(self.chain.state, t)
                    self.chain.blocks.append(b)
                print(f"[{self.port}] REORG: dropped {len(rewound)} block(s), applied {len(new_blocks)}")
            return True
        except (OSError, ConnectionError, socket.timeout):
            return False
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def gossip_block(self, blk):
        """Broadcast a new block to all peers."""
        blk_bytes = blk.to_bytes()
        with self.lock:
            peers = list(self.peers.values())
        for conn in peers:
            try:
                send_msg(conn, encode_msg(BLOCK, blk_bytes))
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Sqrt-fanout gossip
    # ------------------------------------------------------------------

    def _gossip(self, tx_hash: bytes):
        """Send TX body to sqrt(N) peers; ANNOUNCE_TX (hash only) to the rest."""
        with self.lock:
            peers = list(self.peers.items())
            body = self.tx_pool.get(tx_hash)
        if not peers or body is None:
            return
        k = max(1, int(math.sqrt(len(peers))))
        full_recipients = set(p[0] for p in random.sample(peers, min(k, len(peers))))
        for pid, conn in peers:
            try:
                if pid in full_recipients:
                    send_msg(conn, encode_msg(TX, body))
                else:
                    send_msg(conn, encode_msg(ANNOUNCE_TX, tx_hash))
            except OSError:
                pass

    def submit_tx(self, tx_bytes: bytes):
        """Inject a new transaction into this node and gossip it."""
        h = keccak256(tx_bytes)
        with self.lock:
            self.seen_tx.add(h)
            self.tx_pool[h] = tx_bytes
        self._gossip(h)
