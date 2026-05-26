# From-Scratch Blockchain Notebooks Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sequence of self-contained Jupyter notebooks that teach Ethereum-style blockchain mechanics by implementing every important primitive from scratch in Python — keys, signatures, RLP, hashing, a toy chain, **real-socket networking with debugging**, a P2P node protocol, fork choice, a Merkle-Patricia trie, and a toy EVM. Stops just before real Solidity smart-contract development (the existing `blockchain_primer/` covers that).

**v2 changes vs v1:**
- Networking is now **three notebooks** (foundations → P2P protocol → fork choice) using **real TCP sockets**, not Flask. Includes hands-on debugging with `tcpdump`, `netcat`, hex dumps, and Wireshark.
- Each network notebook teaches one realistic failure mode (partial reads, peer disconnects, fork races).
- MPT notebook now hashes RLP-encoded nodes (closer to real Ethereum) rather than a hand-waved separator.
- EVM notebook adds a final cell that reads real deployed bytecode from the existing `blockchain_primer/` cache.

**Architecture:**
- New top-level directory: `notebooks/from_scratch/`.
- Each notebook is **standalone and runnable top-to-bottom** with `uv run jupyter lab` and a small set of pinned libs.
- Notebooks share `notebooks/from_scratch/_lib/` — but **the notebook that introduces a concept also writes the module** (via `%%writefile`), so the reader sees the code first, then later notebooks `import` it.
- Pedagogical structure per notebook: motivation → minimal theory → built-from-scratch implementation, cell by cell → comparison against a real reference (MetaMask, Etherscan, the `rlp` package, `tcpdump`) → exercises.
- **Audience:** absolute beginner to crypto/networking, comfortable with Python and the command line.

**Tech Stack:**
- Python 3.11+, Jupyter, `uv`
- `coincurve` (secp256k1), `pycryptodome` (keccak256), `rlp` (reference comparison only), `requests`
- **Standard-library `socket`, `selectors`, `struct`, `asyncio`** for the networking notebooks — no Flask, no FastAPI
- `matplotlib` for plots
- External CLI tools used for debugging: `netcat` (`nc`), `tcpdump`, optionally Wireshark — installed by the user on their OS

---

## File Structure

```
notebooks/from_scratch/
├── README.md
├── _lib/
│   ├── __init__.py
│   ├── keccak.py          # NB01
│   ├── ecdsa.py           # NB01 + NB02
│   ├── rlp_min.py         # NB02
│   ├── framing.py         # NB05 — length-prefixed message I/O
│   ├── rpc.py             # NB05 — JSON-RPC over our framing
│   ├── peer.py            # NB06 — P2P peer protocol
│   ├── chain.py           # NB04 — toy chain (extracted for reuse)
│   ├── trie.py            # NB08
│   └── evm.py             # NB09
├── 00_foundations.ipynb
├── 01_keys_and_addresses.ipynb
├── 02_signing_a_transaction.ipynb
├── 03_broadcast_to_sepolia.ipynb           # optional
├── 04_toy_blockchain.ipynb                 # single-node, no networking
├── 05_networking_from_scratch.ipynb        # sockets, framing, JSON-RPC, debugging
├── 06_p2p_node_protocol.ipynb              # real TCP peers, handshake, gossip
├── 07_fork_choice_and_reorgs.ipynb         # competing chains, longest-chain rule
├── 08_merkle_patricia_trie.ipynb
└── 09_toy_evm.ipynb
```

Ten notebooks. Each does one thing well.

---

## Task 0: Series scaffolding

**Files:**
- Create: `notebooks/from_scratch/README.md`
- Create: `notebooks/from_scratch/_lib/__init__.py` (empty)
- Modify: root `pyproject.toml`

- [ ] **Step 1: Create directory layout**

```bash
mkdir -p notebooks/from_scratch/_lib
touch notebooks/from_scratch/_lib/__init__.py
```

- [ ] **Step 2: Add deps to root `pyproject.toml`**

Under `[project.optional-dependencies]`:

```toml
from-scratch = [
  "coincurve>=19.0",
  "pycryptodome>=3.20",
  "rlp>=4.0",
  "requests>=2.31",
  "jupyterlab>=4.0",
  "matplotlib>=3.8",
]
```

Then: `uv sync --extra from-scratch`

- [ ] **Step 3: Write `notebooks/from_scratch/README.md`**

```markdown
# Blockchain From Scratch

A 10-notebook series that builds every important Ethereum primitive — including the network layer — by hand in Python. No web3.py, no Flask, no shortcuts. Stops just before real Solidity development (see `../blockchain_primer/`).

## Order

| # | Notebook | What you build |
|---|----------|----------------|
| 00 | Foundations | Bytes, hex, big-ints, mod arithmetic |
| 01 | Keys & Addresses | secp256k1 keygen, keccak256, Ethereum addresses |
| 02 | Signing a Transaction | RLP, EIP-1559 tx, ECDSA sign + recover |
| 03 | Broadcast to Sepolia *(optional)* | Send your hand-signed tx to a real testnet |
| 04 | Toy Blockchain | Blocks, state, parent-hash linking, validation |
| 05 | Networking From Scratch | TCP sockets, length-prefixed framing, JSON-RPC by hand, **debugging with `nc` and `tcpdump`** |
| 06 | P2P Node Protocol | Real TCP peer connections, handshake, sqrt-fanout gossip |
| 07 | Fork Choice & Reorgs | Competing chains, longest-chain rule, debugging reorgs |
| 08 | Merkle-Patricia Trie | State root + inclusion proofs (RLP-hashed nodes) |
| 09 | Toy EVM | Interpreter for ~25 opcodes, reads real deployed bytecode |

## Setup

```bash
uv sync --extra from-scratch
uv run jupyter lab notebooks/from_scratch/
```

You also need these CLI tools installed for the networking notebooks (NB05+):
- `nc` (netcat) — usually preinstalled
- `tcpdump` — `sudo apt install tcpdump` on Debian/Ubuntu
- Optional: Wireshark for pretty packet dissection

Run notebooks **in order** — later ones import code defined earlier into `_lib/`.
```

