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
    # 04b — Graph topology

    The compiled LangGraph, rendered. Plus what each node does.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from shared.config import Config

    CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'
    return CONSUMER, Config


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Build the graph with no-op stubs
    """)
    return


@app.cell
def _(CONSUMER, Config):
    from consumer.graph import build_graph

    cfg = Config(consumer_private_key=CONSUMER)
    async def _noop(*a, **k): return "{}"
    def _noop_sync(*a, **k): return "{}"
    async_tools = {"discover_provider", "browse_catalog", "request_quote", "present_credential"}
    tools = {n: (_noop if n in async_tools else _noop_sync)
             for n in ("discover_provider","browse_catalog","request_quote","lock_payment",
                       "await_settlement","present_credential","verify_credential")}
    graph = build_graph(cfg, tools)
    print('graph compiled')
    return (graph,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Render the LangGraph PNG
    """)
    return


@app.cell
def _(graph):
    from IPython.display import Image
    png = graph.get_graph().draw_mermaid_png()
    Image(png)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mermaid source (so we can see the conditional edges in text)
    """)
    return


@app.cell
def _(graph):
    print(graph.get_graph().draw_mermaid())
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Per-node table

    | Node | Reads | Writes | What it does |
    |---|---|---|---|
    | `discover_node` | `provider_urls` | `provider_url`, `provider_urls`, `log` | Fetches each provider's AgentCard; drops any provider missing the required skills (`get_catalog`, `request_quote`, `activate`). |
    | `browse_node` | `provider_urls` | `offers`, `catalog`, `log` | A2A `get_catalog` against every surviving provider; merges per-package by best price. |
    | `pick_tier_node` | `catalog`, `user_message`, `model` | `chosen_tier`, `chosen_mbps`, `provider_url`, `thinking`, `log` | **LLM call** → one-word tier; `deterministic_tier_pick` fallback if the LLM doesn't comply. |
    | `quote_node` | `provider_url`, `chosen_tier` | `agreement_id`, `log` | A2A `request_quote`; populates `agreement_id`. |
    | `lock_node` | `agreement_id` | `tx_hash`, `log` | Sends `escrow.requestAgreement{value: priceWei}` via the consumer MCP `lock_payment` tool. |
    | `settle_node` | `agreement_id` | `token_id` (on success), `settle_attempts`, `log` | Polls `getAgreement` for status `ACTIVE`; sets `token_id`; retries up to 3 times via `_settle_route`. |
    | `present_node` | `provider_url`, `token_id` | `activation`, `log` | A2A `activate` with a fresh signed nonce. |
    | `verify_node` | `token_id`, `chosen_mbps` | `on_chain_verification`, `log`, possibly `error` | Independent on-chain verification: `ownerOf(tokenId)`, `getTokenMetadata`, mbps match. |
    | `summary_node` | (most state fields) | `final_response`, `thinking` | **LLM call** (informational); `final_response` is template-built, not LLM-built. |
    | `error_node` | `error` | `final_response` | Terminal sink for any `error`. |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Conditional edges

    The graph has two kinds of routing:

    1. **Linear-with-error fallback** (`_route_after`). After `discover_node`, `browse_node`, `pick_tier_node`, `quote_node`, `lock_node`, `present_node`, `verify_node`: if `state["error"]` is set, route to `error_node`; otherwise route to the next happy-path node.

    2. **Settle retry loop** (`_settle_route`). After `settle_node`:
       - If `state["error"]`: → `error_node`.
       - Else if `state["token_id"]` is set: → `present_node` (success).
       - Else if `settle_attempts >= 3`: → `error_node`.
       - Else: → `settle_node` again (loop).

    This is the only loop in the graph. The retry budget protects against forgotten settlements without livelocking.

    Next: [04c — LLM prompts](04c_graph_llm_prompts.py).
    """)
    return


if __name__ == "__main__":
    app.run()
