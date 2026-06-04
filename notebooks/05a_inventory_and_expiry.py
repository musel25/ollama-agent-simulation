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
    # 05a — Inventory + expiry

    The provider's "I have a slot" model: how slots are reserved, how they expire, and how the chain event listener bridges escrow events into MCP tool calls.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The catalog

    `provider/catalog.py` defines three tiers as a constant:

    | packageId | mbps | duration | priceWei |
    |---|---|---|---|
    | `small`  | 2 | 600s (10 min) | 0.01 ETH |
    | `medium` | 5 | 600s (10 min) | 0.02 ETH |
    | `large`  | 8 | 600s (10 min) | 0.08 ETH |

    Pricing is non-linear (large is 4× medium even though it's 1.6× the bandwidth) — the catalog is illustrative, not market-realistic.

    `pending_quotes: dict[int, dict]` is an in-memory cache: `agreementId → {packageId, expires, ...}`. Quote TTL is 300 seconds. `cleanup_quotes()` evicts expired entries; called once at the start of `make_quote()` and `_handle()`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The inventory file

    `provider/inventory.txt` is JSONL (one row per tier). Each row has a `slots` list:

    ```json
    {"tier": "small", "mbps": 2, "durationSeconds": 600, "slots": [
        {"pe": "pe1", "subinterface": "ethernet-1/2.0", "ce": "ce1",
         "agreementId": null, "expiresAt": null}
    ]}
    ```

    A slot is "free" when `agreementId is null`. When a quote is accepted, the slot is bound: `agreementId` becomes the agreement ID, `expiresAt` becomes `time() + durationSeconds`.

    The current inventory has exactly 3 slots (one per tier). Add slots by appending to the relevant row's `slots` list.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## SlotPool semantics

    `SlotPool` (`shared/slot_pool.py`) wraps inventory.txt with an `fcntl.LOCK_EX` (file lock). All public methods take the lock so two concurrent `reserve` calls can't double-allocate.

    **Expiry-on-read:** every read also reclaims slots whose `expiresAt < time()`. This makes `available_count` and `tiers` self-healing — a stale slot is freed the next time anyone looks at it.

    **Methods:**
    - `reserve(tier, agreement_id, duration_seconds) → Slot | None` — find first free slot in tier, bind it, persist.
    - `release(agreement_id)` — clear bindings for the given agreement.
    - `lookup(agreement_id) → Slot | None` — find the slot bound to this agreement.
    - `available_count(tier) → int` — count free slots after reclaim.
    - `tiers() → list[dict]` — for catalog display.
    - `expired_agreement_ids() → list[int]` — read-only enumeration of expired-but-still-bound agreements.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Event listener

    `provider/event_listener.py` runs in the FastAPI lifespan. Polls the escrow contract for `AgreementRequested` events every 2s. For each event:

    1. Look up the cached quote.
    2. Sanity-check escrow state matches the quote (mbps, duration, price).
    3. `slot_pool.reserve(tier, agreementId, durationSeconds)`.
    4. MCP `mint_credential` (NFT mint with the slot's pe/subinterface).
    5. MCP `complete_swap` (approve + deposit; the escrow's atomic swap fires).

    Failures release the slot. The listener never blocks the FastAPI loop — handlers run as `asyncio.create_task` from the polling loop.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Expiry sweep

    `provider/expiry.py` runs every 30s. It reads inventory.txt, finds slots where `expiresAt < now`, and for each:

    1. MCP `revoke_bandwidth(pe, subinterface)` — pushes a no-op (mock) or real gNMI/tc revoke.
    2. `slot_pool.release(agreement_id)` — frees the slot in inventory.txt.

    Without this, an expired lease's PE policer would stay configured indefinitely, and the slot would stay "bound" until manual cleanup.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Live inventory snapshot
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    import json
    from pathlib import Path
    rows = [json.loads(line) for line in Path("provider/inventory.txt").read_text().splitlines() if line.strip()]
    from IPython.display import HTML
    slot_rows = []
    for r in rows:
        for s in r["slots"]:
            slot_rows.append((r["tier"], r["mbps"], r["durationSeconds"],
                              s["pe"], s["subinterface"], s["ce"],
                              s["agreementId"], s["expiresAt"]))
    html_rows = "".join(f"<tr>{''.join(f'<td>{c}</td>' for c in row)}</tr>" for row in slot_rows)
    HTML(f"<table style='border-collapse:collapse;font-size:13px;font-family:monospace'>"
         f"<thead style='background:#f6f8fa'><tr>"
         f"<th>tier</th><th>mbps</th><th>dur</th>"
         f"<th>pe</th><th>subif</th><th>ce</th>"
         f"<th>aid</th><th>expiresAt</th></tr></thead>"
         f"<tbody>{html_rows}</tbody></table>")
    return (Path,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Walkthrough — reserve + manual expire
    """)
    return


@app.cell
def _(Path):
    import shutil, tempfile, time
    from shared.slot_pool import SlotPool

    td = tempfile.mkdtemp()
    inv_path = Path(td) / "inventory.txt"
    shutil.copy("provider/inventory.txt", inv_path)
    pool = SlotPool(inv_path)
    print('available medium:', pool.available_count('medium'))
    slot = pool.reserve('medium', agreement_id=42, duration_seconds=2)
    print('reserved:', slot)
    print('available medium now:', pool.available_count('medium'))

    time.sleep(3)
    print('expired ids:', pool.expired_agreement_ids())
    print('available medium after read+reclaim:', pool.available_count('medium'))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    After the 3-second sleep, the slot has expired (`expiresAt < now`). `expired_agreement_ids` enumerates them; the next `available_count` call triggers expiry-on-read and frees the slot. In production, the expiry sweep would have called `revoke_bandwidth` first to actually clear the gNMI policer.

    Next: [06 — end to end](06_end_to_end.py), then the network block ([07a](07a_network_concepts.py)).
    """)
    return


if __name__ == "__main__":
    app.run()
