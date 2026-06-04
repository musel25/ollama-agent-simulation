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
    # 06 — End-to-end

    The whole flow in one notebook: anvil + deployed contracts + provider FastAPI + consumer FastAPI + real Ollama. POST `/chat` with a free-form bandwidth request and watch the negotiation.

    > **Prereq:** `anvil` + `forge` on PATH; `ollama serve` running with `llama3.2:3b` pulled.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import (render_mermaid, render_chat_log, render_event_timeline)
    import os, socket, threading, time, asyncio
    from pathlib import Path
    import httpx
    import uvicorn

    return (
        Path,
        asyncio,
        httpx,
        os,
        render_chat_log,
        render_event_timeline,
        render_mermaid,
        socket,
        threading,
        time,
        uvicorn,
    )


@app.cell
def _(socket, threading, time, uvicorn):
    DEPLOYER = '0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'

    def free_port():
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def serve(app, port):
        cfg = uvicorn.Config(app, host='127.0.0.1', port=port,
                              log_level='warning', lifespan='on')
        server = uvicorn.Server(cfg)
        t = threading.Thread(target=server.run, daemon=True)
        t.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not server.started:
            time.sleep(0.05)
        return server, t

    return CONSUMER, DEPLOYER, PROVIDER, free_port, serve


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## End-to-end sequence
    """)
    return


@app.cell
def _(render_mermaid):
    render_mermaid("""
    sequenceDiagram
      participant U as User
      participant CG as Consumer LangGraph
      participant CM as Consumer MCP
      participant PA as Provider A2A
      participant PM as Provider MCP
      participant CH as Chain (anvil)
      participant OL as Ollama
      U->>CG: POST /chat "I need 5 Mbps"
      CG->>CM: discover_provider
      CM->>PA: GET /.well-known/agent-card.json
      CG->>CM: browse_catalog
      CM->>PA: A2A get_catalog
      PA->>PM: MCP get_catalog
      CG->>OL: pick_tier prompt
      OL-->>CG: "medium"
      CG->>CM: request_quote
      CM->>PA: A2A request_quote
      PA->>PM: MCP request_quote
      CG->>CM: lock_payment
      CM->>CH: requestAgreement{value}
      CH-->>PM: AgreementRequested log
      PM->>CH: mint(...) + approve + deposit
      CH-->>CH: atomic swap (NFT→consumer, ETH→provider)
      CG->>CM: await_settlement (poll)
      CM->>CH: getAgreement
      CG->>CM: present_credential (signed nonce)
      CM->>PA: A2A activate
      PA->>PM: verify_credential_ownership + allocate_bandwidth
      CG->>CM: verify_credential
      CM->>CH: ownerOf + getTokenMetadata
      CG->>OL: summary prompt
      CG-->>U: final_response
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Spawn anvil + deploy
    """)
    return


@app.cell
def _(CONSUMER, DEPLOYER, PROVIDER):
    from shared.anvil import anvil
    from shared.config import Config
    from shared.deploy import deploy_contracts

    ctx = anvil(port=18545)
    rpc_url = ctx.__enter__()
    cfg = Config(rpc_url=rpc_url, deployer_private_key=DEPLOYER,
                 provider_private_key=PROVIDER, consumer_private_key=CONSUMER,
                 sdn_mock=True)
    addrs = deploy_contracts(cfg)
    print('deployed:', addrs)
    return ctx, rpc_url


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Start provider + consumer FastAPI in-process
    """)
    return


@app.cell
def _(CONSUMER, PROVIDER, free_port, os, rpc_url, serve):
    provider_port = free_port()
    consumer_port = free_port()
    provider_url = f'http://127.0.0.1:{provider_port}'
    consumer_url = f'http://127.0.0.1:{consumer_port}'

    os.environ.update({
        'RPC_URL': rpc_url,
        'CONSUMER_PRIVATE_KEY': CONSUMER,
        'PROVIDER_PRIVATE_KEY': PROVIDER,
        'PROVIDER_BASE_URL': provider_url,
        'CONSUMER_BASE_URL': consumer_url,
        'PROVIDER_A2A_URLS': provider_url,
        'SDN_MOCK': 'true',
        'OLLAMA_HOST': os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434'),
        'OLLAMA_MODEL': os.environ.get('OLLAMA_MODEL', 'llama3.2:3b'),
    })

    from provider.app import app as provider_app
    from consumer.app import app as consumer_app
    ps, pt = serve(provider_app, provider_port)
    cs, ct = serve(consumer_app, consumer_port)
    print('provider:', provider_url)
    print('consumer:', consumer_url)
    return consumer_url, cs, ps


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Inventory before
    """)
    return


@app.cell
def _(Path):
    from IPython.display import HTML
    inv_before = Path("provider/inventory.txt").read_text()
    HTML(f"<pre style='font-size:11px'>{inv_before}</pre>")
    return HTML, inv_before


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Run one negotiation
    """)
    return


@app.cell
def _(asyncio, consumer_url, httpx, render_chat_log):
    async def chat():
        async with httpx.AsyncClient(timeout=180.0) as http:
            r = await http.post(f'{consumer_url}/chat',
                                json={"message": "I need 5 Mbps for 10 minutes"})
            return r.json()
    body = asyncio.get_event_loop().run_until_complete(chat())
    print('final:', body['response'])
    render_chat_log(body['log'])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Inventory after
    """)
    return


@app.cell
def _(HTML, Path, inv_before):
    inv_after = Path("provider/inventory.txt").read_text()
    HTML(f"<table><tr><th>before</th><th>after</th></tr>"
         f"<tr><td><pre style='font-size:11px'>{inv_before}</pre></td>"
         f"<td><pre style='font-size:11px'>{inv_after}</pre></td></tr></table>")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## On-chain events
    """)
    return


@app.cell
def _(asyncio, consumer_url, httpx, render_event_timeline):
    async def chain():
        async with httpx.AsyncClient(timeout=10.0) as http:
            return (await http.get(f'{consumer_url}/chain_events')).json()
    events = asyncio.get_event_loop().run_until_complete(chain())
    render_event_timeline(events)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Teardown
    """)
    return


@app.cell
def _(cs, ctx, ps):
    ps.should_exit = True
    cs.should_exit = True
    ctx.__exit__(None, None, None)
    print('done')
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Recap: one POST request, ~10 inter-agent messages, 3 chain transactions, 2 LLM calls, ~5 seconds wall clock. Everything we explored layer-by-layer in 01-05a happened, in order.

    Next: [07a — network concepts](07a_network_concepts.py).
    """)
    return


if __name__ == "__main__":
    app.run()
