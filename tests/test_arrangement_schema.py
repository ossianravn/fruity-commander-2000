"""Verify the MCP arrangement result and revision handoff with a native-reader double."""

import asyncio
import json
import unittest
from unittest.mock import patch

import jsonschema

from scripts.automation_edit import AutomationRevision
from scripts.postfader_server import prepare_server


class ArrangementSchemaTest(unittest.TestCase):
    def test_readback_survives_mcp_serialization_and_supplies_revision_input(self):
        points = [{"time_qn": 0.0, "value": 0.20000000298023224, "tension": 0.0, "curve": 0},
                  {"time_qn": 8.0, "value": 0.699999988079071, "tension": 0.0, "curve": 0}]
        observed = {
            "arrangement_index": 0,
            "clips": [{"index": 0, "start_tick": 1536, "source_id": 151552,
                       "length_tick": 768, "track": 2, "muted": False,
                       "source_range_bytes": "0000000000000000"}],
            "automation": [{"channel_index": 2, "source_event": 131072, "points": points}],
            "links": [{"source_event": 131072, "target_event": 102474}],
            "time_selection": {"start_tick": -1, "end_tick": -1, "active": False},
            "project": {"process_id": 123, "path": None, "engine_sha256": "a" * 64,
                        "identity_basis": "qualified_native_project_path_read"},
            "verification": "native_object_readback",
        }
        server = prepare_server()

        async def inspect():
            catalog = await server.mcp.list_tools()
            schema = next(t.output_schema for t in catalog if t.name == "fl_inspect_native_arrangement")
            self.assertIsNotNone(schema)
            result = await server.mcp.call_tool("fl_inspect_native_arrangement", {})
            return schema, result.model_dump(mode="json", by_alias=True)

        with patch("scripts.automation_tool.inspect_arrangement", return_value=observed):
            schema, result = asyncio.run(inspect())
        self.assertFalse(result.get("isError", False))
        self.assertEqual(result["structuredContent"], observed)
        self.assertEqual(json.loads(result["content"][0]["text"]), observed)
        jsonschema.validate(result["structuredContent"], schema)
        source = result["structuredContent"]["automation"][0]
        revision = AutomationRevision(source_event=source["source_event"], expected_points=source["points"],
            points=[{"time_qn": 0, "value": .3}, {"time_qn": 8, "value": .6}])
        self.assertEqual([p.model_dump() for p in revision.expected_points], points)


if __name__ == "__main__":
    unittest.main()
