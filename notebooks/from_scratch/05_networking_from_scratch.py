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
    # NB05 — Networking From Scratch

    In NB03 we used `requests.post(url, json=...)`.  That is three layers stacked:
    HTTP, JSON-RPC, and the TCP socket underneath.  In this notebook we open the
    socket ourselves, design our own message frame, and watch the bytes on the wire
    with `tcpdump`.  By the end you can read an Ethereum node's protocol dump and
    know what you are seeing.

    **What we build:**
    1. A bare TCP echo server (blocking and threaded)
    2. A length-prefixed binary framing protocol (`_lib/framing.py`)
    3. A JSON-RPC 2.0 server **without HTTP** (`_lib/rpc.py`)
    4. Three failure-mode demos — timeout, oversized frame, half-closed peer
    5. A side-by-side comparison with a real Sepolia RPC endpoint

    **Prerequisites:** NB01 (keys), NB02 (signing), NB04 (toy blockchain).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1 — What we are cutting

    When you call `requests.post("https://...", json=payload)`, the following
    layers activate, bottom to top:

    | Layer | Responsibility |
    |-------|---------------|
    | TCP socket | ordered, reliable byte stream over IP |
    | TLS (HTTPS) | encryption, server authentication |
    | HTTP/1.1 | text-based request/response envelope |
    | JSON | serialise the payload to text |
    | JSON-RPC 2.0 | standardised RPC schema on top of JSON |

    In this notebook we remove HTTP, TLS, and `requests`.  We keep JSON-RPC 2.0
    because that is exactly what Ethereum nodes speak (see NB03).

    Our transport will be a raw TCP connection with a **4-byte length prefix** to
    delimit messages — a stripped-down version of what the Ethereum devp2p
    wire-protocol uses.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2 — TCP in 50 lines: the blocking echo server

    TCP gives you an ordered, reliable **byte stream** — NOT discrete messages.
    Two `send()` calls can be merged into one `recv()`; one `send()` can split
    across two `recv()`s.  This is the number-one source of bugs in custom protocol
    implementations.

    The simplest possible TCP server is a blocking echo server: it accepts one
    connection, reads whatever the client sends, and writes it straight back.
    """)
    return


@app.cell
def _():
    import socket

    def run_blocking_echo_server(port=5550):
        """Blocking echo server — DO NOT call this inside Jupyter (uses accept(), will hang)."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            print(f"listening on 127.0.0.1:{port}")
            conn, addr = srv.accept()
            print("client:", addr)
            with conn:
                while True:
                    data = conn.recv(4096)
                    if not data:
                        break
                    print(f"recv {len(data)} bytes:", data)
                    conn.sendall(data)

    # To experiment manually (three separate terminals):
    #   Terminal 1: python -c "import socket; exec(open('build_nb05.py').read()); run_blocking_echo_server()"
    #   Terminal 2: nc 127.0.0.1 5550    — type text, press Enter, watch the echo
    #   Terminal 3: sudo tcpdump -i lo -X 'port 5550'   — see the raw bytes
    #
    # We do NOT call this inside Jupyter — it would block forever waiting for accept().
    # run_blocking_echo_server()  # uncomment to run in a standalone terminal

    print("run_blocking_echo_server defined (not called — would hang the notebook)")
    return (socket,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### The three-terminal experiment (run manually)

    Open three terminal windows and do the following:

    **Terminal 1 — run the blocking server:**
    ```bash
    python3 -c "
    import socket
    def run_blocking_echo_server(port=5550):
        with socket.socket() as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(('127.0.0.1', port))
            srv.listen(1)
            print('listening on 127.0.0.1:5550')
            conn, addr = srv.accept()
            print('client:', addr)
            with conn:
                while True:
                    data = conn.recv(4096)
                    if not data: break
                    print('recv:', data)
                    conn.sendall(data)
    run_blocking_echo_server()
    "
    ```

    **Terminal 2 — connect with `nc`:**
    ```bash
    nc 127.0.0.1 5550
    ```
    Type `hello` and press Enter.  You will see `hello` echoed back.

    **Terminal 3 — capture the wire bytes:**
    ```bash
    sudo tcpdump -i lo -X 'port 5550' -c 20
    ```
    You will see the three-way handshake (SYN, SYN-ACK, ACK) and then PSH+ACK
    packets carrying your bytes.  The `-X` flag prints hex + ASCII side by side.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3 — Threaded echo server (works inside Jupyter)

    A threaded server starts in a background daemon thread so the notebook cell
    returns immediately.  Daemon threads are killed automatically when the Python
    process exits — they do not prevent `nbconvert` from finishing.
    """)
    return


@app.cell
def _(socket):
    import threading
    import time

    def run_threaded_echo_server(port):
        """Start an echo server in a daemon thread; returns immediately."""
        def serve():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("127.0.0.1", port))
                srv.listen(1)
                try:
                    srv.settimeout(5.0)
                    conn, _ = srv.accept()
                    with conn:
                        conn.settimeout(5.0)
                        while True:
                            data = conn.recv(4096)
                            if not data:
                                break
                            conn.sendall(data)
                except socket.timeout:
                    pass
        threading.Thread(target=serve, daemon=True).start()

    PORT_ECHO = 5551
    run_threaded_echo_server(PORT_ECHO)
    time.sleep(0.1)   # give the thread time to bind and listen

    # Now connect from the same notebook cell
    c = socket.socket()
    c.settimeout(2.0)
    c.connect(("127.0.0.1", PORT_ECHO))

    c.sendall(b"hello")
    c.sendall(b"world")
    time.sleep(0.05)   # let the server merge the two sends into one recv buffer
    data = c.recv(4096)
    c.close()

    print("got back:", data)
    print()
    print("Two separate sendall() calls returned as ONE recv().")
    print("TCP is a byte stream, not a message stream.")
    return threading, time


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The output is almost always `b'helloworld'` — two calls to `sendall()` merged
    into a single `recv()`.  Occasionally TCP flushes them separately and you get
    `b'hello'` then `b'world'`, but you can never predict which will happen.

    **This is the core insight**: TCP has no concept of messages.  Any protocol
    built on top of TCP must provide its own message-delimiting mechanism.  HTTP
    uses `\r\n\r\n` plus a `Content-Length` header.  WebSocket uses a binary
    length-prefix inside a small framing header.  We will use the simplest possible
    design: a 4-byte big-endian length followed by the payload bytes.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4 — `tcpdump` — what to expect

    Run this in a separate terminal **while the echo server from Step 3 is still
    alive** (within 5 seconds of the cell above executing):

    ```bash
    sudo tcpdump -i lo -X 'port 5551' -c 10
    ```

    Then reconnect manually:

    ```bash
    nc 127.0.0.1 5551
    ```

    Type `hello` and press Enter.  You will see something like:

    ```
    12:34:56.000 IP localhost.5551 > localhost.45678: Flags [P.], seq 1:6, length 5
            0x0000:  4500 002d 0000 4000 4006 0000 7f00 0001  E..-.......
            0x0010:  7f00 0001 15af b27a 0000 0001 0000 0000  .......z........
            0x0020:  5018 0200 fe40 0000 6865 6c6c 6f0a       P....@..hello.
    ```

    Breaking that down:

    | Field | Value | Meaning |
    |-------|-------|---------|
    | `Flags [P.]` | PSH + ACK | data-carrying segment, acknowledging previous |
    | `seq 1:6` | bytes 1–6 | sequence-number range of this segment |
    | `length 5` | 5 bytes | `hello` is 5 bytes; `\n` is the 6th from `nc` |
    | `6865 6c6c 6f` | hex | ASCII for `h e l l o` |

    The three-way handshake (SYN → SYN-ACK → ACK) appears first.  After you press
    Ctrl-D in `nc`, you will see FIN and FIN-ACK to close the connection.

    > Note: `sudo tcpdump` requires a password.  Run it manually — the notebook
    > intentionally does not execute `tcpdump` because it would either fail or
    > require interactive sudo.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 5 — Length-prefixed framing

    The framing contract:

    ```
    ┌──────────────────────┬────────────────────────────┐
    │  4 bytes (big-endian)│  N bytes (the payload)     │
    │  uint32 length = N   │  arbitrary bytes            │
    └──────────────────────┴────────────────────────────┘
    ```

    Two subtleties matter:

    1. **Short reads** — `sock.recv(n)` may return *fewer* than `n` bytes even
       when more are coming.  `recv_exact` loops until we have exactly what we
       asked for.

    2. **Size cap** — without `MAX_FRAME_SIZE`, a malicious peer can send
       `\xff\xff\xff\xff` (≈4 GiB) as the length field, causing your process to
       attempt a 4 GiB memory allocation and crash.  We refuse any announced length
       above 10 MB.
    """)
    return


