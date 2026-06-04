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
    # 01b — Chain: escrow lifecycle

    The contract's state machine, transition by transition.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_mermaid

    return (render_mermaid,)


@app.cell
def _(render_mermaid):
    render_mermaid("""
    stateDiagram-v2
      [*] --> NONE
      NONE --> REQUESTED : requestAgreement (consumer, msg.value)
      REQUESTED --> ACTIVE : deposit (provider, tokenId)
      REQUESTED --> CANCELLED : cancel (consumer or after deadline)
      ACTIVE --> [*]
      CANCELLED --> [*]
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Transitions

    | Function | Caller | Pre-state | Post-state | Event emitted |
    |---|---|---|---|---|
    | `requestAgreement(id, provider, mbps, dur)` (payable) | consumer | `NONE` | `REQUESTED` | `AgreementRequested(id, consumer, provider, mbps, dur, priceWei)` |
    | `deposit(id, tokenId)` | provider | `REQUESTED` | `ACTIVE` | `AgreementActive(id, tokenId, consumer, provider)` |
    | `cancel(id)` | consumer (anytime) or anyone (after `requestDeadline`) | `REQUESTED` | `CANCELLED` | `AgreementCancelled(id, consumer)` |

    `CLOSED` is unreachable today — reserved for a future "lease ended cleanly" transition that the current contracts don't implement.

    `NONE → REQUESTED` requires `msg.value > 0` (otherwise `ZeroPriceNotAllowed`). The locked ETH lives in the escrow contract's balance until either `deposit()` (paid to provider) or `cancel()` (refunded to consumer).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The atomic swap inside `deposit()`

    The most subtle code in the whole repo:

    ```solidity
    // ── Effects ───────────────────────────────────────────────────────────
    ag.status = Status.ACTIVE;
    ag.tokenId = tokenId;

    // ── Interactions ──────────────────────────────────────────────────────
    nftContract.safeTransferFrom(msg.sender, address(this), tokenId);
    nftContract.safeTransferFrom(address(this), ag.consumer, tokenId);
    (bool ok,) = ag.provider.call{value: ag.priceWei}("\");
    if (!ok) revert ETHTransferFailed();
    ```

    This is the **Checks-Effects-Interactions** pattern. The status flip to `ACTIVE` happens **before** any external call. Why?

    If status were updated AFTER the ETH transfer, a malicious provider contract could re-enter `deposit()` from inside its `receive()` callback while `status` was still `REQUESTED`. CEI guarantees that any reentrant call sees the updated state and reverts on `WrongStatus`.

    The two `safeTransferFrom` calls walk the NFT through the escrow:
    1. Provider → escrow (the escrow inherits `ERC721Holder` so this is allowed).
    2. Escrow → consumer.

    This is functionally a single transfer but the contract pattern keeps approval scopes tight: the provider only approves the escrow, never the consumer directly.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Cancel paths

    **Consumer-initiated** — anytime while `REQUESTED`. The consumer might want to back out before the provider deposits.

    **Anyone-after-deadline** — once `block.timestamp > requestDeadline`, anyone can call `cancel()`. This prevents a stuck-provider from keeping consumer funds locked forever.

    `cancel()` flips status to `CANCELLED`, refunds `priceWei` to the consumer, and emits `AgreementCancelled`. Like `deposit()`, status updates BEFORE the ETH transfer.
    """)
    return


@app.cell
def _():
    import json
    from pathlib import Path
    abi = json.loads(Path("shared/abi/BandwidthEscrow.json").read_text())
    fns = [f for f in abi if f.get("type") == "function" and f["name"] in ("requestAgreement", "deposit", "cancel", "getAgreement")]
    print(json.dumps(fns, indent=2))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Next: [01c — NFT minting](01c_chain_nft_minting.py).
    """)
    return


if __name__ == "__main__":
    app.run()
