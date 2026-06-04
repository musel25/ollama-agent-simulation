"""
Provider agent — the seller side of the bandwidth trade.

This package implements the provider AI agent: a FastAPI app that
hosts an MCP server, an A2A executor, an on-chain event listener,
and SDN activation tools.

Entry point:
    provider.app:app  (uvicorn; port 8002)

Key modules:
    app              — FastAPI app, MCP mount, A2A mount, Agent Card route
    agent_executor   — A2A task handler (quote / activate); the trust boundary
    mcp_server       — MCP server: catalog, quote, mint, verify, allocate
    catalog          — Tier metadata, pending quotes, and slot pool wiring
    event_listener   — Polls AgreementRequested events and drives mint+swap
    expiry           — Periodic sweep that revokes SDN for expired slots

See docs/03-architecture.md for the full picture.
"""