@app.cell
def _():
    import struct

    MAX_FRAME_SIZE = 10_000_000  # 10 MB hard cap

    def send_msg(sock, payload: bytes) -> None:
        """Send payload as a 4-byte-length-prefixed frame."""
        sock.sendall(struct.pack(">I", len(payload)) + payload)

    def recv_exact(sock, n: int) -> bytes:
        """Read exactly n bytes; loop over short reads."""
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("peer closed")
            buf += chunk
        return buf

    def recv_msg(sock) -> bytes:
        """Read one length-prefixed message; raises ValueError if too large."""
        header = recv_exact(sock, 4)
        (length,) = struct.unpack(">I", header)
        if length > MAX_FRAME_SIZE:
            raise ValueError(f"message too large: {length} bytes (cap {MAX_FRAME_SIZE})")
        return recv_exact(sock, length)

    print("send_msg, recv_exact, recv_msg defined")
    print(f"MAX_FRAME_SIZE = {MAX_FRAME_SIZE:,} bytes")
    return recv_exact, recv_msg, send_msg, struct


@app.cell
def _():
    # Write to _lib/framing.py so subsequent notebooks can import it
    framing_src = '"""framing.py — length-prefixed binary framing for raw TCP sockets.\n\nEvery message is transmitted as:\n    [4-byte big-endian length][N bytes payload]\n\nFunctions\n---------\nsend_msg(sock, payload)  — frame and send a bytes payload\nrecv_exact(sock, n)      — read exactly n bytes (handles short reads)\nrecv_msg(sock)           — read one framed message; enforces MAX_FRAME_SIZE\n"""\n\nimport struct\n\nMAX_FRAME_SIZE = 10_000_000  # 10 MB hard cap — prevents 4 GB allocation attacks\n\n\ndef send_msg(sock, payload: bytes) -> None:\n    """Send *payload* as a length-prefixed frame."""\n    sock.sendall(struct.pack(">I", len(payload)) + payload)\n\n\ndef recv_exact(sock, n: int) -> bytes:\n    """Read exactly *n* bytes from *sock*, looping over short reads."""\n    buf = b""\n    while len(buf) < n:\n        chunk = sock.recv(n - len(buf))\n        if not chunk:\n            raise ConnectionError("peer closed")\n        buf += chunk\n    return buf\n\n\ndef recv_msg(sock) -> bytes:\n    """Read one length-prefixed message from *sock*.\n\n    Raises ValueError if the announced length exceeds MAX_FRAME_SIZE.\n    """\n    header = recv_exact(sock, 4)\n    (length,) = struct.unpack(">I", header)\n    if length > MAX_FRAME_SIZE:\n        raise ValueError(f"message too large: {length} bytes (cap {MAX_FRAME_SIZE})")\n    return recv_exact(sock, length)\n'
    with open('_lib/framing.py', 'w') as _f:
        _f.write(framing_src)
    print('_lib/framing.py written')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 6 — Hex-dump helper

    When debugging binary protocols, the most useful tool is a hex dump: the raw
    bytes shown as hex digits on the left and printable ASCII on the right (dots for
    non-printable bytes).  This is exactly what `tcpdump -X` and `xxd` print.
    """)
    return


@app.cell
def _(struct):
    def hexdump(data: bytes, width: int = 16) -> str:
        """Format bytes as a hex + ASCII dump, like xxd or tcpdump -X."""
        out = []
        for i in range(0, len(data), width):
            chunk = data[i : i + width]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            out.append(f"{i:04x}  {hex_part:<{width * 3}}  {ascii_part}")
        return "\n".join(out)

    # Demo: frame the string "hello world"
    payload = b"hello world"
    framed = struct.pack(">I", len(payload)) + payload
    print(hexdump(framed))
    return (hexdump,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Expected output:
    ```
    0000  00 00 00 0b 68 65 6c 6c 6f 20 77 6f 72 6c 64     ....hello world
    ```

    Reading left to right:
    - `00 00 00 0b` — length prefix, big-endian uint32 = 11 (len("hello world"))
    - `68 65 6c 6c 6f 20 77 6f 72 6c 64` — ASCII for "hello world"

    For comparison, the plan showed `42` (`0x2a`) as the payload length; with
    `"hello world"` (11 bytes = `0x0b`) you see `00 00 00 0b` instead.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 7 — JSON-RPC 2.0 server by hand (over our framing, not HTTP)

    **JSON-RPC 2.0 in six lines:**

    | Message | Shape |
    |---------|-------|
    | Request | `{"jsonrpc":"2.0","id":N,"method":"name","params":[...]}` |
    | Success response | `{"jsonrpc":"2.0","id":N,"result":...}` |
    | Error response | `{"jsonrpc":"2.0","id":N,"error":{"code":...,"message":"..."}}` |

    Real Ethereum nodes wrap this in HTTP (`Content-Type: application/json`).
    We skip HTTP entirely — the body travels directly inside our 4-byte-framed TCP
    stream.  The JSON is identical; only the transport differs.
    """)
    return


