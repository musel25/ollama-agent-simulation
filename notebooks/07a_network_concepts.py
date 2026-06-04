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
    # 07a — Network concepts

    The provider's three SDN tools (`allocate_bandwidth`, `revoke_bandwidth`, `verify_bandwidth`) are what make a "credential" actually translate to "real bandwidth on a real network". This notebook unpacks the model.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What `SDN_MOCK` gates

    `shared/config.py` carries `sdn_mock: bool = True`. The provider MCP server (`provider/mcp_server.py`) inspects this flag inside the three SDN tools. When `True`:

    - `allocate_bandwidth` returns `{"success": True, ..., "gnmi_pushed": False, "tc_applied": False, "message": "mocked"}`.
    - `revoke_bandwidth` returns `{"status": "revoked", "mocked": True}`.
    - `verify_bandwidth` returns `{"passed": True, "measured_mbps": expected_mbps or 0.0, "message": "mocked"}`.

    When `False`, the tools delegate to the [`srl-bandwidth`](https://github.com/musel25/srl-gnmi-bandwidth-poc) package (a `[tool.uv.sources]` git dep), which talks gNMI to a Nokia SR Linux containerlab topology.

    The mock path is fully self-contained — no clab, no gNMI, no iperf3. The real path needs an external clab topology that this repo does NOT ship.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mental model: three layers per slot

    Every active slot is **three configurations** running in parallel:

    1. **gNMI policer at the PE.** A QoS policer on the customer's subinterface limits the rate. Configured via gNMI Set against the SR Linux router.

    2. **`tc tbf` queue on the CE.** Token-bucket-filter qdisc on the CE host's network interface. Belt-and-suspenders: even if the policer fails, the CE itself shapes traffic.

    3. **iperf3 verify probe between CE peers.** UDP probe from `src_ce` to `dst_ce` (defined in `provider/app.py:31` as `CE_PEER`). Measures actual throughput, returns whether it's within tolerance of the expected Mbps.

    `allocate_bandwidth` pushes (1) and (2). `revoke_bandwidth` removes them. `verify_bandwidth` runs (3).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why `endpoint = clab://<pe>/<subinterface>`

    The NFT's `endpoint` field is the literal SDN identifier. When the consumer presents a credential, the provider parses out `<pe>` and `<subinterface>`, then maps to the bound `<ce>` via the slot pool's `lookup(agreementId)`.

    `<pe>` is the PE router name in the clab topology (`pe1`, `pe2`).
    `<subinterface>` is the SR Linux subinterface (e.g. `ethernet-1/3.0`).
    `<ce>` is the CE host name (e.g. `ce1`).

    Together they uniquely identify which "wire" gets configured for this lease.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## CE peer pairing

    `provider/app.py:31` hard-codes:

    ```python
    CE_PEER = {"ce1": "ce2", "ce2": "ce1", "ce3": "ce4", "ce4": "ce3"}
    ```

    Why? `verify_bandwidth` needs a destination. iperf3 measures throughput between two endpoints. The peering says: "if we're verifying ce1's bandwidth, blast traffic at ce2."

    This implies the topology has at least 4 CE hosts in two peer pairs. The actual clab definition lives in upstream `srl-gnmi-bandwidth-poc`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why three tools, not one

    You could imagine a single `set_bandwidth` tool that internally allocates, then verifies. Why split?

    - **`allocate_bandwidth`** is part of the activation path (called by `present_credential` flow → `_handle_activate` → MCP).
    - **`revoke_bandwidth`** is part of the expiry path (called by the expiry sweep).
    - **`verify_bandwidth`** is independent: it can be called anytime after activation to debug "is the network actually configured?".

    Splitting them keeps each tool's failure mode isolated. A bad policer push doesn't accidentally trigger an iperf3 storm. A failed verify doesn't tear down a working allocation.
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
    graph TB
      subgraph Provider
        A[allocate_bandwidth]
        R[revoke_bandwidth]
        V[verify_bandwidth]
      end
      subgraph PE [PE router]
        G[gNMI policer]
      end
      subgraph CE [CE host]
        T[tc tbf]
        I[iperf3 server]
      end
      A --> G
      A --> T
      R --> G
      R --> T
      V --> I
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Next: [07b — topology](07b_network_topology.py), [07c — before/after](07c_network_before_after.py), [07d — router config](07d_network_router_config.py).
    """)
    return


if __name__ == "__main__":
    app.run()
