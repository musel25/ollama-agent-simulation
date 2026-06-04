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
    # NB03 — Broadcast a Hand-Signed Transaction to Sepolia

    **This notebook is OPTIONAL.**

    The previous notebooks (NB01 and NB02) built and signed a transaction entirely from scratch,
    without touching a live network.  This notebook takes that signed payload and sends it
    to the Ethereum Sepolia test network so you can watch the confirmation happen on a real chain.

    ---

    ## Before you start — what you need

    1. **A throwaway Sepolia account.**  Generate one with NB01, or use MetaMask → "Create Account".
       **Never use a key that holds real ETH or any other real-value asset.**

    2. **A small amount of Sepolia ETH** (testnet only, worthless).  Get it from a faucet:
       - https://sepoliafaucet.com
       - https://www.alchemy.com/faucets/ethereum-sepolia
       - https://faucet.quicknode.com/ethereum/sepolia

    3. **A public Sepolia RPC endpoint.**  The default below is `https://ethereum-sepolia-rpc.publicnode.com`
       (no API key required).  If it is unresponsive, try:
       - `https://rpc.sepolia.org`
       - `https://1rpc.io/sepolia`

       Note: `https://rpc.sepolia.org` was found to return HTTP 404 during authoring of this notebook;
       `publicnode.com` was used as the primary endpoint.

    ---

    ## How to skip the broadcast

    Leave `PRIV_HEX = "\"` (the default).  All cells that would actually spend test ETH are guarded
    by `if PRIV_HEX:` and will print a skip message instead of running.  The read-only network cells
    (chain-ID check, current base fee) run regardless — they confirm the RPC is reachable.

    ---

    ## What each cell maps to in a real wallet

    | Cell | What MetaMask / Geth does internally |
    |------|--------------------------------------|
    | Step 2 | Application layer: resolve chain ID via `eth_chainId` |
    | Step 3 | Fee estimation: read `baseFeePerGas` from the latest block |
    | Step 4 | Account lookup: get nonce for the sender via `eth_getTransactionCount` |
    | Step 5 | Transaction construction and EIP-1559 signing |
    | Step 6 | Propagation: submit raw bytes via `eth_sendRawTransaction` |
    | Step 7 | Confirmation polling: call `eth_getTransactionReceipt` in a loop |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 1 — Configure constants

    Edit `PRIV_HEX` (and optionally `RPC_URL`) to enable the broadcast steps.
    Everything else can be left as-is.
    """)
    return


@app.cell
def _():
    # ---------------------------------------------------------------------------
    # RPC endpoint — change if this one is rate-limiting you.
    # Note: https://rpc.sepolia.org returned HTTP 404 during authoring;
    # publicnode.com is used as the primary endpoint here.
    RPC_URL  = "https://ethereum-sepolia-rpc.publicnode.com"

    # ---------------------------------------------------------------------------
    # Private key for your THROWAWAY Sepolia account.
    # Paste the 32-byte key as a hex string, with or without the '0x' prefix.
    # Leave blank (default) to skip all broadcast / signing cells.
    PRIV_HEX = ""   # e.g. "0xdeadbeef..."

    # ---------------------------------------------------------------------------
    # Destination address (defaults to the burn address — safe for demos).
    TO_ADDR  = "0x000000000000000000000000000000000000dEaD"

    # ---------------------------------------------------------------------------
    # Value to send in wei.  10**14 == 0.0001 ETH.
    VALUE_WEI = 10**14
    return PRIV_HEX, RPC_URL, TO_ADDR, VALUE_WEI


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## JSON-RPC helper

    All Ethereum nodes expose a single HTTP endpoint that accepts JSON-RPC 2.0 calls.
    This tiny wrapper handles the boilerplate so the rest of the notebook stays readable.
    """)
    return


