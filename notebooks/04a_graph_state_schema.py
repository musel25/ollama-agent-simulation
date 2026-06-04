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
    # 04a — Graph state schema

    The consumer's `WorkflowState` is the single bus that every node reads from and writes to. Here we walk every field, who writes it, and who reads it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## TypedDict semantics

    `WorkflowState` is a `TypedDict` with `total=False`, meaning every key is optional. Every node returns a partial dict; LangGraph merges it into the running state. Two fields are append-mutated lists (`log` and `thinking`); every node that touches them returns `{"log": state["log"]}` to preserve the appended entries.

    `agreement_id` is a `str` even though on-chain it's a `uint256` — the consumer carries it as a string for JSON-safety in the inter-agent log and `lock_payment` parses it back to an int when sending the tx.
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
    import inspect
    from consumer.graph import WorkflowState
    print(inspect.getsource(WorkflowState))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Field-by-field map
    """)
    return


@app.cell
def _():
    from IPython.display import HTML
    rows_data = [
        ("user_message",        "str",       "(initial)",      "pick_tier_node, summary_node"),
        ("provider_url",        "str",       "discover_node",  "all A2A nodes"),
        ("provider_urls",       "list[str]", "discover_node",  "browse_node"),
        ("offers",              "list[dict]","browse_node",    "pick_tier_node"),
        ("catalog",             "list[dict]","browse_node",    "pick_tier_node"),
        ("chosen_tier",         "str",       "pick_tier_node", "quote_node, summary_node"),
        ("chosen_mbps",         "float",     "pick_tier_node", "verify_node, summary_node"),
        ("agreement_id",        "str",       "quote_node",     "lock_node, settle_node, summary_node"),
        ("tx_hash",             "str",       "lock_node",      "(observability)"),
        ("token_id",            "int",       "settle_node",    "present_node, verify_node, summary_node"),
        ("settle_attempts",     "int",       "settle_node",    "_settle_route"),
        ("activation",          "dict",      "present_node",   "(observability)"),
        ("on_chain_verification","dict",     "verify_node",    "(observability)"),
        ("final_response",      "str",       "summary_node|error_node", "\u2014"),
        ("log",                 "list[dict]","every node",     "every node"),
        ("thinking",            "list[str]", "pick_tier_node, summary_node", "\u2014"),
        ("error",               "str|None",  "any node on failure", "_route_after, _settle_route"),
    ]
    rows = "".join(f"<tr><td><code>{n}</code></td><td><code>{t}</code></td>"
                   f"<td>{w}</td><td>{r}</td></tr>" for n,t,w,r in rows_data)
    HTML(f"<table style='border-collapse:collapse;font-size:12px;font-family:system-ui'>"
         f"<thead style='background:#f6f8fa'><tr><th>field</th><th>type</th>"
         f"<th>written by</th><th>read by</th></tr></thead>"
         f"<tbody>{rows}</tbody></table>")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Observation: most fields are write-once

    `agreement_id` is set once (by `quote_node`), `token_id` is set once (by `settle_node`), `chosen_tier` is set once (by `pick_tier_node`), and so on. The only loops in state come from:

    - `log` and `thinking` — append-only across every node.
    - `settle_attempts` — bumped each time `settle_node` retries.

    This write-once shape is what makes the graph easy to reason about: errors flow forward as `error`; happy-path values flow forward as their typed fields. There's no shared mutable state between branches.

    Next: [04b — graph topology](04b_graph_topology.py).
    """)
    return


if __name__ == "__main__":
    app.run()
