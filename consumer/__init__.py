"""
Consumer agent — the buyer side of the bandwidth trade.

This package implements the consumer AI agent: a FastAPI app that
hosts a local MCP server, drives a LangGraph state machine over a
local Ollama LLM, and talks to the provider over A2A.

Entry point:
    consumer.app:app  (uvicorn; port 8001)

Key modules:
    app           — FastAPI app and /chat endpoint
    graph         — LangGraph state machine (browse → quote → lock → settle → present → summary)
    mcp_server    — In-process MCP server exposing tools to the LLM
    a2a_client    — A2A SDK client wrapping calls to the provider
    agent_card    — Builds the published Agent Card

See docs/04-architecture.md for the full picture.
"""