- [ ] **Step 4: Commit**

```bash
git add notebooks/from_scratch/ pyproject.toml uv.lock
git commit -m "chore(from-scratch): scaffold notebook series"
```

---

## Task 1: NB00 — Foundations

**Files:** Create `notebooks/from_scratch/00_foundations.ipynb`

Identical to v1. Verbatim:

- [ ] **Step 1: "Why this notebook"** — markdown framing.
- [ ] **Step 2: "Bytes and hex"** — `bytes`, `.hex()`, `int.to_bytes`/`from_bytes`.
- [ ] **Step 3: "Hash functions, intuitively"** — `hashlib.sha256`, avalanche demo.
- [ ] **Step 4: "Modular arithmetic"** — `% p`, `pow(a, -1, p)`, secp256k1 field prime.
- [ ] **Step 5: "Randomness"** — `secrets.randbits`, why `random` is unsafe.
- [ ] **Step 6: "Endianness, briefly"** *(new for v2)* — big-endian vs little-endian; Ethereum/network protocols use big-endian; demo with `struct.pack(">I", 1234)` vs `<I`. This sets up NB05 framing.

Code:

```python
import struct
struct.pack(">I", 1234).hex()   # '000004d2' — big endian, network order
struct.pack("<I", 1234).hex()   # 'd2040000' — little endian
```

- [ ] **Step 7: Commit**

```bash
git add notebooks/from_scratch/00_foundations.ipynb
git commit -m "feat(from-scratch): NB00 foundations"
```

---

## Task 2: NB01 — Keys & Addresses

**Files:**
- Create: `notebooks/from_scratch/01_keys_and_addresses.ipynb`
- Create: `notebooks/from_scratch/_lib/keccak.py`
- Create: `notebooks/from_scratch/_lib/ecdsa.py` (keygen + derivation)

Same as v1. Steps:

- [ ] **Step 1: "What is an account?"** — markdown framing.
- [ ] **Step 2: keccak256 from `pycryptodome`** + sanity assertion (`keccak256(b"")`).
- [ ] **Step 3: Export keccak to `_lib/keccak.py`** with `%%writefile`.
- [ ] **Step 4: "secp256k1 — the curve"** — markdown calling out that we delegate curve math to `coincurve`.
- [ ] **Step 5: `gen_private_key()`** — rejection sampling against `SECP256K1_N`.
- [ ] **Step 6: Derive public key** via `coincurve.PrivateKey`.
- [ ] **Step 7: Derive address** — `keccak256(pub_xy)[-20:]`.
- [ ] **Step 8: Known-vector check** — `priv = 0x...01` → `0x7e5f4552091a69125d5dfcb7b8c2659029395bdf`.
- [ ] **Step 9: Export to `_lib/ecdsa.py`** (gen_private_key, priv_to_pub, priv_to_address).
- [ ] **Step 10: Exercises** — generate 5 addresses; import a MetaMask dev key and verify.
- [ ] **Step 11: Commit**

```bash
git add notebooks/from_scratch/01_keys_and_addresses.ipynb notebooks/from_scratch/_lib/keccak.py notebooks/from_scratch/_lib/ecdsa.py
git commit -m "feat(from-scratch): NB01 keys, keccak, addresses"
```

---

## Task 3: NB02 — Signing a Transaction

**Files:**
- Create: `notebooks/from_scratch/02_signing_a_transaction.ipynb`
- Create: `notebooks/from_scratch/_lib/rlp_min.py`
- Modify: `notebooks/from_scratch/_lib/ecdsa.py` — add `sign_digest`, `recover_address`

- [ ] **Step 1: "What is a transaction, byte-for-byte"** — markdown framing.
- [ ] **Step 2: "RLP from scratch — the rules"** — write `rlp_encode` (ints, bytes, lists) and assert equivalence with `rlp` package on a few cases.
- [ ] **Step 3: Export `rlp_encode` to `_lib/rlp_min.py`**.
- [ ] **Step 4: "Build an EIP-1559 transaction"** — full field-by-field dict, build `unsigned_payload = b"\x02" + rlp_encode(...)`.
- [ ] **Step 5: "Hash and sign"** — `sighash = keccak256(unsigned_payload)`, `sign_recoverable`, unpack `(r, s, v)`.
- [ ] **Step 6: "Assemble signed tx + txHash"**.
- [ ] **Step 7: "Recover the signer"** — `PublicKey.from_signature_and_message`, recompute address, assert match.
- [ ] **Step 8: Export `sign_digest` + `recover_address` to `_lib/ecdsa.py`** (append).
- [ ] **Step 9: Tampering exercises** — flip a byte in `value`; flip a bit in `r`; observe failures.
- [ ] **Step 10: Commit**

```bash
git add notebooks/from_scratch/02_signing_a_transaction.ipynb notebooks/from_scratch/_lib/rlp_min.py notebooks/from_scratch/_lib/ecdsa.py
git commit -m "feat(from-scratch): NB02 RLP + EIP-1559 sign/recover"
```

---

## Task 4: NB03 — Broadcast to Sepolia (optional)

**Files:** Create `notebooks/from_scratch/03_broadcast_to_sepolia.ipynb`

Same as v1, but **renamed cells to make optionality clearer** and add a "skip me" banner at the top.

