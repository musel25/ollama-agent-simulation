"""
FastMCP server for the bandwidth provider.
Exposes get_catalog and request_quote as MCP tools.
Mounted at /mcp inside provider/app.py.
"""
import json

from fastmcp import FastMCP

from provider.catalog import get_catalog_with_availability, make_quote

mcp = FastMCP("bandwidth-provider")


@mcp.tool()
def get_catalog() -> str:
    """
    Return available bandwidth packages with pricing and slot availability.

    Returns JSON array of objects with fields: packageId, mbps, durationSeconds,
    priceWei (in wei), availableSlots.
    """
    return json.dumps(get_catalog_with_availability())


@mcp.tool()
def request_quote(package_id: str, consumer_address: str) -> str:
    """
    Request a price quote for a bandwidth package.

    Args:
        package_id: One of 'small', 'medium', 'large'.
        consumer_address: The consumer's Ethereum address (0x...).

    Returns:
        JSON with: agreementId (int), priceWei (int), bandwidthMbps (int),
        durationSeconds (int). Or JSON with 'error' key if unavailable.
    """
    quote = make_quote(package_id, consumer_address)
    if quote is None:
        return json.dumps({"error": f"Package '{package_id}' not found or no slots available."})
    return json.dumps(quote)
