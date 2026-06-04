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
    # 01d — Chain walkthrough

    Walk one full trade. Render every state change.

    > **Prereq:** `anvil` and `forge` on PATH.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import (render_chain_status, render_event_timeline)

    return render_chain_status, render_event_timeline


@app.cell
def _():
    from shared.anvil import anvil
    from shared.config import Config
    from shared.deploy import deploy_contracts
    from shared.chain import make_web3, send_tx, extract_token_id
    from shared.contracts import get_escrow_contract, get_nft_contract
    from eth_account import Account

    DEPLOYER = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'
    provider_account = Account.from_key(PROVIDER)
    consumer_account = Account.from_key(CONSUMER)

    ctx = anvil(port=18547)
    rpc_url = ctx.__enter__()
    cfg = Config(rpc_url=rpc_url, deployer_private_key=DEPLOYER,
                 provider_private_key=PROVIDER, consumer_private_key=CONSUMER,
                 sdn_mock=True)
    addrs = deploy_contracts(cfg)
    print('escrow:', addrs['bandwidthEscrow'])
    print('nft:   ', addrs['bandwidthNFT'])

    w3 = make_web3(cfg)
    escrow = get_escrow_contract(w3)
    nft = get_nft_contract(w3)
    return (
        CONSUMER,
        PROVIDER,
        consumer_account,
        ctx,
        escrow,
        extract_token_id,
        nft,
        provider_account,
        send_tx,
        w3,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Initial balances
    """)
    return


@app.cell
def _(consumer_account, escrow, provider_account, w3):
    def balances():
        return {
            "consumer": w3.eth.get_balance(consumer_account.address),
            "provider": w3.eth.get_balance(provider_account.address),
            "escrow": w3.eth.get_balance(escrow.address),
        }
    b0 = balances(); b0
    return b0, balances


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Stage 1 — `requestAgreement` (consumer locks ETH)
    """)
    return


@app.cell
def _(
    CONSUMER,
    consumer_account,
    display,
    escrow,
    provider_account,
    render_chain_status,
    send_tx,
    w3,
):
    agreement_id = 1234
    mbps, duration, price_wei = 5, 600, 10**16
    tx1, _ = send_tx(w3, consumer_account, CONSUMER,
        escrow.functions.requestAgreement(agreement_id, provider_account.address,
                                          mbps, duration), value=price_wei)
    display(render_chain_status(escrow, agreement_id))
    return agreement_id, duration, mbps


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Stage 2 — `mint` (provider creates the credential)
    """)
    return


@app.cell
def _(
    PROVIDER,
    agreement_id,
    duration,
    extract_token_id,
    mbps,
    nft,
    provider_account,
    send_tx,
    w3,
):
    tx2, mint_rcpt = send_tx(w3, provider_account, PROVIDER,
        nft.functions.mint(provider_account.address, agreement_id,
                           mbps, duration, 'clab://pe1/eth-1.100'))
    token_id = extract_token_id(mint_rcpt, nft)
    print('tokenId =', token_id)
    return (token_id,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Stage 3 — `approve` + `deposit` (the atomic swap)

    The provider first approves the escrow to transfer the NFT, then calls `deposit`. Inside `deposit`, the contract:

    1. Updates `status` to `ACTIVE` (Effects-before-Interactions).
    2. Pulls the NFT from provider into escrow.
    3. Pushes the NFT from escrow to consumer.
    4. Sends `priceWei` to provider.

    All three transfers happen in one transaction. Atomic.
    """)
    return


@app.cell
def _(
    PROVIDER,
    agreement_id,
    display,
    escrow,
    nft,
    provider_account,
    render_chain_status,
    send_tx,
    token_id,
    w3,
):
    send_tx(w3, provider_account, PROVIDER,
            nft.functions.approve(escrow.address, token_id))
    tx3, _ = send_tx(w3, provider_account, PROVIDER,
            escrow.functions.deposit(agreement_id, token_id))
    display(render_chain_status(escrow, agreement_id))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Balances before vs after
    """)
    return


@app.cell
def _(b0, balances):
    b1 = balances()
    from IPython.display import HTML
    def w2e(v): return f"{v/10**18:.4f} ETH"
    rows = "".join(
        f"<tr><td>{k}</td><td>{w2e(b0[k])}</td><td>{w2e(b1[k])}</td>"
        f"<td>{w2e(b1[k]-b0[k])}</td></tr>"
        for k in b0)
    HTML(f"<table style='border-collapse:collapse;font-family:monospace;font-size:13px'>"
         f"<thead><tr><th>actor</th><th>before</th><th>after</th><th>\u0394</th></tr></thead>"
         f"<tbody>{rows}</tbody></table>")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Full event timeline
    """)
    return


@app.cell
def _(display, escrow, nft, render_event_timeline, w3):
    events = []
    for name in ("AgreementRequested", "AgreementActive", "AgreementCancelled"):
        evt = getattr(escrow.events, name, None)
        if evt:
            for log in evt.get_logs(fromBlock=0):
                tx_hash = log["transactionHash"].hex() if hasattr(log["transactionHash"], "hex") else str(log["transactionHash"])
                gas = w3.eth.get_transaction_receipt(tx_hash)["gasUsed"]
                events.append({"event": name, "block": log["blockNumber"],
                               "args": dict(log["args"]),
                               "gas": int(gas), "txHash": tx_hash})
    for log in nft.events.Transfer().get_logs(fromBlock=0):
        tx_hash = log["transactionHash"].hex() if hasattr(log["transactionHash"], "hex") else str(log["transactionHash"])
        gas = w3.eth.get_transaction_receipt(tx_hash)["gasUsed"]
        events.append({"event": "Transfer", "block": log["blockNumber"],
                       "args": {k: str(v) for k, v in dict(log["args"]).items()},
                       "gas": int(gas), "txHash": tx_hash})
    events.sort(key=lambda e: (e["block"], e["event"]))
    display(render_event_timeline(events))
    return


@app.cell
def _(ctx):
    ctx.__exit__(None, None, None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Recap: one trade, three transactions (request → mint → approve+deposit), one atomic swap. Next: [02a — MCP concepts](02a_mcp_concepts.py).
    """)
    return


if __name__ == "__main__":
    app.run()