@app.cell
def _(recv_msg, send_msg, socket, threading):
    import json

    class RpcServer:
        """JSON-RPC 2.0 server over our custom framing protocol (no HTTP)."""

        def __init__(self, port: int):
            self.port = port
            self.methods = {}
            self._stop = threading.Event()
            self._srv_sock = None

        def method(self, name=None):
            """Decorator: register a callable under *name* (defaults to fn.__name__)."""
            def deco(fn):
                self.methods[name or fn.__name__] = fn
                return fn
            return deco

        def serve_forever(self):
            """Block, accepting connections, until stop() is called."""
            srv = socket.socket()
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", self.port))
            srv.listen(5)
            srv.settimeout(0.5)   # poll _stop every 0.5 s
            self._srv_sock = srv
            print(f"rpc listening on {self.port}")
            while not self._stop.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
            srv.close()

        def stop(self):
            """Signal serve_forever() to exit."""
            self._stop.set()

        def _handle(self, conn):
            """Handle one client connection: read requests, write responses."""
            with conn:
                conn.settimeout(5.0)
                try:
                    while True:
                        raw = recv_msg(conn)
                        try:
                            req = json.loads(raw)
                            fn = self.methods[req["method"]]
                            result = fn(*req.get("params", []))
                            resp = {"jsonrpc": "2.0", "id": req["id"], "result": result}
                        except Exception as e:
                            resp = {
                                "jsonrpc": "2.0",
                                "id": req.get("id") if isinstance(req, dict) else None,
                                "error": {"code": -32000, "message": str(e)},
                            }
                        send_msg(conn, json.dumps(resp).encode())
                except (ConnectionError, socket.timeout, json.JSONDecodeError, ValueError):
                    pass

    print("RpcServer class defined")
    return RpcServer, json


