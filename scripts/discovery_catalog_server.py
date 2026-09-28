"""Metadata-only MCP fixture for controlled discovery measurements, never FL execution.

Replays a captured product catalog under chosen server guidance. It imports no
product host code and rejects host execution; this is not a product server mode.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.mcpserver import MCPServer
from mcp.server.stdio import stdio_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.tool_contracts import lookup, register


async def contract_definition():
    registry = MCPServer("contract-metadata")
    register(SimpleNamespace(mcp=registry))
    return (await registry.list_tools())[0].model_dump(mode="json", by_alias=True, exclude_none=True)


async def run(options):
    catalog = json.loads(options.catalog.read_text(encoding="utf-8"))["catalog"]
    if options.contract_lookup:
        catalog.append(await contract_definition())
    tools = [types.Tool.model_validate(tool) for tool in catalog]

    async def list_tools(context, params):
        return types.ListToolsResult(tools=tools)

    async def handle_call(context, params):
        # `executed` records host execution; the optional metadata lookup is local.
        with options.call_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"tool": params.name, "executed": False}) + "\n")
        if options.contract_lookup and params.name == "fl_get_tool_contract":
            try:
                result = lookup(catalog, **(params.arguments or {}))
            except (ValueError, TypeError) as error:
                return types.CallToolResult(is_error=True, content=[types.TextContent(
                    type="text", text=str(error))])
            return types.CallToolResult(structured_content=result, content=[types.TextContent(
                type="text", text=json.dumps(result, ensure_ascii=False))])
        return types.CallToolResult(is_error=True, content=[types.TextContent(
            type="text", text="Metadata-only evaluation: host execution is unavailable.")])

    server = Server("postfader-fl-studio-mcp", version="10.0.0",
        instructions=options.instructions.read_text(encoding="utf-8"),
        on_list_tools=list_tools, on_call_tool=handle_call)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--instructions", type=Path, required=True)
    parser.add_argument("--call-log", type=Path, required=True)
    parser.add_argument("--contract-lookup", action="store_true", help="Include the evaluation-only metadata lookup candidate")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
