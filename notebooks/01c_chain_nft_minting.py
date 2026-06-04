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
    # 01c — Chain: NFT credential

    What exactly is in a `BandwidthNFT`, and why it IS the credential.

    > **Prereq:** `anvil` and `forge` on PATH (Foundry). The notebook spawns a local Anvil node and deploys both contracts to demonstrate one mint.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## `TokenMetadata` field-by-field

    | Field | Source | Meaning |
    |---|---|---|
    | `agreementId` | `mint()` arg | Which escrow agreement this NFT settles |
    | `bandwidthMbps` | `mint()` arg | Granted Mbps |
    | `durationSeconds` | `mint()` arg | Lease duration |
    | `startTime` | `block.timestamp` at mint | Lease starts ticking from here |
    | `endpoint` | `mint()` arg | `clab://<pe>/<subinterface>` — literal SDN endpoint |

    The endpoint is the literal binding from credential to network identifier. The provider's `mint_credential` MCP tool builds it as `f"clab://{pe}/{subinterface}"` from the slot it just reserved.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why on-chain metadata, not `tokenURI` / IPFS

    **Verifiability without a second trust assumption.** Anyone with an RPC endpoint can read `getTokenMetadata(tokenId)` and trust the answer because they trust Ethereum. With `tokenURI` pointing at IPFS, you'd need to trust IPFS (and pinning) too.

    **Cheap.** The metadata is small (~5 fields, ~100 bytes). On-chain storage cost is dominated by the `string endpoint` — but it's bounded.

    **Atomic with mint.** The metadata is set in the same transaction as `_safeMint`, so partial-state issues (NFT exists but metadata doesn't) are impossible.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why owner-only mint

    `BandwidthNFT` is `Ownable(initialOwner)` with the provider EOA as owner. Only the provider can mint, which means: **the only way an NFT exists is via a path the provider controls.** Combined with the contract's invariant that `mint` parameters are recorded in `TokenMetadata`, this means: a credential's claims are exactly what the provider wrote at mint time.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    return


@app.cell
def _():
    from shared.anvil import anvil
    from shared.config import Config
    from shared.deploy import deploy_contracts
    from shared.chain import make_web3, send_tx, extract_token_id
    from shared.contracts import get_nft_contract
    from eth_account import Account

    DEPLOYER = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'

    ctx = anvil(port=18546)
    rpc_url = ctx.__enter__()
    cfg = Config(rpc_url=rpc_url, deployer_private_key=DEPLOYER,
                 provider_private_key=PROVIDER, consumer_private_key=CONSUMER,
                 sdn_mock=True)
    deploy_contracts(cfg)
    w3 = make_web3(cfg)
    nft = get_nft_contract(w3)
    provider_account = Account.from_key(PROVIDER)
    tx, receipt = send_tx(w3, provider_account, PROVIDER,
        nft.functions.mint(provider_account.address, 1234, 5, 600,
                           'clab://pe1/eth-1.100'))
    token_id = extract_token_id(receipt, nft)
    print('tokenId:', token_id)
    return ctx, nft, token_id


@app.cell
def _(nft, token_id):
    from IPython.display import HTML
    meta = nft.functions.getTokenMetadata(token_id).call()
    fields = ["agreementId", "bandwidthMbps", "durationSeconds", "startTime", "endpoint"]
    rows = "".join(f"<tr><td><b>{k}</b></td><td><code>{v}</code></td></tr>"
                   for k, v in zip(fields, meta))
    HTML(f"<div style='border:2px dashed #1b5e20;padding:12px;border-radius:8px;"
         f"max-width:480px;font-family:system-ui'>"
         f"<div style='font-size:18px;font-weight:600'>"
         f"🎫 BandwidthNFT #{token_id}</div>"
         f"<table style='font-size:13px'>{rows}</table></div>")
    return


@app.cell
def _(ctx):
    ctx.__exit__(None, None, None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Next: [01d — chain walkthrough](01d_chain_walkthrough.py).
    """)
    return


if __name__ == "__main__":
    app.run()
