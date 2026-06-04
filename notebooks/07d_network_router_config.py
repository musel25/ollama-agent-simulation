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
    # 07d — Router config

    What `allocate_bandwidth` and `verify_bandwidth` actually push to the network — when `SDN_MOCK=false`. We compare the mock no-op JSON against the real gNMI Set body and tc command.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from shared.config import Config
    import asyncio, json
    from fastmcp import Client
    from provider.mcp_server import build_mcp_server

    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    return Client, Config, PROVIDER, asyncio, build_mcp_server, json


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Mock path — `SDN_MOCK=true`
    """)
    return


@app.cell
def _(Client, Config, PROVIDER, asyncio, build_mcp_server, json):
    cfg_mock = Config(provider_private_key=PROVIDER, sdn_mock=True)
    mcp_mock, _ = build_mcp_server(cfg_mock)

    async def alloc(mcp):
        async with Client(mcp) as c:
            r = await c.call_tool("allocate_bandwidth",
                {"customer_id": "0xC0FFEE", "pe": "pe1",
                 "subinterface": "ethernet-1/3.0", "mbps": 5.0})
            return json.loads(r.content[0].text)

    mock_resp = asyncio.get_event_loop().run_until_complete(alloc(mcp_mock))
    mock_resp
    return (mcp_mock,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The mock body is constant: `gnmi_pushed=False`, `tc_applied=False`, `message="mocked"`. It returns the request parameters echoed back so callers can stub responses without ever leaving the python process.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Real path — what `SDN_MOCK=false` would push
    """)
    return


@app.cell
def _():
    from IPython.display import Markdown
    Markdown("""
    ### gNMI Set request (illustrative — Nokia SR Linux)

    ```yaml
    update:
      - path: /interface[name=ethernet-1/3]/subinterface[index=0]/qos
        val:
          input:
            classifiers:
              ipv4-classifier: customer-class
            policers:
              - name: customer-policer
                cir: 5000000        # 5 Mbps in bits/sec
                cbs: 625000
                action: drop-on-exceed
    ```

    This is what `srl_bandwidth.bandwidth.allocate_bandwidth(ServiceRequest(...))` produces internally for SR Linux's gNMI server. The path uses YANG-style keying for the subinterface; `cir` (committed information rate) is the rate limit; `cbs` (committed burst size) is the bucket size; `action` is what happens to over-rate packets.

    ### tc tbf command (illustrative — CE host)

    ```bash
    tc qdisc add dev eth1.100 root tbf rate 5mbit burst 32kbit latency 50ms
    ```

    `tbf` is the Linux Token Bucket Filter qdisc. `rate` matches the policer; `burst` is the per-packet credit; `latency` caps queue delay before drops kick in. This runs on the CE host directly, applied to the subinterface that mirrors the PE-side policer.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Verify probe — iperf3 UDP between CE peers
    """)
    return


@app.cell
def _(Client, asyncio, json, mcp_mock):
    async def verify(mcp):
        async with Client(mcp) as c:
            r = await c.call_tool("verify_bandwidth",
                {"src_ce": "ce3", "dst_ce": "ce4", "expected_mbps": 5.0})
            return json.loads(r.content[0].text)
    verify_resp = asyncio.get_event_loop().run_until_complete(verify(mcp_mock))
    verify_resp
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Mock returns `{"passed": True, "measured_mbps": expected_mbps, "message": "mocked"}`. Real path runs (illustratively):

    ```bash
    # on dst_ce (ce4):
    iperf3 -s -p 5201 -1

    # on src_ce (ce3):
    iperf3 -c <ce4-addr> -u -b 5M -t 5 -p 5201 --json
    ```

    Then it parses the iperf3 JSON output for `end.sum.bits_per_second`, divides by `1e6`, and compares against `expected_mbps` with `tolerance` (default 0.2 → ±20%).

    Returns `{"passed": bool, "measured_mbps": float, "expected_mbps": float, "tolerance": float}`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What the repo does NOT ship

    The clab topology file (a `.clab.yml` defining `pe1`, `pe2`, `ce1`-`ce4`, links, gNMI credentials) is NOT in this repo. The real-SDN backend is a separate project: [`musel25/srl-gnmi-bandwidth-poc`](https://github.com/musel25/srl-gnmi-bandwidth-poc) — already wired in via `[tool.uv.sources]` in `pyproject.toml`.

    To run with `SDN_MOCK=false`:
    1. Stand up the upstream clab topology.
    2. Ensure `pe1`, `pe2` are reachable from the provider host on port 57400 (gNMI).
    3. Set `SDN_MOCK=false` in the provider's environment.
    4. The provider's three SDN tools start delegating to `srl_bandwidth.bandwidth.*` instead of returning mocks.

    For everything else in this series (notebooks 00-07c plus 06), `SDN_MOCK=true` is enough — and that's what the rest of the codebase defaults to.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## End of the series

    You've now seen every layer:
    - **Chain** (01a-d): contracts, lifecycle, NFT credential, walkthrough.
    - **MCP** (02a-c): tool protocol, both servers' catalogs, in-process calls.
    - **A2A** (03a-c): agent protocol, both cards, executor walkthrough.
    - **LangGraph** (04a-d): consumer state machine, prompts, streaming.
    - **Inventory** (05a): slot pool, event listener, expiry sweep.
    - **End-to-end** (06): full negotiation with real Ollama.
    - **Network** (07a-d): SDN model, topology, before/after, router config.

    To extend the system: add a new tier to `provider/inventory.txt`, add a new skill to the provider's AgentCard + executor, or swap `srl-bandwidth` for a different SDN backend by changing the import. The architectural seams are all visible in the code — nothing is buried.
    """)
    return


if __name__ == "__main__":
    app.run()