- [ ] **Step 1: "Skip if you don't have a Sepolia faucet account"** — banner cell with links to faucets and a public RPC list.
- [ ] **Step 2: "Get nonce"** — `eth_getTransactionCount`.
- [ ] **Step 3: "Get base fee"** — `eth_getBlockByNumber("latest", false)`.
- [ ] **Step 4: "Re-build + sign with real nonce/fees"** — paste from NB02, substitute live values.
- [ ] **Step 5: "Send"** — `eth_sendRawTransaction`, print Etherscan URL.
- [ ] **Step 6: "Poll receipt"** — loop `eth_getTransactionReceipt` until non-null, print block number.
- [ ] **Step 7: Commit**

```bash
git add notebooks/from_scratch/03_broadcast_to_sepolia.ipynb
git commit -m "feat(from-scratch): NB03 broadcast hand-signed tx to Sepolia"
```

---

## Task 5: NB04 — Toy Blockchain (single node)

**Files:**
- Create: `notebooks/from_scratch/04_toy_blockchain.ipynb`
- Create: `notebooks/from_scratch/_lib/chain.py` (extract for NB06+ to import)

**Goal:** A ~300-line in-process blockchain. **No networking yet** — that's NB05/06.

- [ ] **Step 1: "Minimum viable blockchain"** — markdown: what we keep (sigs, nonces, balances, parent-hash chain) and what we cut (PoS, gas, Merkle root — added in NB08).
- [ ] **Step 2: `Account` dataclass + `State = dict[str, Account]`**.
- [ ] **Step 3: `Tx` dataclass with `unsigned_bytes()` via `rlp_encode`** + `make_tx(priv, to, value, nonce)` helper.
- [ ] **Step 4: `apply_tx(state, tx)`** — verify sig (via `recover_address`), check nonce, check balance, mutate state.
- [ ] **Step 5: `Block` dataclass with `header_bytes()` and `hash()`**. Markdown note that we're concatenating tx hashes here and will replace with a Merkle root in NB08.
- [ ] **Step 6: `Chain` class** — `genesis`, `head`, `propose(txs)` (with state snapshot rollback on failure).
- [ ] **Step 7: "Demo: Alice pays Bob"** — generate two keys, fund Alice in genesis, propose a tx, print balances.
- [ ] **Step 8: Validation showcase** — three cells, each demonstrating one rejection: wrong nonce, insufficient balance, tampered sig.
- [ ] **Step 9: `verify_chain(chain)` exercise** — re-walk from genesis, re-apply all txs, assert head hash matches.
- [ ] **Step 10: Export everything to `_lib/chain.py`** with `%%writefile`.
- [ ] **Step 11: Commit**

```bash
git add notebooks/from_scratch/04_toy_blockchain.ipynb notebooks/from_scratch/_lib/chain.py
git commit -m "feat(from-scratch): NB04 toy blockchain"
```

---

## Task 6: NB05 — Networking From Scratch (the big one)

**Files:**
- Create: `notebooks/from_scratch/05_networking_from_scratch.ipynb`
- Create: `notebooks/from_scratch/_lib/framing.py`
- Create: `notebooks/from_scratch/_lib/rpc.py`

**Goal:** Strip away every networking abstraction and rebuild it. By the end, the reader has a working JSON-RPC server (like the existing `scratch/jsonrpc_demo/server.py`) but built on a **custom length-prefixed binary protocol** over raw TCP, with hands-on debugging.

### Step 1: "What we're cutting" (markdown)

> In NB03 we used `requests.post(url, json=...)`. That's three layers of magic stacked: HTTP, JSON-RPC, and the TCP socket underneath. In this notebook we open the socket ourselves, design our own message frame, and watch the bytes on the wire with `tcpdump`. By the end you can read an Ethereum node's protocol dump and understand what you're seeing.

### Step 2: "TCP in 50 lines" — echo server

Markdown teaching: TCP gives you an ordered, reliable byte stream — **not** discrete messages. Two `send()` calls can be merged into one `recv()`; one `send()` can be split across two `recv()`s. This is the #1 source of bugs in custom protocols.

```python
# Run this cell in a terminal, not in Jupyter — uses blocking accept()
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 5555))
    srv.listen(1)
    print("listening on 127.0.0.1:5555")
    conn, addr = srv.accept()
    print("client:", addr)
    with conn:
        while True:
            data = conn.recv(4096)
            if not data: break
            print(f"recv {len(data)} bytes:", data)
            conn.sendall(data)
```

Markdown: "**Open a second terminal and run:** `nc 127.0.0.1 5555` — type a message, press enter, watch the server echo it back."

### Step 3: Observe the bytes with `tcpdump`

Markdown:

> In a *third* terminal, run:
>
> ```bash
> sudo tcpdump -i lo -X 'port 5555'
> ```
>
> Send another `nc` message. You'll see the actual TCP packets — handshake (SYN, SYN-ACK, ACK), the data segment carrying your bytes, and the FIN when you close. The `-X` flag prints the hex+ASCII payload.

Include a cell with an annotated tcpdump excerpt the reader should expect to see (one SYN, one PSH+ACK with payload, one FIN+ACK).

### Step 4: The framing problem — demo the bug

Run the echo server. Have it `time.sleep(0.5)` between recv and send. From a Python client:

```python
import socket, time
s = socket.socket(); s.connect(("127.0.0.1", 5555))
s.sendall(b"hello"); s.sendall(b"world")
time.sleep(0.1)
print(s.recv(4096))  # often: b'helloworld' — TWO sends merged into ONE recv
```

Markdown: this is "TCP's no concept of messages." You need **framing**.

