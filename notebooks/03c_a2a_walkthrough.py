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
    # 03c — A2A walkthrough

    Drive the provider’s `BandwidthProviderExecutor` in-process. No port; no httpx; no real client. We fabricate a `RequestContext` and an `EventQueue`, and capture the executor’s enqueued events.
    """)
    return


@app.cell
def _():
    import sys, pathlib
    _ROOT = pathlib.Path(__file__).resolve().parent.parent
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))

    from notebooks._viz import render_chat_log, render_mermaid
    from shared.config import Config
    from provider.agent_executor import BandwidthProviderExecutor
    from provider.mcp_server import build_mcp_server
    from a2a.types import Message, Part
    from google.protobuf.json_format import MessageToDict, ParseDict
    from google.protobuf.struct_pb2 import Struct, Value
    from unittest.mock import MagicMock

    PROVIDER = '0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d'
    cfg = Config(provider_private_key=PROVIDER, sdn_mock=True)
    mcp, _ = build_mcp_server(cfg)
    executor = BandwidthProviderExecutor(mcp)
    print('executor ready')
    return (
        MagicMock,
        Message,
        MessageToDict,
        ParseDict,
        Part,
        Struct,
        Value,
        executor,
        render_chat_log,
        render_mermaid,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## FakeQueue + helpers

    The real queue (`EventQueue`) ships events to the HTTP transport. For in-process testing we capture them in a list.
    """)
    return


@app.cell
def _(MagicMock, Message, MessageToDict, ParseDict, Part, Struct, Value):
    class FakeQueue:

        def __init__(self):
            self.events = []

        async def enqueue_event(self, e):
            self.events.append(_e)

    def data_part(d):
        s = Struct()
        ParseDict(d, s)
        return Part(data=Value(struct_value=s), media_type='application/json')

    def make_context(payload):
        msg = Message(message_id='m1', parts=[data_part(payload)])
        ctx = MagicMock()
        ctx.message = msg
        ctx.task_id = 't1'
        ctx.context_id = 'c1'
        return ctx

    def payload_of(event):
        return MessageToDict(event.artifact.parts[0].data, preserving_proto_field_name=True)

    return FakeQueue, make_context, payload_of


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Action 1 — `get_catalog`
    """)
    return


@app.cell
def _(FakeQueue, executor, make_context, payload_of):
    import asyncio

    async def run_action(payload):
        q = FakeQueue()
        await executor.execute(make_context(payload), q)
        return q.events
    _events = asyncio.get_event_loop().run_until_complete(run_action({'action': 'get_catalog'}))
    for _e in _events:
        cls = type(_e).__name__
        print(cls)
        if hasattr(_e, 'artifact'):
            print(' ', payload_of(_e))
        elif hasattr(_e, 'status'):
            print(' status =', _e.status.state)
    return asyncio, run_action


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Action 2 — `request_quote`
    """)
    return


@app.cell
def _(asyncio, payload_of, render_chat_log, run_action):
    _events = asyncio.get_event_loop().run_until_complete(run_action({'action': 'request_quote', 'package_id': 'medium', 'consumer_address': '0x000000000000000000000000000000000000dEaD'}))
    log = []
    for _e in _events:
        if hasattr(_e, 'artifact'):
            log.append({'from': 'provider', 'message': str(payload_of(_e))})
    render_chat_log(log)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Action 3 — `activate` (deferred)

    `activate` requires a real signed nonce against a deployed contract. We skip it here because that needs anvil. The full path is exercised in [06 — end to end](06_end_to_end.py).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Internal dispatch
    """)
    return


@app.cell
def _(render_mermaid):
    render_mermaid("""
    graph LR
      A[action: get_catalog] --> M1[MCP get_catalog]
      B[action: request_quote] --> M2[MCP request_quote]
      C[action: activate] --> M3[MCP verify_credential_ownership]
      C --> M4[MCP allocate_bandwidth]
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    The executor's job is just to route. Look at `provider/agent_executor.py:111-173` — `_handle_catalog`, `_handle_quote`, `_handle_activate` are each a few lines that pass-through to the MCP client. Keeping the executor thin means new actions can be added with one match arm + one `_handle_*` helper.

    Next: [04a — graph state schema](04a_graph_state_schema.py).
    """)
    return


if __name__ == "__main__":
    app.run()