@app.cell
def _(RPC_URL):
    import requests

    def rpc(method, params):
        """Make one JSON-RPC call to RPC_URL and return the 'result' field."""
        r = requests.post(
            RPC_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data["result"]

    return (rpc,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 2 — Confirm the RPC is reachable and points at Sepolia

    `eth_chainId` returns the integer chain identifier as a hex string.  Sepolia is chain **11155111** (`0xaa36a7`).

    This cell **always runs** — it is a read-only call that costs nothing.
    """)
    return


@app.cell
def _(rpc):
    chain_id_hex = rpc("eth_chainId", [])
    assert int(chain_id_hex, 16) == 11155111, f"unexpected chain id: {chain_id_hex}"
    print("connected to Sepolia, chainId =", chain_id_hex)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 3 — Read the current base fee

    Since EIP-1559 (London fork), each block carries a `baseFeePerGas` that the protocol sets automatically.
    Any transaction must offer at least this fee to be included.  Reading the latest block header gives us
    a good starting point for fee estimation.

    This cell **always runs** — it is read-only.
    """)
    return


@app.cell
def _(rpc):
    blk = rpc("eth_getBlockByNumber", ["latest", False])
    base_fee = int(blk["baseFeePerGas"], 16)
    print(f"latest block: {int(blk['number'], 16)}")
    print(f"base fee:     {base_fee / 1e9:.4f} gwei")
    return (base_fee,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 4 — Get the nonce for your account

    Every transaction from an address carries a monotonically increasing **nonce**.  The node rejects
    transactions whose nonce is not exactly equal to the next expected value for that sender.

    We use `"pending"` (not `"latest"`) so any already-submitted but unconfirmed transactions are
    counted — this prevents accidentally sending two transactions with the same nonce.

    This cell is **skipped when `PRIV_HEX` is empty**.
    """)
    return


@app.cell
def _(PRIV_HEX, rpc):
    from _lib.ecdsa import priv_to_address

    if not PRIV_HEX:
        print("skipped — set PRIV_HEX to enable")
    else:
        priv = bytes.fromhex(PRIV_HEX.removeprefix("0x"))
        FROM = priv_to_address(priv)
        print("from:", FROM)
        nonce_hex = rpc("eth_getTransactionCount", [FROM, "pending"])
        nonce = int(nonce_hex, 16)
        print("nonce:", nonce)
    return nonce, priv


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 5 — Build and sign the EIP-1559 transaction

    This is the same signing logic from NB02, now using real values from the chain:

    - `chainId = 11155111` (Sepolia) — prevents replay attacks on other networks.
    - `nonce` — fetched above from the node.
    - `maxPriorityFeePerGas = 2 gwei` — tip paid to the block producer.
    - `maxFeePerGas = 2 * baseFee + tip` — absolute ceiling; any excess over `baseFee + tip` is refunded.
    - `gasLimit = 21000` — the exact cost of a simple ETH transfer.

    The unsigned payload is `0x02 || RLP(fields)`.  We hash that with Keccak-256, sign it with our
    private key, then append the signature to get the final signed payload.

    This cell is **skipped when `PRIV_HEX` is empty**.
    """)
    return


@app.cell
def _(PRIV_HEX, TO_ADDR, VALUE_WEI, base_fee, nonce, priv):
    if not PRIV_HEX:
        print("skipped — set PRIV_HEX to enable")
    else:
        from _lib.keccak import keccak256
        from _lib.ecdsa import sign_digest
        from _lib.rlp_min import rlp_encode

        def addr_to_bytes(a):
            """Convert a 0x-prefixed hex address string to 20 raw bytes."""
            return bytes.fromhex(a.removeprefix("0x"))

        max_priority = 2 * 10**9          # 2 gwei tip
        max_fee      = 2 * base_fee + max_priority   # fee cap

        # EIP-1559 unsigned fields (type 2): chainId, nonce, maxPriorityFeePerGas,
        # maxFeePerGas, gasLimit, to, value, data, accessList
        unsigned_fields = [
            11155111,               # chainId
            nonce,
            max_priority,
            max_fee,
            21000,                  # gasLimit
            addr_to_bytes(TO_ADDR), # to
            VALUE_WEI,              # value
            b"",                    # data (empty for a plain ETH transfer)
            [],                     # accessList (empty)
        ]

        unsigned_payload = b"\x02" + rlp_encode(unsigned_fields)
        sighash = keccak256(unsigned_payload)
        r, s, v = sign_digest(priv, sighash)

        # Append signature fields: yParity (int), r (bytes), s (bytes)
        signed_payload = b"\x02" + rlp_encode(unsigned_fields + [v, r, s])
        raw_hex = "0x" + signed_payload.hex()

        print(f"sighash:     {sighash.hex()}")
        print(f"yParity:     {v}")
        print(f"r:           {r.hex()}")
        print(f"s:           {s.hex()}")
        print(f"raw tx ({len(signed_payload)} bytes):")
        print(raw_hex)
    return (raw_hex,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 6 — Submit the transaction

    `eth_sendRawTransaction` accepts the RLP-encoded signed bytes (hex-encoded with 0x prefix) and
    returns the transaction hash.  At this point the transaction is in the mempool — not yet confirmed.

    This cell is **skipped when `PRIV_HEX` is empty**.
    """)
    return


@app.cell
def _(PRIV_HEX, raw_hex, rpc):
    if not PRIV_HEX:
        print("skipped — set PRIV_HEX to enable")
    else:
        tx_hash_hex = rpc("eth_sendRawTransaction", [raw_hex])
        print("submitted:", tx_hash_hex)
        print(f"https://sepolia.etherscan.io/tx/{tx_hash_hex}")
    return (tx_hash_hex,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Step 7 — Poll for confirmation

    `eth_getTransactionReceipt` returns `null` while the transaction is pending and an object once it
    is included in a block.  We poll every 2 seconds for up to 120 seconds.

    The `status` field in the receipt is `"0x1"` for success and `"0x0"` for a reverted transaction.

    This cell is **skipped when `PRIV_HEX` is empty**.
    """)
    return


@app.cell
def _(PRIV_HEX, rpc, tx_hash_hex):
    if not PRIV_HEX:
        print("skipped — set PRIV_HEX to enable")
    else:
        import time
        for _ in range(60):
            rcpt = rpc("eth_getTransactionReceipt", [tx_hash_hex])
            if rcpt:
                print("confirmed in block", int(rcpt["blockNumber"], 16))
                print("status:", rcpt["status"])
                break
            time.sleep(2)
        else:
            print("not confirmed within 120s — check Etherscan link above")
    return


if __name__ == "__main__":
    app.run()