### Step 5: Length-prefixed framing

Markdown: simplest reliable framing — every message is `[4-byte big-endian length][N bytes payload]`.

```python
import struct

def send_msg(sock, payload: bytes) -> None:
    sock.sendall(struct.pack(">I", len(payload)) + payload)

def recv_exact(sock, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf += chunk
    return buf

def recv_msg(sock) -> bytes:
    header = recv_exact(sock, 4)
    (length,) = struct.unpack(">I", header)
    if length > 10_000_000:
        raise ValueError(f"message too large: {length}")
    return recv_exact(sock, length)
```

Markdown call-outs:
- `recv_exact` is the antidote to short-reads — `recv(n)` may return fewer than `n` bytes.
- The size cap (`10MB`) is **mandatory** — without it a malicious peer can announce `length=2**32` and exhaust your memory.

Export to `_lib/framing.py` via `%%writefile`.

### Step 6: Hex-dump helper for debugging

```python
def hexdump(data: bytes, width: int = 16) -> str:
    out = []
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append(f"{i:04x}  {hex_part:<{width*3}}  {ascii_part}")
    return "\n".join(out)

print(hexdump(struct.pack(">I", 42) + b"hello world"))
```

Expected output shown in markdown so reader knows what success looks like.

### Step 7: JSON-RPC by hand (replaces `scratch/jsonrpc_demo`)

Markdown: JSON-RPC 2.0 spec in 6 lines:
- Request: `{"jsonrpc":"2.0","id":N,"method":"name","params":[...]}`
- Response: `{"jsonrpc":"2.0","id":N,"result":...}` OR `{"jsonrpc":"2.0","id":N,"error":{"code":...,"message":"..."}}`

Server (uses our framing — not HTTP):

```python
import json, socket, threading

class RpcServer:
    def __init__(self, port: int):
        self.port = port
        self.methods = {}

    def method(self, name: str = None):
        def deco(fn):
            self.methods[name or fn.__name__] = fn
            return fn
        return deco

    def serve_forever(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.port))
        srv.listen(5)
        print(f"rpc listening on {self.port}")
        while True:
            conn, _ = srv.accept()
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        with conn:
            try:
                while True:
                    raw = recv_msg(conn)
                    req = json.loads(raw)
                    try:
                        fn = self.methods[req["method"]]
                        result = fn(*req.get("params", []))
                        resp = {"jsonrpc":"2.0", "id":req["id"], "result":result}
                    except Exception as e:
                        resp = {"jsonrpc":"2.0", "id":req.get("id"),
                                "error":{"code":-32000,"message":str(e)}}
                    send_msg(conn, json.dumps(resp).encode())
            except (ConnectionError, json.JSONDecodeError):
                pass

# Demo: wrap NB04 chain methods
from _lib.chain import Chain, Account
chain = Chain({"0xabc": Account(balance=1000)})
rpc = RpcServer(7000)

@rpc.method("eth_getBalance")
def get_balance(addr):
    return chain.state.get(addr, Account()).balance

threading.Thread(target=rpc.serve_forever, daemon=True).start()
```

### Step 8: Client + raw byte inspection

```python
def rpc_call(host, port, method, params):
    s = socket.socket(); s.connect((host, port))
    req = json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    send_msg(s, req)
    resp_bytes = recv_msg(s)
    s.close()
    return json.loads(resp_bytes)

print(rpc_call("127.0.0.1", 7000, "eth_getBalance", ["0xabc"]))
```

Then a **debugging cell**: same call but using raw sockets and `hexdump` to print every byte sent and received. Reader sees: `00 00 00 5d {"jsonrpc"...}` on the way out, similar on the way back.

Export client + server to `_lib/rpc.py`.

### Step 9: Failure modes (debugging exercises)

Three cells, each a deliberately broken scenario the reader fixes:

1. **Slow loris**: a client sends only `00 00 00 ff` then hangs. Server's `recv_exact` blocks forever. Fix: add `sock.settimeout(5)`.
2. **Bad length**: client sends `ff ff ff ff` followed by 1 byte. Without the 10MB cap, server allocates 4GB. Demonstrate the cap saves you.
3. **Half-closed**: client `shutdown(SHUT_WR)` mid-message. Server's `recv` returns `b""` mid-frame. Demonstrate `recv_exact` raises `ConnectionError` cleanly.

### Step 10: Compare to a real Ethereum RPC

```python
# This works against any public Ethereum RPC that speaks HTTP+JSON-RPC.
# Most public RPCs use HTTP, not raw framing — we use requests here for the HTTP part
# and just hand-build the JSON-RPC body, to show it's the same payload as our toy server.
import requests
resp = requests.post(
    "https://rpc.sepolia.org",
    json={"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]},
)
print(resp.json())
```

Markdown note: "Real Ethereum RPCs use HTTP framing instead of our 4-byte length prefix. Same JSON-RPC body, different transport. The devp2p protocol (peer-to-peer between nodes) uses a fancier framed binary protocol with encryption — see the `eth/68` spec. We'll build a simpler version of that in NB06."

### Step 11: Commit

```bash
git add notebooks/from_scratch/05_networking_from_scratch.ipynb notebooks/from_scratch/_lib/framing.py notebooks/from_scratch/_lib/rpc.py
git commit -m "feat(from-scratch): NB05 networking — sockets, framing, JSON-RPC, debugging"
```

---

## Task 7: NB06 — P2P Node Protocol

**Files:**
- Create: `notebooks/from_scratch/06_p2p_node_protocol.ipynb`
- Create: `notebooks/from_scratch/_lib/peer.py`

**Goal:** Build a real (toy) Ethereum-style peer protocol over TCP. Nodes connect to each other, perform a handshake, then gossip transactions using sqrt-fanout.

