import pytest
from consumer.mcp_client import mcp_tool_to_ollama, quote_cache


class FakeTool:
    def __init__(self, name, description, input_schema):
        self.name = name
        self.description = description
        self.inputSchema = input_schema


def test_mcp_tool_to_ollama_shape():
    tool = FakeTool(
        name="get_catalog",
        description="Returns catalog",
        input_schema={"type": "object", "properties": {}},
    )
    result = mcp_tool_to_ollama(tool)
    assert result["type"] == "function"
    assert result["function"]["name"] == "get_catalog"
    assert result["function"]["description"] == "Returns catalog"
    assert result["function"]["parameters"] == {"type": "object", "properties": {}}


def test_mcp_tool_to_ollama_none_description():
    tool = FakeTool(name="x", description=None, input_schema={"type": "object", "properties": {}})
    result = mcp_tool_to_ollama(tool)
    assert result["function"]["description"] == ""


def test_quote_cache_is_dict():
    assert isinstance(quote_cache, dict)