@app.cell
def _(RpcServer, threading, time):
    # Wire up NB04's Chain as the RPC back-end
    import sys, os
    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)

    from _lib.chain import Chain, Account
    from _lib.ecdsa import gen_private_key, priv_to_address

    _priv = gen_private_key()
    _addr = priv_to_address(_priv)
    chain = Chain({_addr: Account(balance=1000)})

    PORT_RPC = 5560
    rpc = RpcServer(PORT_RPC)

    @rpc.method("eth_getBalance")
    def get_balance(addr):
        return chain.state.get(addr, Account()).balance

    @rpc.method("eth_blockNumber")
    def block_number():
        return chain.head.number

    server_thread = threading.Thread(target=rpc.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)
    print("rpc server up, funded address:", _addr)
    return PORT_RPC, rpc


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 8 — Client and raw byte inspection

    We can now make JSON-RPC calls from Python without `requests` or HTTP — just
    our framing layer and a raw socket.
    """)
    return


@app.cell
def _(PORT_RPC, json, recv_msg, send_msg, socket):
    def rpc_call(host, port, method, params):
        """Single-shot JSON-RPC call; returns the parsed response dict."""
        s = socket.socket()
        s.settimeout(3.0)
        s.connect((host, port))
        req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }).encode()
        send_msg(s, req)
        resp_bytes = recv_msg(s)
        s.close()
        return json.loads(resp_bytes)

    bal = rpc_call("127.0.0.1", PORT_RPC, "eth_getBalance", [_addr])
    blk = rpc_call("127.0.0.1", PORT_RPC, "eth_blockNumber", [])

    print("eth_getBalance:", bal)
    print("eth_blockNumber:", blk)
    return


@app.cell
def _(PORT_RPC, hexdump, json, recv_exact, socket, struct):
    # Same call, but print every byte on the wire — the framing is visible
    s2 = socket.socket()
    s2.settimeout(3.0)
    s2.connect(("127.0.0.1", PORT_RPC))

    req_body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": [],
    }).encode()
    framed_req = struct.pack(">I", len(req_body)) + req_body

    print("SEND:")
    print(hexdump(framed_req))

    s2.sendall(framed_req)

    resp_len = struct.unpack(">I", recv_exact(s2, 4))[0]
    resp_body = recv_exact(s2, resp_len)
    s2.close()

    framed_resp = struct.pack(">I", resp_len) + resp_body
    print("\nRECV:")
    print(hexdump(framed_resp))
    return


@app.cell
def _():
    # Write _lib/rpc.py
    rpc_src = '"""rpc.py — JSON-RPC 2.0 server and client over custom length-prefixed framing.\n\nTransport: raw TCP with 4-byte big-endian length prefix (see framing.py).\nThis is intentionally NOT HTTP — we build the framing ourselves.\n\nClasses / functions\n-------------------\nRpcServer   — register methods with @rpc.method(); start with serve_forever()\nrpc_call    — single-shot client helper\n"""\n\nimport json\nimport socket\nimport threading\n\nfrom .framing import send_msg, recv_msg, recv_exact, MAX_FRAME_SIZE  # noqa: F401\n\n\nclass RpcServer:\n    """JSON-RPC 2.0 server over our custom framing protocol."""\n\n    def __init__(self, port: int):\n        self.port = port\n        self.methods: dict = {}\n        self._stop = threading.Event()\n        self._srv_sock = None\n\n    def method(self, name=None):\n        """Decorator: register a callable under *name* (defaults to function name)."""\n        def deco(fn):\n            self.methods[name or fn.__name__] = fn\n            return fn\n        return deco\n\n    def serve_forever(self):\n        """Block until stop() is called, accepting and dispatching connections."""\n        srv = socket.socket()\n        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n        srv.bind(("127.0.0.1", self.port))\n        srv.listen(5)\n        srv.settimeout(0.5)\n        self._srv_sock = srv\n        print(f"rpc listening on {self.port}")\n        while not self._stop.is_set():\n            try:\n                conn, _ = srv.accept()\n            except socket.timeout:\n                continue\n            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()\n        srv.close()\n\n    def stop(self):\n        """Signal serve_forever() to exit after its next 0.5-second poll."""\n        self._stop.set()\n\n    def _handle(self, conn):\n        """Handle one client connection: read requests, write responses."""\n        with conn:\n            conn.settimeout(5.0)\n            try:\n                while True:\n                    raw = recv_msg(conn)\n                    try:\n                        req = json.loads(raw)\n                        fn = self.methods[req["method"]]\n                        result = fn(*req.get("params", []))\n                        resp = {"jsonrpc": "2.0", "id": req["id"], "result": result}\n                    except Exception as e:\n                        resp = {\n                            "jsonrpc": "2.0",\n                            "id": req.get("id") if isinstance(req, dict) else None,\n                            "error": {"code": -32000, "message": str(e)},\n                        }\n                    send_msg(conn, json.dumps(resp).encode())\n            except (ConnectionError, socket.timeout, json.JSONDecodeError, ValueError):\n                pass\n\n\ndef rpc_call(host: str, port: int, method: str, params: list):\n    """Single-shot JSON-RPC call; returns the parsed response dict."""\n    s = socket.socket()\n    s.settimeout(3.0)\n    s.connect((host, port))\n    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()\n    send_msg(s, req)\n    resp_bytes = recv_msg(s)\n    s.close()\n    return json.loads(resp_bytes)\n'
    with open('_lib/rpc.py', 'w') as _f:
        _f.write(rpc_src)
    print('_lib/rpc.py written')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 9 — Failure modes: debug like a network engineer

    Three classic failure modes, each demonstrated and then fixed.

    ### (a) Slow-loris attack — client sends only the length header then stalls

    Without `settimeout`, the server's `recv_exact` blocks indefinitely waiting for
    the body.  The fix is a bounded timeout on the connection socket.
    """)
    return


