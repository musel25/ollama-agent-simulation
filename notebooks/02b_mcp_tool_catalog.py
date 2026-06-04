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
    # 02b — MCP tool catalog

    Inspect every tool from both servers. Each tool is rendered as a card with name, description, and JSON Schema for its inputs.

    > **Prereq:** none — both servers build in-process without anvil or network.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_mcp_tools
    from shared.config import Config

    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'
    return CONSUMER, Config, PROVIDER, render_mcp_tools


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Provider tools (8)
    """)
    return


@app.cell
def _(Config, PROVIDER, render_mcp_tools):
    from provider.mcp_server import build_mcp_server as build_provider_mcp
    cfg_p = Config(provider_private_key=PROVIDER, sdn_mock=True)
    mcp_p, _ = build_provider_mcp(cfg_p)
    render_mcp_tools(mcp_p)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Consumer tools (8)
    """)
    return


@app.cell
def _(CONSUMER, Config, render_mcp_tools):
    from consumer.mcp_server import build_mcp_server as build_consumer_mcp
    cfg_c = Config(consumer_private_key=CONSUMER)
    mcp_c, _ = build_consumer_mcp(cfg_c)
    render_mcp_tools(mcp_c)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## How they fit together

    | Consumer tool | Goes through | Provider tool(s) |
    |---|---|---|
    | `discover_provider` | HTTP (no MCP) | none — fetches `/.well-known/agent-card.json` |
    | `browse_catalog` | A2A `get_catalog` action | `get_catalog` |
    | `request_quote` | A2A `request_quote` action | `request_quote` |
    | `present_credential` | A2A `activate` action | `verify_credential_ownership` + `allocate_bandwidth` |
    | `lock_payment` | direct on-chain | (none — escrow contract) |
    | `await_settlement` | direct on-chain | (none — escrow contract) |
    | `verify_credential` | direct on-chain | (none — NFT contract) |
    | `wallet_address` | local | (none) |

    Note: the provider's three SDN tools (`allocate_bandwidth`, `revoke_bandwidth`, `verify_bandwidth`) and chain-touching tools (`mint_credential`, `complete_swap`) are never called by the consumer — they're internal to the provider's own workflow (event listener, expiry sweep). See [05a — inventory & expiry](05a_inventory_and_expiry.py) for those paths.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Next: [02c — walkthrough](02c_mcp_walkthrough.py).
    """)
    return


if __name__ == "__main__":
    app.run()
