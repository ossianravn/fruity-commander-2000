"""Preserve actual result fields when adding a validated MCP structured payload."""

import json

from mcp.types import CallToolResult, TextContent


def structured_result(value: dict) -> CallToolResult:
    # SDK 2.0.1's automatic TypedDict conversion emits absent optional fields as
    # null. Its explicit CallToolResult path validates without rewriting payloads.
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(value, ensure_ascii=False, indent=2))],
        structured_content=value,
    )
