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
    # 03a — A2A concepts

    What A2A is, the agent-card discovery model, and how an executor turns inbound messages into outbound events.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What A2A is

    [A2A](https://google.github.io/A2A/) — Google's **Agent-to-Agent** SDK — is a protocol and SDK for agent-to-agent interoperability. The wire format is **Protocol Buffers**; the transport in this repo is **JSON-RPC over HTTP**.

    Each agent advertises itself with an **AgentCard** at `/.well-known/agent-card.json`. The card lists the agent's name, version, description, capabilities, supported interfaces (URLs + protocol bindings), and skills.

    Skills are typed actions: each has an `id`, a human-readable name and description, and example payloads. The provider exposes three skills (`get_catalog`, `request_quote`, `activate`); the consumer exposes one (`purchase_bandwidth`).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The executor pattern

    A2A servers don't expose handlers per-skill; they expose a single `AgentExecutor` whose `execute(context, queue)` method receives the inbound message and enqueues outbound events.

    Inbound: `RequestContext.message` is an `a2a.types.Message` with one or more `parts`. We use a single `data` part — a `google.protobuf.Value(struct_value=Struct)` carrying a JSON-shaped payload.

    Outbound: enqueue `TaskArtifactUpdateEvent` (with the result data) followed by `TaskStatusUpdateEvent` (with `state=TASK_STATE_COMPLETED`). Errors enqueue an artifact with an `error` field and `state=TASK_STATE_FAILED`.

    This split (executor + queue) lets a single executor stream multiple events for one request, which matters for long-running or multi-stage actions.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why protobuf

    A2A's wire format is generated from `a2a.proto`. That means the SDK gives us protobuf message classes (`Message`, `Part`, `Value`, `TaskStatusUpdateEvent`...). To put a Python dict into a `Part`, you build a `google.protobuf.Struct` and wrap it in `google.protobuf.Value(struct_value=Struct)`. To read it back, you call `MessageToDict(value, preserving_proto_field_name=True)`.

    This is more ceremony than passing dicts around but it gives us cross-language compatibility and version-stable wire format.
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
    sequenceDiagram
      participant C as Consumer (a2a.client)
      participant H as Provider HTTP /a2a (JSONRPC)
      participant E as Executor
      participant Q as EventQueue
      C->>H: send_message(Message[parts])
      H->>E: execute(context, queue)
      E->>Q: TaskArtifactUpdateEvent (data part)
      E->>Q: TaskStatusUpdateEvent COMPLETED
      Q-->>H: stream events
      H-->>C: artifact_update chunk
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Reading streamed responses

    The client iterates a stream of `StreamResponse` chunks. Each chunk has a `WhichOneof('payload')` — usually `artifact_update` (a `TaskArtifactUpdateEvent`) or `task` (a complete `Task` snapshot). The result is in `artifact_update.artifact.parts[0].data`.

    Our `consumer/a2a_client.py` opens a fresh `httpx.AsyncClient` per call, builds the request, and walks the stream until it finds a `data` part. Cost: one resolve + one HTTP round-trip per call; we don't optimize for high call rates.

    Next: [03b — agent cards](03b_a2a_agent_cards.py), then [03c — walkthrough](03c_a2a_walkthrough.py).
    """)
    return


if __name__ == "__main__":
    app.run()
