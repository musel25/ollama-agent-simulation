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
    # 02a — MCP concepts

    What MCP is, what FastMCP gives us, and why both agents are MCP servers.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## What MCP is

    MCP — **Model Context Protocol** — is a JSON-RPC 2.0 protocol for plugging tools, resources, and prompts into LLM applications. Originally built by Anthropic to give Claude controlled access to local capabilities, MCP is now a multi-vendor standard.

    A server exposes:
    - **Tools** — callable functions with JSON-Schema-typed inputs/outputs.
    - **Resources** — addressable read-only blobs (files, configs, etc.).
    - **Prompts** — reusable LLM prompt templates.

    This repo only uses **tools**.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## FastMCP

    [FastMCP](https://github.com/jlowin/fastmcp) is a Python framework that turns plain functions into MCP servers via a decorator:

    ```python
    from fastmcp import FastMCP

    mcp = FastMCP("my-server")

    @mcp.tool()
    def add(a: int, b: int) -> int:
        \"\"\"Add two numbers.\"\"\"
        return a + b
    ```

    The decorator inspects the function's type hints + docstring, derives a JSON Schema for the inputs, and registers the tool. Callers reach the tool via `fastmcp.Client(mcp).call_tool("add", {"a": 1, "b": 2})` — no manual marshalling.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Transports

    | Transport | When | This repo |
    |---|---|---|
    | **In-process** | Same Python process. Calls go through normal function dispatch with JSON-Schema validation in front. | Tests, all notebooks. |
    | **stdio** | Subprocess — server writes JSON-RPC on stdout, reads on stdin. Used by Claude Desktop. | Not used. |
    | **HTTP** | Server is a web app at `/mcp` (or wherever you mount it). Clients open an HTTP session per call. | The provider FastAPI app mounts its FastMCP server at `/`; the consumer would mount its own if needed. |
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Why both agents are MCP servers

    The provider has tools the consumer (or any external LLM) needs to call: `get_catalog`, `request_quote`, `mint_credential`, etc.

    The consumer ALSO has tools: `lock_payment`, `await_settlement`, `verify_credential`, `present_credential`, etc. They're consumed by the consumer's own LangGraph workflow today, but they're packaged as MCP tools so a higher-level orchestrator could drive a fleet of consumer agents over MCP.

    This is the symmetry that makes the architecture composable: every action either side can take is an MCP tool call, regardless of who initiates it.
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
    graph LR
      caller[Caller code]
      client[fastmcp.Client]
      server[FastMCP server]
      fn[Decorated python fn]
      caller -->|"call_tool(name, args)"| client
      client -->|JSON-RPC| server
      server -->|"validates against<br/>JSON Schema"| fn
      fn -->|return value| server
      server -->|JSON-RPC response| client
      client -->|"result.content[0].text"| caller
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Next: [02b — tool catalog](02b_mcp_tool_catalog.py) — see every tool from both servers rendered as cards. Then [02c — walkthrough](02c_mcp_walkthrough.py) — actually call the tools.
    """)
    return


if __name__ == "__main__":
    app.run()
