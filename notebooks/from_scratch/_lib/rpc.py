"""rpc.py — JSON-RPC 2.0 server and client over custom length-prefixed framing.

Transport: raw TCP with 4-byte big-endian length prefix (see framing.py).
This is intentionally NOT HTTP — we build the framing ourselves.

Classes / functions
-------------------
RpcServer   — register methods with @rpc.method(); start with serve_forever()
rpc_call    — single-shot client helper
"""

import json
import socket
import threading

from .framing import send_msg, recv_msg, recv_exact, MAX_FRAME_SIZE  # noqa: F401


class RpcServer:
    """JSON-RPC 2.0 server over our custom framing protocol."""

    def __init__(self, port: int):
        self.port = port
        self.methods: dict = {}
        self._stop = threading.Event()
        self._srv_sock = None

    def method(self, name=None):
        """Decorator: register a callable under *name* (defaults to function name)."""
        def deco(fn):
            self.methods[name or fn.__name__] = fn
            return fn
        return deco

    def serve_forever(self):
        """Block until stop() is called, accepting and dispatching connections."""
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.port))
        srv.listen(5)
        srv.settimeout(0.5)
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
        """Signal serve_forever() to exit after its next 0.5-second poll."""
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


def rpc_call(host: str, port: int, method: str, params: list):
    """Single-shot JSON-RPC call; returns the parsed response dict."""
    s = socket.socket()
    s.settimeout(3.0)
    s.connect((host, port))
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    send_msg(s, req)
    resp_bytes = recv_msg(s)
    s.close()
    return json.loads(resp_bytes)