@app.cell
def _(recv_exact, socket, threading, time):
    PORT_VICTIM_A = 5561

    def victim_a(port):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        s.settimeout(3.0)
        try:
            conn, _ = s.accept()
            conn.settimeout(2.0)   # THE FIX: bounded wait
            try:
                # Client only sent 4 bytes; recv_exact(100) will hit the timeout
                data = recv_exact(conn, 100)
                print("unexpectedly got data:", data)
            except (socket.timeout, ConnectionError) as e:
                print(f"caught expected: {type(e).__name__}: {e}")
            conn.close()
        except socket.timeout:
            print("victim_a: no connection received (timeout)")
        finally:
            s.close()

    threading.Thread(target=victim_a, args=(PORT_VICTIM_A,), daemon=True).start()
    time.sleep(0.1)

    # Attacker: sends only the 4-byte length header, then goes silent
    atk_a = socket.socket()
    atk_a.connect(("127.0.0.1", PORT_VICTIM_A))
    atk_a.sendall(b"\x00\x00\x00\xff")  # claims 255 bytes incoming; sends none
    time.sleep(3.0)   # hold the connection open without sending the body
    atk_a.close()
    print("attacker disconnected; server stayed alive thanks to settimeout(2.0)")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### (b) Bad length — client announces a 4 GiB frame

    Without `MAX_FRAME_SIZE`, the server calls `recv_exact(sock, 0xffffffff)`,
    which triggers a 4 GiB `bytearray` allocation and usually crashes the process.
    `recv_msg` rejects any announced length above 10 MB before allocating anything.
    """)
    return


@app.cell
def _(recv_msg, socket, threading, time):
    PORT_VICTIM_B = 5562

    def victim_b(port):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        s.settimeout(3.0)
        try:
            conn, _ = s.accept()
            conn.settimeout(2.0)
            try:
                payload = recv_msg(conn)   # uses MAX_FRAME_SIZE cap
                print("got payload of", len(payload))
            except ValueError as e:
                print(f"rejected oversized frame: {e}")
            conn.close()
        except socket.timeout:
            print("victim_b: no connection received (timeout)")
        finally:
            s.close()

    threading.Thread(target=victim_b, args=(PORT_VICTIM_B,), daemon=True).start()
    time.sleep(0.1)

    atk_b = socket.socket()
    atk_b.connect(("127.0.0.1", PORT_VICTIM_B))
    atk_b.sendall(b"\xff\xff\xff\xff")   # announces ~4 GiB
    time.sleep(0.5)
    atk_b.close()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### (c) Half-closed peer — client sends an incomplete frame then shuts down the write half

    `recv_exact` detects the empty `recv()` return (EOF) and raises `ConnectionError`
    instead of hanging forever.
    """)
    return


