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
    # 07c — Before / after

    The consumer starts with **0 Mbps** (no active slot, no policer). After negotiation + settlement: **5 Mbps** on the medium-tier slot. Toggle below shows both states.

    The diagrams come from the same `render_topology_from_rows` helper — the only thing that changes is which agreementId is in the "active" set. Active edges get a green stroke; the consumer banner switches color.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_topology_from_rows, toggle_before_after

    return render_topology_from_rows, toggle_before_after


@app.cell
def _():
    import json
    from pathlib import Path
    from provider.app import CE_PEER

    rows = [json.loads(l) for l in Path("provider/inventory.txt").read_text().splitlines() if l.strip()]
    print('loaded', len(rows), 'tier rows')
    return CE_PEER, json, rows


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Build the BEFORE frame (no active slots)
    """)
    return


@app.cell
def _(CE_PEER, render_topology_from_rows, rows):
    from IPython.display import HTML

    def banner(label, value, color):
        return HTML(f"<div style='background:{color};color:white;padding:10px;border-radius:8px;font-family:system-ui;text-align:center;max-width:400px;font-size:18px;font-weight:600;margin-bottom:8px'>{label}: {value}</div>")
    before_top = render_topology_from_rows(rows, set(), CE_PEER)
    before_top_html = before_top.data if hasattr(before_top, 'data') else f"<img src='data:image/png;base64,{__import__('base64').b64encode(before_top.data if hasattr(before_top, 'data') else b'').decode()}'/>"
    import base64
    if hasattr(before_top, 'format') and before_top.format == 'png':
        _img_b64 = base64.b64encode(before_top.data).decode()
        before_body = f"<img src='data:image/png;base64,{_img_b64}' style='max-width:600px'/>"
    # render_topology returns an Image (PNG bytes via mermaid.ink) on success, or HTML fallback
    else:
        before_body = before_top.data
    before = HTML(banner('Consumer', '0 Mbps', '#888').data + before_body)
    return HTML, banner, base64, before


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Build the AFTER frame (medium slot bound to a fake agreementId=777)
    """)
    return


@app.cell
def _(CE_PEER, HTML, banner, base64, json, render_topology_from_rows, rows):
    rows_after = json.loads(json.dumps(rows))  # deep copy
    for r in rows_after:
        if r['tier'] == 'medium':
            r['slots'][0]['agreementId'] = 777
            r['slots'][0]['expiresAt'] = 9999999999
    after_top = render_topology_from_rows(rows_after, {777}, CE_PEER)
    if hasattr(after_top, 'format') and after_top.format == 'png':
        _img_b64 = base64.b64encode(after_top.data).decode()
        after_body = f"<img src='data:image/png;base64,{_img_b64}' style='max-width:600px'/>"
    else:
        after_body = after_top.data
    after = HTML(banner('Consumer', '5 Mbps (medium tier)', '#1b5e20').data + after_body)
    return (after,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The toggle
    """)
    return


@app.cell
def _(after, before, toggle_before_after):
    toggle_before_after(before, after)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## How the highlight works

    `render_topology_from_rows` accepts a set of "active" agreement IDs. For every slot whose `agreementId` is in that set, the helper emits a `linkStyle <idx> stroke:#1b5e20,stroke-width:3px` line in the mermaid source. Mermaid's `linkStyle` overrides the default edge style on a per-edge basis.

    In the BEFORE frame, the active set is empty → no edges highlighted, banner is gray.
    In the AFTER frame, the active set is `{777}` → the medium-tier edge (the one whose `agreementId == 777`) is green, banner is green.

    To run a real before/after with the negotiation actually firing: run [06 — end to end](06_end_to_end.py) once, then re-run cell 7 of this notebook with the live `agreementId` from `provider/inventory.txt`.

    Next: [07d — router config](07d_network_router_config.py).
    """)
    return


if __name__ == "__main__":
    app.run()
