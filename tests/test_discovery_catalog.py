"""The comparison fixture serves metadata over MCP but cannot execute host tools."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class DiscoveryCatalogTest(unittest.IsolatedAsyncioTestCase):
    async def test_frozen_catalog_and_guidance_without_host_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog, instructions, log = [root / name for name in ("catalog.json", "guide.txt", "calls.jsonl")]
            tool = {"name": "fl_save_project", "description": "Fixture only",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {"type": "object", "properties": {"saved": {"type": "boolean"}}}}
            catalog.write_text(json.dumps({"catalog": [tool]}), encoding="utf-8")
            instructions.write_text("Comparison guidance Æøå", encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts/discovery_catalog_server.py"
            server = StdioServerParameters(command=sys.executable, args=[str(script),
                "--catalog", str(catalog), "--instructions", str(instructions), "--call-log", str(log)])
            async with stdio_client(server) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    discovered = await session.discover()
                    self.assertEqual(discovered.instructions, "Comparison guidance Æøå")
                    actual = (await session.list_tools()).tools
                    self.assertEqual([t.model_dump(mode="json", by_alias=True, exclude_none=True)
                                      for t in actual], [tool])
                    result = await session.call_tool("fl_save_project", {})
                    self.assertTrue(result.is_error)
                    self.assertIsNone(result.structured_content)
                    self.assertIn("host execution is unavailable", result.content[0].text)
            self.assertEqual(json.loads(log.read_text()), {"tool": "fl_save_project", "executed": False})

    async def test_candidate_returns_selected_contract_without_expanding_references(self):
        delta = {"type": "object", "properties": {
            "mode": {"type": "string", "enum": ["resume", "replace_remaining"],
                     "default": "replace_remaining"},
            "operations": {"type": "array", "items": {"$ref": "#/$defs/Operation"}},
        }}
        tool = {"name": "resume", "inputSchema": {"type": "object", "properties": {
            "delta": {"$ref": "#/$defs/Delta"}}, "$defs": {"Delta": delta,
            "Operation": {"type": "object"}}}, "outputSchema": {"type": "object"}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog, instructions, log = [root / name for name in ("catalog.json", "guide.txt", "calls.jsonl")]
            catalog.write_text(json.dumps({"catalog": [tool]}), encoding="utf-8")
            instructions.write_text("Metadata only", encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts/discovery_catalog_server.py"
            server = StdioServerParameters(command=sys.executable, args=[str(script),
                "--catalog", str(catalog), "--instructions", str(instructions),
                "--call-log", str(log), "--contract-lookup"])
            async with stdio_client(server) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.discover()
                    self.assertEqual([t.name for t in (await session.list_tools()).tools], ["resume", "fl_get_tool_contract"])
                    root_result = (await session.call_tool("fl_get_tool_contract", {"tool_name": "resume"})).structured_content
                    self.assertNotIn("$defs", root_result["schema_fragment"])
                    self.assertEqual(root_result["references"], ["/$defs/Delta"])
                    result = await session.call_tool("fl_get_tool_contract", {
                        "tool_name": "resume", "json_pointer": root_result["references"][0]})
                    self.assertFalse(result.is_error)
                    self.assertEqual(result.structured_content["schema_fragment"], delta)
                    self.assertEqual(result.structured_content["references"], ["/$defs/Operation"])
                    self.assertEqual(json.loads(result.content[0].text), result.structured_content)
                    output = await session.call_tool("fl_get_tool_contract", {
                        "tool_name": "resume", "schema_section": "output"})
                    self.assertEqual(output.structured_content["schema_fragment"], tool["outputSchema"])
                    missing = await session.call_tool("fl_get_tool_contract", {
                        "tool_name": "resume", "json_pointer": "/$defs/Missing"})
                    self.assertTrue(missing.is_error)
                    self.assertTrue((await session.call_tool("resume", {})).is_error)


if __name__ == "__main__":
    unittest.main()