@app.cell
def _(recv_msg, socket, threading, time):
    PORT_VICTIM_C = 5563

    def victim_c(port):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        s.settimeout(3.0)
        try:
            conn, _ = s.accept()
            try:
                payload = recv_msg(conn)
                print("got:", payload)
            except ConnectionError as e:
                print(f"clean failure on EOF: {e}")
            conn.close()
        except socket.timeout:
            print("victim_c: no connection received (timeout)")
        finally:
            s.close()

    threading.Thread(target=victim_c, args=(PORT_VICTIM_C,), daemon=True).start()
    time.sleep(0.1)

    atk_c = socket.socket()
    atk_c.connect(("127.0.0.1", PORT_VICTIM_C))
    atk_c.sendall(b"\x00\x00\x00\x10" + b"abc")   # claims 16 bytes, sends only 3
    atk_c.shutdown(socket.SHUT_WR)                     # half-close the write side
    time.sleep(0.5)
    atk_c.close()
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 10 — Compare to real Ethereum

    Real Ethereum JSON-RPC endpoints use **HTTP** as the transport (the request body
    is wrapped in `POST / HTTP/1.1 ... Content-Type: application/json`).  The
    JSON-RPC body itself is identical to what we built above — only the framing
    differs.

    Let us call a public Sepolia RPC node directly, just as we did in NB03:
    """)
    return


@app.cell
def _():
    import requests

    resp = requests.post(
        "https://ethereum-sepolia-rpc.publicnode.com",
        json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
        timeout=10,
    )
    print("HTTP status:", resp.status_code)
    print("JSON body:  ", resp.json())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The `result` field contains the current Sepolia block number as a hex string
    (e.g. `"0x7b1a4f"`).

    **Transport comparison:**

    | | Our NB05 server | Real Ethereum node |
    |---|---|---|
    | Transport | Raw TCP | TCP (usually TLS) |
    | Framing | 4-byte big-endian length | HTTP `Content-Length` header |
    | Encoding | UTF-8 JSON body | UTF-8 JSON body |
    | Protocol | JSON-RPC 2.0 | JSON-RPC 2.0 |

    The peer-to-peer protocol between Ethereum nodes (devp2p / `eth/68`) is closer
    to what we built: a binary framed TCP connection with RLP-encoded messages rather
    than JSON.  It also adds ECDH key exchange and AES-256 encryption on the session.
    We build a simplified version of that in NB06.

    For now, appreciate that the core mechanism — write a length, then write the
    payload; read a length, then read exactly that many bytes — is universal across
    custom binary protocols.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 11 — Cleanup
    """)
    return


