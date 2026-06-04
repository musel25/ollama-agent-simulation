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
    # 04d — Graph walkthrough

    Run the consumer graph with stubbed tools and a stubbed LLM. After each node, render the state diff (added/changed/removed keys) so the data flow is visible.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_state, render_chat_log
    from shared.config import Config
    from consumer.graph import build_graph
    from langchain_ollama import ChatOllama
    import json

    CONSUMER = '0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a'
    return (
        CONSUMER,
        ChatOllama,
        Config,
        build_graph,
        json,
        render_chat_log,
        render_state,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Stub the tools and the LLM
    """)
    return


@app.cell
def _(CONSUMER, ChatOllama, Config, build_graph, json):
    fake_catalog = [
        {'packageId': 'small',  'mbps': 2, 'durationSeconds': 600, 'priceWei': 10**16, 'availableSlots': 1},
        {'packageId': 'medium', 'mbps': 5, 'durationSeconds': 600, 'priceWei': 2*10**16, 'availableSlots': 1},
        {'packageId': 'large',  'mbps': 8, 'durationSeconds': 600, 'priceWei': 8*10**16, 'availableSlots': 1},
    ]

    async def discover(url): return json.dumps({'name': 'P', 'version': '1',
        'skills': ['get_catalog', 'request_quote', 'activate']})
    async def browse(url): return json.dumps(fake_catalog)
    async def quote(url, pkg): return json.dumps({'agreementId': '777', 'priceWei': 2*10**16,
        'bandwidthMbps': 5, 'durationSeconds': 600})
    def lock(aid): return 'OK 0xdeadbeef'
    def settle(aid): return 'OK tokenId=99'
    async def present(url, tid): return json.dumps({'status': 'active', 'bandwidthMbps': 5, 'tokenId': tid})
    def verify(tid): return json.dumps({'ok': True, 'owner': '0xC', 'ownerIsConsumer': True,
        'agreementId': 777, 'mbps': 5, 'durationSeconds': 600,
        'secondsRemaining': 600, 'endpoint': 'clab://pe1/eth-1.100'})

    tools = {'discover_provider': discover, 'browse_catalog': browse,
             'request_quote': quote, 'lock_payment': lock,
             'await_settlement': settle, 'present_credential': present,
             'verify_credential': verify}

    class _R:
        def __init__(self, c): self.content = c
    async def fake_ainvoke(self, prompt, *a, **kw):
        return _R('medium' if 'EXACTLY ONE WORD' in prompt else 'ok')
    ChatOllama.ainvoke = fake_ainvoke

    cfg = Config(consumer_private_key=CONSUMER)
    graph = build_graph(cfg, tools)
    print('graph compiled')
    return (graph,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Stream node-by-node with state diffs
    """)
    return


@app.cell
def _(graph, render_state):
    import asyncio
    from IPython.display import display, HTML

    async def stream_with_diff():
        initial = {'user_message': 'I need 5 Mbps',
                   'provider_url': 'http://provider:8002',
                   'log': [], 'thinking': []}
        prev = dict(initial)
        diffs = []
        async for step in graph.astream(initial):
            for node, output in step.items():
                cur = {**prev, **(output if isinstance(output, dict) else {})}
                diffs.append((node, prev, cur))
                prev = cur
        return diffs

    diffs = asyncio.get_event_loop().run_until_complete(stream_with_diff())
    for node, prev_s, cur_s in diffs:
        display(HTML(f"<h4 style='margin:8px 0 4px'>node: <code>{node}</code></h4>"))
        display(render_state(cur_s, prev_s))
    return asyncio, display


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Final state and conversation log
    """)
    return


@app.cell
def _(asyncio, display, graph, render_chat_log, render_state):
    final = asyncio.get_event_loop().run_until_complete(graph.ainvoke({
        'user_message': 'I need 5 Mbps',
        'provider_url': 'http://provider:8002',
        'log': [], 'thinking': []}))
    display(render_chat_log(final['log']))
    display(render_state(final))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What we just observed

    - Every node added 1-3 keys to state, often `log` (append-mutated).
    - `pick_tier_node` set `chosen_tier='medium'` (the stubbed LLM always returns "medium").
    - `quote_node` set `agreement_id='777'`.
    - `settle_node` set `token_id=99` on the first attempt.
    - `verify_node` validated the on-chain mbps match (stubbed to `True`).
    - `summary_node` populated `final_response`.

    Real run with anvil + Ollama: [06 — end to end](06_end_to_end.py).
    Provider-side companion: [05a — inventory & expiry](05a_inventory_and_expiry.py).
    """)
    return


if __name__ == "__main__":
    app.run()
