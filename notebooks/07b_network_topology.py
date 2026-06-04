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
    # 07b — Network topology

    Drawn live from `provider/inventory.txt` and the `CE_PEER` map. Editing inventory.txt and re-running this notebook updates the diagram.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_topology_from_rows

    return (render_topology_from_rows,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Topology with no active slots
    """)
    return


@app.cell
def _(render_topology_from_rows):
    import json
    from pathlib import Path
    from provider.app import CE_PEER

    rows = [json.loads(l) for l in Path("provider/inventory.txt").read_text().splitlines() if l.strip()]
    render_topology_from_rows(rows, active_agreement_ids=set(), ce_peer=CE_PEER)
    return (rows,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## How to read the diagram

    - **PE nodes** (rectangles): `pe1`, `pe2` — the PE routers in the clab topology.
    - **CE nodes** (circles): `ce1`, `ce2`, `ce3`, `ce4` — customer edge hosts.
    - **Solid edges**: a (CE → PE) link, labeled with the tier's `mbps` and the SR Linux subinterface.
    - **Dotted "peer" edges**: CE-to-CE peering from `CE_PEER` (used by `verify_bandwidth`'s iperf3 probe).
    - **Green-highlighted edges** (when present): slots currently bound to an agreement.

    The current inventory has 3 slots: `small`/2 Mbps on `pe1/eth-1/2.0/ce1`, `medium`/5 Mbps on `pe1/eth-1/3.0/ce3`, `large`/8 Mbps on `pe2/eth-1/2.0/ce2`. So `pe1` carries two slots and `pe2` carries one.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Per-tier inventory summary
    """)
    return


@app.cell
def _(rows):
    from IPython.display import HTML
    trows = "".join(f"<tr><td>{r['tier']}</td><td>{r['mbps']}</td>"
                    f"<td>{r['durationSeconds']}</td>"
                    f"<td>{r['slots'][0]['pe']}</td>"
                    f"<td>{r['slots'][0]['subinterface']}</td>"
                    f"<td>{r['slots'][0]['ce']}</td></tr>" for r in rows)
    HTML(f"<table style='border-collapse:collapse;font-size:13px;font-family:system-ui'>"
         f"<thead><tr><th>tier</th><th>mbps</th><th>dur</th>"
         f"<th>pe</th><th>subif</th><th>ce</th></tr></thead>"
         f"<tbody>{trows}</tbody></table>")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    > **Note:** This notebook reads inventory at runtime. If you add slots to `provider/inventory.txt` (multiple slots per tier, or new tiers), re-running cells 4 and 7 picks them up automatically — no notebook edits needed.

    Next: [07c — before/after](07c_network_before_after.py).
    """)
    return


if __name__ == "__main__":
    app.run()