### Step 1: "From client-server to peer-to-peer" (markdown)

> NB05 had a server and a client. In P2P, every node is **both**. Each node listens for incoming peers AND dials out to known peers. We'll build a `Node` class that does both, then run 8 nodes locally on different ports and watch a tx propagate.

### Step 2: Message types

Markdown: define a small binary protocol on top of our framing.

| Type | Code | Payload |
|------|------|---------|
| HELLO | 0x01 | `node_id (8 bytes) || port (2 bytes BE)` |
| GETPEERS | 0x02 | — |
| PEERS | 0x03 | `count (1 byte) || (ip4(4) || port(2)) * count` |
| ANNOUNCE_TX | 0x04 | `tx_hash (32 bytes)` |
| GET_TX | 0x05 | `tx_hash (32 bytes)` |
| TX | 0x06 | `tx_bytes (RLP)` |

```python
import struct

def encode_msg(msg_type: int, body: bytes) -> bytes:
    return bytes([msg_type]) + body

def decode_msg(payload: bytes) -> tuple[int, bytes]:
    return payload[0], payload[1:]
```

### Step 3: The `Node` class — listener

Markdown explains: one thread accepts incoming peers, spawns a per-peer handler thread, stores the connection in `self.peers`.

```python
import socket, threading, secrets
from _lib.framing import send_msg, recv_msg

class Node:
    def __init__(self, port: int):
        self.port = port
        self.node_id = secrets.token_bytes(8)
        self.peers: dict[bytes, socket.socket] = {}   # node_id -> sock
        self.known_addrs: set[tuple[str, int]] = set()
        self.seen_tx: set[bytes] = set()
        self.tx_pool: dict[bytes, bytes] = {}         # hash -> rlp bytes
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self.port))
        srv.listen(20)
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=self._handshake_inbound, args=(conn,), daemon=True).start()
```

### Step 4: Handshake

Both sides exchange HELLO immediately. Reject if duplicate node_id (already connected).

```python
    def _handshake_inbound(self, conn):
        payload = recv_msg(conn)
        msg_type, body = decode_msg(payload)
        if msg_type != 0x01: conn.close(); return
        peer_id = body[:8]
        peer_port = struct.unpack(">H", body[8:10])[0]
        with self.lock:
            if peer_id == self.node_id or peer_id in self.peers:
                conn.close(); return
            self.peers[peer_id] = conn
            self.known_addrs.add(("127.0.0.1", peer_port))
        # send our HELLO back
        send_msg(conn, encode_msg(0x01, self.node_id + struct.pack(">H", self.port)))
        print(f"[{self.port}] inbound peer {peer_id.hex()} from :{peer_port}")
        self._peer_loop(peer_id, conn)

    def connect(self, host: str, port: int):
        conn = socket.socket(); conn.connect((host, port))
        # send HELLO first
        send_msg(conn, encode_msg(0x01, self.node_id + struct.pack(">H", self.port)))
        payload = recv_msg(conn)
        _, body = decode_msg(payload)
        peer_id = body[:8]
        with self.lock:
            self.peers[peer_id] = conn
            self.known_addrs.add((host, port))
        print(f"[{self.port}] outbound peer {peer_id.hex()} -> :{port}")
        threading.Thread(target=self._peer_loop, args=(peer_id, conn), daemon=True).start()
```

### Step 5: Peer loop & message handling

```python
    def _peer_loop(self, peer_id: bytes, conn: socket.socket):
        try:
            while True:
                payload = recv_msg(conn)
                msg_type, body = decode_msg(payload)
                if msg_type == 0x04:    # ANNOUNCE_TX
                    self._handle_announce(peer_id, body)
                elif msg_type == 0x05:  # GET_TX
                    if body in self.tx_pool:
                        send_msg(conn, encode_msg(0x06, self.tx_pool[body]))
                elif msg_type == 0x06:  # TX
                    self._handle_tx(body)
        except (ConnectionError, OSError):
            with self.lock:
                self.peers.pop(peer_id, None)
            print(f"[{self.port}] peer {peer_id.hex()} disconnected")

    def _handle_announce(self, peer_id: bytes, tx_hash: bytes):
        if tx_hash in self.seen_tx:
            return
        # request the body from the peer that announced
        send_msg(self.peers[peer_id], encode_msg(0x05, tx_hash))

    def _handle_tx(self, tx_bytes: bytes):
        from _lib.keccak import keccak256
        h = keccak256(tx_bytes)
        if h in self.seen_tx: return
        self.seen_tx.add(h)
        self.tx_pool[h] = tx_bytes
        print(f"[{self.port}] got tx {h.hex()[:8]}…")
        self._gossip(h)
```

### Step 6: Sqrt-fanout gossip

Markdown: when we have a new tx, send the full body to ~√(peer_count) peers and an ANNOUNCE_TX (just the hash) to all others — exactly what `eth/68` does. This bounds bandwidth at scale.

```python
    def _gossip(self, tx_hash: bytes):
        import math, random
        with self.lock:
            peers = list(self.peers.items())
        if not peers: return
        k = max(1, int(math.sqrt(len(peers))))
        full_recipients = set(p[0] for p in random.sample(peers, k))
        for pid, conn in peers:
            try:
                if pid in full_recipients:
                    send_msg(conn, encode_msg(0x06, self.tx_pool[tx_hash]))
                else:
                    send_msg(conn, encode_msg(0x04, tx_hash))
            except OSError:
                pass

    def submit_tx(self, tx_bytes: bytes):
        from _lib.keccak import keccak256
        h = keccak256(tx_bytes)
        self.seen_tx.add(h); self.tx_pool[h] = tx_bytes
        self._gossip(h)
```

