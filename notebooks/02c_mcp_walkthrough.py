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
    # 02c — MCP walkthrough

    Call provider tools through `fastmcp.Client`. No A2A, no chain — just MCP-against-FastMCP-in-process.

    > **Prereq:** none.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from shared.config import Config

    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    return Config, PROVIDER


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Build the provider MCP server in-process
    """)
    return


@app.cell
def _(Config, PROVIDER):
    from provider.mcp_server import build_mcp_server
    cfg = Config(provider_private_key=PROVIDER, sdn_mock=True)
    mcp, tool_log = build_mcp_server(cfg)
    print('built. tool_log starts empty.')
    return mcp, tool_log


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## List tools and call `get_catalog`
    """)
    return


@app.cell
def _(mcp):
    import asyncio, json
    from fastmcp import Client

    async def demo():
        async with Client(mcp) as c:
            tools = await c.list_tools()
            print('Tools:')
            for t in tools:
                print(f'  - {t.name}')
            catalog = await c.call_tool('get_catalog', {})
            return json.loads(catalog.content[0].text)
    catalog = asyncio.get_event_loop().run_until_complete(demo())
    catalog
    return Client, asyncio, json


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## How the response shape works

    `call_tool` returns a `CallToolResult`. The actual return value of the python function is serialized into `result.content[0].text` as a JSON string. To use it in Python you parse it with `json.loads`.

    This wrapping exists because MCP transports (stdio, HTTP) need a uniform content-typed envelope. In-process transport keeps the same shape for symmetry.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Call `request_quote`
    """)
    return


@app.cell
def _(Client, asyncio, json, mcp):
    async def quote():
        async with Client(mcp) as c:
            r = await c.call_tool('request_quote',
                {'package_id': 'medium',
                 'consumer_address': '0x000000000000000000000000000000000000dEaD'})
            return json.loads(r.content[0].text)
    quote_data = asyncio.get_event_loop().run_until_complete(quote())
    quote_data
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Inspect the tool log
    """)
    return


@app.cell
def _(tool_log):
    from IPython.display import HTML
    rows = "".join(
        f"<tr><td>{e['ts']:.2f}</td><td><code>{e['tool']}</code></td>"
        f"<td>{e['status']}</td><td><code style='font-size:12px'>{e['args']}</code></td></tr>"
        for e in tool_log)
    HTML(f"<table style='border-collapse:collapse;font-size:13px'>"
         f"<thead style='background:#f6f8fa'><tr><th>ts</th><th>tool</th><th>status</th><th>args</th></tr></thead>"
         f"<tbody>{rows}</tbody></table>")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What we didn't call

    `mint_credential`, `complete_swap`, `allocate_bandwidth`, `revoke_bandwidth`, `verify_bandwidth`, `verify_credential_ownership` — these all require either a live chain (anvil) or SDN_MOCK semantics, and we're staying purely in-memory here. See [01d — chain walkthrough](01d_chain_walkthrough.py) and [05a — inventory & expiry](05a_inventory_and_expiry.py) for those.

    Next: [03a — A2A concepts](03a_a2a_concepts.py).
    """)
    return


if __name__ == "__main__":
    app.run()
