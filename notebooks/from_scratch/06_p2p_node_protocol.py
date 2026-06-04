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
    # NB06 — P2P Node Protocol

    Build a real (toy) Ethereum-style peer protocol over TCP.
    Nodes connect to each other, handshake, gossip transactions using sqrt-fanout.

    **Dependencies:** `_lib/framing.py`, `_lib/keccak.py` (from prior notebooks).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 1. From client-server to peer-to-peer

    NB05 had a server and a client. In P2P, every node is BOTH.
    Each node listens for incoming peers AND dials out to known peers.
    We will build a `Node` class that does both, then run 8 nodes locally
    and watch a transaction propagate across the mesh.

    Key ideas:

    * **Dual role** — every node binds a listen port AND connects to peers.
    * **Handshake** — nodes exchange `HELLO` (id + port) before sending anything else.
    * **Gossip** — when a node learns a new tx it forwards it; no central coordinator.
    * **Sqrt-fanout** — the `eth/68` pattern: send the full body to ~√N peers,
      send only the hash (`ANNOUNCE_TX`) to the rest. Recipients that want the body
      request it with `GET_TX`. This bounds bandwidth at scale.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Message types

    | Type | Code | Payload |
    |------|------|---------|
    | HELLO | `0x01` | `node_id (8 bytes) \|\| port (2 bytes BE)` |
    | ANNOUNCE_TX | `0x04` | `tx_hash (32 bytes)` |
    | GET_TX | `0x05` | `tx_hash (32 bytes)` |
    | TX | `0x06` | `tx_bytes (arbitrary)` |

    Codes `0x02` (GETPEERS) and `0x03` (PEERS) are reserved for a future session.

    Every message is wrapped in the 4-byte length-prefix framing from `_lib/framing.py`.
    """)
    return


@app.cell
def _():
    import struct

    # Message type constants
    HELLO       = 0x01
    ANNOUNCE_TX = 0x04
    GET_TX      = 0x05
    TX          = 0x06

    def encode_msg(msg_type: int, body: bytes) -> bytes:
        """Prepend the single-byte type code."""
        return bytes([msg_type]) + body

    def decode_msg(payload: bytes) -> tuple:
        """Split (msg_type, body)."""
        return payload[0], payload[1:]

    print('constants:', hex(HELLO), hex(ANNOUNCE_TX), hex(GET_TX), hex(TX))
    return ANNOUNCE_TX, TX, encode_msg


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 3. The `Node` class

    The `Node` class lives in `_lib/peer.py`.  It combines:

    * A **listener thread** that `accept()`s inbound connections
      (with a 0.5 s socket timeout so it checks `_stop` frequently).
    * A **handshake** that exchanges `HELLO` before any data flows.
    * A **per-peer reader thread** that handles `ANNOUNCE_TX`, `GET_TX`, and `TX`.
    * A **`stop()`** method that sets `_stop`, closes all peer sockets, and
      closes the listener — letting every daemon thread exit cleanly.

    The full source is written to disk with `%%writefile` in the next cell.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 7. 8-node demo

    Spin up 8 nodes on ports 5571-5578, let each one dial 3 random peers,
    then verify every node has at least one connection.
    """)
    return


@app.cell
def _():
    import importlib, sys, time, random, secrets, os
    # Ensure _lib is on the path
    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    import _lib.peer as _p
    importlib.reload(_p)
    from _lib.peer import Node
    from _lib.keccak import keccak256
    nodes = [Node(5570 + i) for i in range(1, 9)]
    for _n in nodes:
        _n.start()
    time.sleep(0.3)
    random.seed(0)
    for _n in nodes:
        others = [m for m in nodes if m is not _n]
        for m in random.sample(others, 3):
    # Each node connects to 3 random others
            _n.connect('127.0.0.1', m.port)
    time.sleep(0.5)
    peer_counts = [len(_n.peers) for _n in nodes]
    print('\npeer counts:', peer_counts)
    assert all((c > 0 for c in peer_counts)), f'a node has no peers: {peer_counts}'
    print('mesh formed OK')
    return Node, keccak256, nodes, random, secrets, time