@app.cell
def _(rpc, time):
    rpc.stop()
    # Give the serve_forever loop one poll cycle to notice the stop signal
    time.sleep(0.6)
    print("rpc server stopped")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Summary

    | Concept | What we learned |
    |---------|----------------|
    | TCP byte stream | Two `send()` calls can merge into one `recv()` |
    | Length-prefix framing | 4-byte uint32 + payload; `recv_exact` handles short reads |
    | Size cap | `MAX_FRAME_SIZE = 10 MB` prevents 4 GB allocation attacks |
    | JSON-RPC 2.0 | `{jsonrpc, id, method, params}` / `{jsonrpc, id, result/error}` |
    | Slow-loris defence | `conn.settimeout()` bounds how long we wait for a body |
    | Half-close | `recv()` returns `b"\"` on EOF; detect and raise `ConnectionError` |
    | Real Ethereum | Same JSON-RPC body, HTTP framing instead of our 4-byte prefix |

    **Files produced:**
    - `_lib/framing.py` — `send_msg`, `recv_exact`, `recv_msg`, `MAX_FRAME_SIZE`
    - `_lib/rpc.py` — `RpcServer`, `rpc_call`

    **Next:** NB06 builds on this foundation to add the devp2p handshake — ECDH
    key exchange and session encryption over the same raw TCP transport.
    """)
    return


if __name__ == "__main__":
    app.run()
