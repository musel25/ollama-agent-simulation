"""
Async MCP client utilities for the consumer agent.

Provides:
- get_provider_tools(): fetch MCP tool schemas from provider
- call_provider_tool(): call a tool on the provider MCP server
- mcp_tool_to_ollama(): convert MCP Tool to Ollama tool dict format
- quote_cache: stores quote results keyed by agreementId string for execute_agreement
"""
import json
import os
from typing import Any

from fastmcp import Client

PROVIDER_MCP_URL = os.environ.get("PROVIDER_MCP_URL", "http://localhost:8002/mcp")

quote_cache: dict[str, dict] = {}


def mcp_tool_to_ollama(tool) -> dict:
    """Convert an MCP Tool object to Ollama's tool dict format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


async def get_provider_tools() -> list:
    """Fetch available tools from the provider's MCP server."""
    async with Client(PROVIDER_MCP_URL) as client:
        return await client.list_tools()


async def call_provider_tool(name: str, args: dict[str, Any]) -> str:
    """
    Call a tool on the provider MCP server and return the text result.
    Automatically caches quote results in quote_cache keyed by agreementId string.
    """
    async with Client(PROVIDER_MCP_URL) as client:
        result = await client.call_tool(name, args)

    text = result.content[0].text if result.content else ""

    if name == "request_quote":
        try:
            data = json.loads(text)
            if "agreementId" in data:
                quote_cache[str(data["agreementId"])] = data
        except (json.JSONDecodeError, KeyError):
            pass

    return text