@app.cell
def _(keccak256, nodes, secrets, time):
    test_tx = b'hand_built_tx_payload_' + secrets.token_bytes(8)
    test_hash = keccak256(test_tx)
    print('\nsubmitting tx', test_hash.hex()[:8], 'at node :', nodes[0].port)
    nodes[0].submit_tx(test_tx)
    have = []
    # Poll up to 2 s for global saturation
    for _ in range(20):
        have = [_n for _n in nodes if test_hash in _n.tx_pool]
        if len(have) == len(nodes):
            break
        time.sleep(0.1)
    print(f'\n{len(have)}/{len(nodes)} nodes have the tx')
    assert len(have) == len(nodes), f'only {len(have)}/{len(nodes)} saturated'
    print('saturation confirmed')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 8. Observing frames with tcpdump

    In a separate terminal, run:

    ```bash
    sudo tcpdump -i lo -X 'tcp portrange 5571-5578' -c 30
    ```

    Then re-run the submit cell above.  You will see:

    * **HELLO frames** (`01` + node_id + port) during `connect()`
    * **ANNOUNCE_TX frames** (`04` + 32-byte hash) — to non-full recipients
    * **TX frames** (`06` + raw payload) — to the sqrt-chosen full recipients

    bouncing between ports 5571-5578.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 9. Debugging exercises

    ### 9a. Kill a node mid-gossip

    P2P networks tolerate node failures.  Stop one node, then broadcast a new
    transaction and confirm all *surviving* nodes still receive it.
    """)
    return


@app.cell
def _(keccak256, nodes, secrets, time):
    print('\n--- killing node :', nodes[3].port, 'and re-submitting ---')
    nodes[3].stop()
    time.sleep(0.3)
    test_tx2 = b'second_payload_' + secrets.token_bytes(8)
    test_hash2 = keccak256(test_tx2)
    nodes[0].submit_tx(test_tx2)
    have2 = []
    for _ in range(20):
        have2 = [_n for _n in nodes if _n is not nodes[3] and test_hash2 in _n.tx_pool]
        if len(have2) == len(nodes) - 1:
            break
        time.sleep(0.1)
    print(f'after kill, {len(have2)}/{len(nodes) - 1} surviving nodes have the new tx')
    assert len(have2) == len(nodes) - 1, f'expected {len(nodes) - 1} surviving, got {len(have2)}'
    print('kill-a-node resilience confirmed')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### 9b. Bandwidth comparison: sqrt-fanout vs full broadcast

    Subclass `Node` to count bytes per gossip strategy.  The origin node does the bulk of the work, so we measure only its `bytes_sent`.

    **Why sqrt-fanout matters:** for N peers, full broadcast sends N copies of the
    full payload. Sqrt-fanout sends √N full copies plus (N-√N) 32-byte hashes.
    For N=7 and a 80-byte payload that is ~7 full sends vs ~3 full + 4 hash sends —
    already a win, and the gap widens dramatically with larger networks.
    """)
    return


@app.cell
def _(ANNOUNCE_TX, Node, TX, encode_msg, random, secrets, time):
    import math
    from _lib.framing import send_msg

    class CountingNode(Node):

        def __init__(self, port, strategy):
            super().__init__(port)
            self.strategy = strategy
            self.bytes_sent = 0

        def _gossip(self, tx_hash):
            with self.lock:
                peers = list(self.peers.items())
                body = self.tx_pool.get(tx_hash)
            if not peers or body is None:
                return
            if self.strategy == 'broadcast':
                for pid, conn in peers:
                    frame = encode_msg(TX, body)
                    self.bytes_sent += 4 + len(frame)
                    try:
                        send_msg(conn, frame)
                    except OSError:
                        pass
            else:
                k = max(1, int(math.sqrt(len(peers))))
                full = set((p[0] for p in random.sample(peers, min(k, len(peers)))))
                for pid, conn in peers:
                    if pid in full:
                        frame = encode_msg(TX, body)
                    else:
                        frame = encode_msg(ANNOUNCE_TX, tx_hash)
                    self.bytes_sent += 4 + len(frame)
                    try:
                        send_msg(conn, frame)
                    except OSError:
                        pass

    def build(strategy, base_port):
        ns = [CountingNode(base_port + i, strategy) for i in range(1, 9)]
        for _n in ns:
            _n.start()
        time.sleep(0.3)
        random.seed(42)
        for _n in ns:
            others = [m for m in ns if m is not _n]
            for m in random.sample(others, 3):
                _n.connect('127.0.0.1', m.port)
        time.sleep(0.5)
        return ns
    ns_sqrt = build('sqrt', 5580)
    ns_bcast = build('broadcast', 5590)
    payload = b'bandwidth_test_' + secrets.token_bytes(64)
    ns_sqrt[0].submit_tx(payload)
    ns_bcast[0].submit_tx(payload)
    time.sleep(1.0)
    print(f'\norigin node bytes sent  sqrt-fanout : {ns_sqrt[0].bytes_sent}')
    print(f'origin node bytes sent  full broadcast: {ns_bcast[0].bytes_sent}')
    print('(sqrt fanout sends full bodies to ~sqrt(N) peers, hashes to the rest)')
    assert ns_sqrt[0].bytes_sent < ns_bcast[0].bytes_sent, 'expected sqrt-fanout to use fewer bytes than broadcast'
    print('bandwidth advantage confirmed')
    for _n in ns_sqrt:
        _n.stop()
    for _n in ns_bcast:
        _n.stop()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 10. Cleanup

    Stop all nodes from the 8-node demo (node 3 was already stopped in §9a).
    """)
    return


@app.cell
def _(nodes):
    for _n in nodes:
        if _n is not nodes[3]:
            _n.stop()
    print('all nodes stopped')
    return


if __name__ == "__main__":
    app.run()