Export everything to `_lib/peer.py`.

### Step 7: 8-node demo

Spin up 8 nodes on ports 7001–7008. Connect them in a partial mesh:

```python
nodes = [Node(7000 + i) for i in range(1, 9)]
for n in nodes: n.start()
import time; time.sleep(0.2)

# each node connects to 3 random others
import random
for n in nodes:
    others = [m for m in nodes if m is not n]
    for m in random.sample(others, 3):
        try: n.connect("127.0.0.1", m.port)
        except Exception: pass

time.sleep(0.5)
print("peer counts:", [len(n.peers) for n in nodes])
```

Then submit a tx at node 0, wait, observe all 8 nodes have it:

```python
nodes[0].submit_tx(b"fake_tx_payload_1234")
time.sleep(0.5)
print("nodes that have the tx:",
      [n.port for n in nodes if b"fake_tx_payload_1234" in n.tx_pool.values()])
```

### Step 8: tcpdump on the gossip

Markdown:

> In a separate terminal, run:
> ```bash
> sudo tcpdump -i lo -X 'tcp portrange 7001-7008' -c 30
> ```
> Submit a tx in the notebook. You'll see HELLO frames during connect, then ANNOUNCE_TX (`04 ` followed by 32 bytes) and TX (`06 ` followed by the payload) flying between ports.

### Step 9: Debugging exercises

1. **Kill a node mid-gossip** — close one node's listener, observe `peer disconnected` messages on the others. Verify the network still propagates.
2. **Drop the size cap** in `framing.recv_msg`. Connect a malicious "node" that sends `ff ff ff ff` — show that without the cap, memory explodes.
3. **Bandwidth comparison**: count bytes-per-message in two runs — one with sqrt-fanout (current), one with full-broadcast (send `TX` to every peer always). Plot the difference for N=8 nodes.

### Step 10: Commit

```bash
git add notebooks/from_scratch/06_p2p_node_protocol.ipynb notebooks/from_scratch/_lib/peer.py
git commit -m "feat(from-scratch): NB06 P2P node protocol over real TCP"
```

---

## Task 8: NB07 — Fork Choice & Reorgs

**Files:**
- Create: `notebooks/from_scratch/07_fork_choice_and_reorgs.ipynb`
- Modify: `notebooks/from_scratch/_lib/peer.py` — add BLOCK / GET_BLOCK / GET_HEAD message types

**Goal:** Extend NB06's P2P node to gossip *blocks*, handle competing histories, and implement the longest-chain rule with reorg debugging.

### Step 1: "What is a fork?" (markdown)

Two nodes can each build a different next block at the same height (network latency, validator disagreement, partition). Both are valid. The chain protocol must pick a winner deterministically. Bitcoin and pre-Merge Ethereum: longest chain. Post-Merge Ethereum: more nuanced (LMD-GHOST + Casper). We'll implement the simple longest-chain rule.

### Step 2: Extend the protocol

Add three message types to `_lib/peer.py`:

| Type | Code | Payload |
|------|------|---------|
| GET_HEAD | 0x10 | — |
| HEAD | 0x11 | `block_number (4 BE) || block_hash (32)` |
| GET_BLOCK | 0x12 | `block_number (4 BE)` |
| BLOCK | 0x13 | `rlp_encoded_block` |

Markdown: walk through how a node uses these to sync — ask GET_HEAD on connect, if peer's number > ours, GET_BLOCK each missing one.

### Step 3: Block serialization

Add `to_bytes` / `from_bytes` to `Block` (use `rlp_encode` on its fields). Add to `_lib/chain.py`.

### Step 4: Wire blocks into `Node`

In `_lib/peer.py`, add a `chain: Chain` attribute and handlers:

```python
def _handle_get_head(self, conn):
    blk = self.chain.head
    send_msg(conn, encode_msg(0x11,
        struct.pack(">I", blk.number) + blk.hash()))

def _on_new_block(self, blk_bytes: bytes):
    from _lib.chain import Block
    blk = Block.from_bytes(blk_bytes)
    if blk.number != self.chain.head.number + 1: return   # too simplistic; expand below
    if blk.parent_hash != self.chain.head.hash(): return
    # validate by re-applying txs
    snap = copy.deepcopy(self.chain.state)
    try:
        for t in blk.txs: apply_tx(self.chain.state, t)
        self.chain.blocks.append(blk)
        self._gossip_block(blk)
    except AssertionError:
        self.chain.state = snap
```

### Step 5: The naive sync — and its bug

Demo: two nodes, both with identical genesis. Node A proposes block 1. Node B proposes a *different* block 1. Both connect. Run `request_head` on each. Show that neither adopts the other — both see "block_number same as ours, ignore". This is the **fork** condition.

### Step 6: Longest-chain rule

Add fork resolution. When a peer's `number > ours`, walk back from their head until you find a common ancestor, then rewind our chain and re-apply theirs.

```python
def _try_sync(self, peer_id):
    conn = self.peers[peer_id]
    send_msg(conn, encode_msg(0x10, b""))
    payload = recv_msg(conn)
    _, body = decode_msg(payload)
    peer_num = struct.unpack(">I", body[:4])[0]
    peer_head_hash = body[4:36]
    if peer_num <= self.chain.head.number:
        return False
    # fetch blocks until common ancestor
    needed = []
    cur_num = peer_num
    cur_hash = peer_head_hash
    while True:
        send_msg(conn, encode_msg(0x12, struct.pack(">I", cur_num)))
        _, blk_bytes_body = decode_msg(recv_msg(conn))
        blk = Block.from_bytes(blk_bytes_body)
        needed.append(blk)
        if cur_num <= self.chain.head.number and \
           cur_num < len(self.chain.blocks) and \
           self.chain.blocks[cur_num].hash() == blk.hash():
            # found common ancestor
            break
        cur_num -= 1
        cur_hash = blk.parent_hash
        if cur_num == 0: break
    # rewind
    common = needed[-1].number
    rewound = self.chain.blocks[common+1:]
    self.chain.blocks = self.chain.blocks[:common+1]
    self.chain.state = self._replay_from_genesis(self.chain.blocks)
    # apply peer chain
    for blk in reversed(needed[:-1]):
        for t in blk.txs: apply_tx(self.chain.state, t)
        self.chain.blocks.append(blk)
    print(f"[{self.port}] REORG: dropped {len(rewound)} block(s), applied {len(needed)-1}")
    return True
```

Markdown explains every step. The `_replay_from_genesis` helper re-runs all txs from block 1 — slow but correct; real nodes keep state snapshots.

### Step 7: Reorg demo with verbose logging

Spin up 2 nodes. Disconnect them (don't connect). Have each propose 3 different blocks. Print both heads. Connect them. Watch the reorg fire on the shorter-chain node. Print both heads — should now match.

Include a `dump_chain(node)` helper that prints `block_number, block_hash[:8], parent_hash[:8], tx_count` for every block — visual aid for understanding what changed.

### Step 8: Debugging exercises

1. **Causal reorg storm**: 3 nodes, each builds 2 different blocks at the same height. Connect them in a triangle simultaneously. Trace the messages with the per-node print logs and explain which node ended up with which chain.
2. **Invalid block defense**: have a node send a block with a tampered tx signature. Verify the receiving node rejects it and doesn't reorg.
3. **Split brain**: partition the network (close some peer connections), let each side mine 5 blocks, heal the partition. Watch the shorter side reorg.

### Step 9: "Why real Ethereum is harder" (markdown)

Closing note: real Ethereum uses LMD-GHOST + Casper FFG — validators *vote* on heads with weighted attestations, finality is checkpoint-based, and >⅔ stake voting locks blocks irreversibly. We've built the spine: blocks with parent-hashes form a tree, you pick a tip, you can reorg. The "which tip wins" rule is what consensus algorithms swap in.

### Step 10: Commit

```bash
git add notebooks/from_scratch/07_fork_choice_and_reorgs.ipynb notebooks/from_scratch/_lib/peer.py notebooks/from_scratch/_lib/chain.py
git commit -m "feat(from-scratch): NB07 fork choice + reorg debugging"
```

---

## Task 9: NB08 — Merkle-Patricia Trie

**Files:**
- Create: `notebooks/from_scratch/08_merkle_patricia_trie.ipynb`
- Create: `notebooks/from_scratch/_lib/trie.py`

**Goal:** Build a simplified MPT that hashes RLP-encoded nodes (closer to real Ethereum), produce a `stateRoot`, generate and verify inclusion proofs.

### Step 1: "Why a trie?" (markdown)

- We need a 32-byte commitment over the whole state.
- We need *inclusion proofs* without sending the whole state.
- Re-hashing the whole state on every change is O(n) — a trie makes it O(log n).

### Step 2: Binary Merkle tree first (warm-up)

Implement `merkle_root` and `merkle_proof` over a list of leaves using just keccak256. Demo with 8 leaves; verify proof at index 3; tamper a leaf and watch verification fail.

(Same code as v1 — proven to teach the proof concept.)

### Step 3: "Why MPT instead?"

Markdown: binary Merkle trees commit to *lists*; state is a *map* (address → account). We need a Merkle structure keyed by arbitrary bytes. MPT = radix-16 trie + Merkle hashing at every node.

### Step 4: Simplified MPT — radix-16 trie

Code: same as v1 (Node with `children: dict[int, Node]` and `value`, `put`, `get`).

### Step 5: Hash with RLP (not separator)

**Key v2 improvement.** Hash each node as RLP-encoded `[child_hashes_list, value]`:

```python
from _lib.rlp_min import rlp_encode

def hash_node(node: Node) -> bytes:
    children = [hash_node(node.children[i]) if i in node.children else b""
                for i in range(16)]
    encoded = rlp_encode([children, node.value or b""])
    return keccak256(encoded)
```

Markdown note: real Ethereum has 4 node types (empty, leaf, extension, branch) and uses HP-encoded path prefixes — we're skipping that for clarity. Our hash will not match mainnet, but the *idea* (RLP → keccak → up the tree) is correct.

### Step 6: Build a state trie

```python
t = Trie()
t.put(addr_to_bytes("0xaaa...aaa"), (100).to_bytes(8, "big"))
t.put(addr_to_bytes("0xbbb...bbb"), (250).to_bytes(8, "big"))
print("stateRoot:", hash_node(t.root).hex())

t.put(addr_to_bytes("0xaaa...aaa"), (101).to_bytes(8, "big"))
print("new root: ", hash_node(t.root).hex())
```

### Step 7: Inclusion proof

Implement `prove(key)` returning the sibling-hash list along the path, and `verify(key, value, proof, root)`. Demo a passing proof and a tampered-value failure.

### Step 8: Wire into the toy chain (preview)

Markdown only: show how `Block.header_bytes` from NB04 could now include `hash_node(state_trie.root)` as `stateRoot`. Optional refactor exercise — don't break previous notebooks.

### Step 9: Export to `_lib/trie.py`** and commit.

```bash
git add notebooks/from_scratch/08_merkle_patricia_trie.ipynb notebooks/from_scratch/_lib/trie.py
git commit -m "feat(from-scratch): NB08 MPT + Merkle proofs"
```

---

## Task 10: NB09 — Toy EVM

**Files:**
- Create: `notebooks/from_scratch/09_toy_evm.ipynb`
- Create: `notebooks/from_scratch/_lib/evm.py`

**Goal:** Stack-machine interpreter for ~25 opcodes. Run hand-written bytecode. **New v2 final cell:** read real deployed bytecode from the existing `blockchain_primer/cache/` and disassemble its first 50 opcodes.

### Step 1: "What is the EVM" (markdown)

Stack machine, 1024 × 256-bit stack, byte-addressable memory, persistent storage, ~140 opcodes.

### Step 2: Opcode table

Markdown table for the ~25 we'll implement (STOP, ADD, MUL, SUB, DIV, MOD, LT, GT, EQ, ISZERO, AND, OR, NOT, POP, MLOAD, MSTORE, MSTORE8, SLOAD, SSTORE, JUMP, JUMPI, JUMPDEST, PC, PUSH1..PUSH32, DUP1, SWAP1, RETURN).

### Step 3: Interpreter skeleton

`EVM` class with `code`, `pc`, `stack`, `memory: bytearray`, `storage: dict`. `step()` dispatches on opcode. Split across 4 cells: arithmetic, stack/memory, storage, control flow. (Same as v1.)

### Step 4: Hand-assembled demo — `(2 + 3) * 4`

```python
code = bytes.fromhex("6004600360020102 00".replace(" ", ""))
evm = EVM(code); evm.run()
assert evm.stack == [20]
```

Walk through pc-by-pc in markdown.

### Step 5: Storage demo + JUMPI loop summing 1..10

(Same as v1.)

### Step 6: Disassembler

```python
OPCODES = {0x00: "STOP", 0x01: "ADD", 0x02: "MUL", ...}  # full table

def disasm(code: bytes) -> list[str]:
    out, pc = [], 0
    while pc < len(code):
        op = code[pc]
        if 0x60 <= op <= 0x7f:
            n = op - 0x5f
            data = code[pc+1:pc+1+n].hex()
            out.append(f"{pc:04x}  PUSH{n} 0x{data}")
            pc += 1 + n
        else:
            out.append(f"{pc:04x}  {OPCODES.get(op, f'?? (0x{op:02x})')}")
            pc += 1
    return out
```

### Step 7: Read real bytecode (v2 NEW)

```python
import json, pathlib
art = json.loads(pathlib.Path("../blockchain_primer/cache/forge_out/Counter.sol/Counter.json").read_text())
deployed = bytes.fromhex(art["deployedBytecode"]["object"].removeprefix("0x"))
print(f"Real Counter contract: {len(deployed)} bytes")
for line in disasm(deployed)[:50]:
    print(line)
```

Markdown: "You're now reading the actual EVM instructions of a contract Solidity compiled. You won't recognize all opcodes — Solidity emits LOG, CALL, REVERT, CODECOPY, KECCAK256 etc. that we didn't implement. But you can see the dispatcher pattern at the top: PUSH4 (selector), EQ, PUSH2 (jump dest), JUMPI."

(Note for executor: the path `../blockchain_primer/cache/forge_out/Counter.sol/Counter.json` exists if the primer's `s05_deploy.py` has been run. If not, fall back to a hardcoded short bytecode hex string in the cell — provide both and let the reader pick.)

### Step 8: "What's not here" (markdown)

CALL/RETURN across contracts, gas accounting, CREATE, LOG, precompiles, ~115 more opcodes. The spine is built; this is where `notebooks/blockchain_primer/` takes over.

### Step 9: Export to `_lib/evm.py`** and commit.

```bash
git add notebooks/from_scratch/09_toy_evm.ipynb notebooks/from_scratch/_lib/evm.py
git commit -m "feat(from-scratch): NB09 toy EVM + real bytecode disassembly"
```

---

## Task 11: Wrap-up

- [ ] **Step 1: Update `notebooks/README.md`** (if it exists) to cross-link `from_scratch/` and `blockchain_primer/`.

- [ ] **Step 2: Append "What's next" to `notebooks/from_scratch/README.md`**: pointer to the primer for Solidity + Foundry, then to Cyfrin Updraft / Ethernaut / Damn Vulnerable DeFi for real smart-contract dev. Also note where each notebook's concept reappears in mainnet Ethereum (e.g., "the gossip in NB06 is `eth/68`; the trie in NB08 becomes the state trie in Geth's `core/state`").

- [ ] **Step 3: Commit**

```bash
git add notebooks/from_scratch/README.md notebooks/README.md
git commit -m "docs(from-scratch): cross-link series and add next-steps"
```

---

## Self-Review Notes

- **Spec coverage:** all 6 original mocks + foundations + broadcast + the user's networking deepening (split into NB05 networking-foundations, NB06 P2P-protocol, NB07 fork-choice). Covered by Tasks 1–10.
- **Networking depth:** real TCP sockets throughout NB05–07. Three debugging tools appear: `nc` (manual peer simulation), `tcpdump` (wire inspection), `hexdump` (in-notebook byte view). Three realistic failure modes per network notebook.
- **From-scratch where it matters:** RLP, address derivation, signature recovery, blockchain validation, custom binary protocol, P2P handshake, gossip, fork choice, MPT, EVM — all hand-implemented. Only secp256k1 curve math is delegated (with explanation).
- **Stopping point:** task 10 ends at the EVM interpreter reading real bytecode. No Solidity authoring, no Foundry, no deployment — that's the existing `blockchain_primer/`.
- **Total notebooks:** 10. Reading time ≈ 1–2 hours each; coding-along ≈ 3–5 hours each. A serious 4–6 week curriculum.
