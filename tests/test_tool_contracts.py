"""The real registry can recover an opaque composite contract without host access."""

import asyncio
import json
import unittest

import jsonschema

from scripts.postfader_server import prepare_server


class ToolContractsTest(unittest.TestCase):
    def test_registered_lookup_preserves_continuation_and_result_contracts(self):
        server = prepare_server()
        tools = {tool.name: tool for tool in asyncio.run(server.mcp.list_tools())}
        original = tools["postfader_continue_run"].input_schema

        def read(name, **arguments):
            result = asyncio.run(server.mcp.call_tool("fl_get_tool_contract", {
                "tool_name": name, **arguments}))
            self.assertFalse(result.is_error)
            self.assertEqual(json.loads(result.content[0].text), result.structured_content)
            jsonschema.validate(result.structured_content, tools["fl_get_tool_contract"].output_schema)
            return result.structured_content

        root = read("postfader_continue_run")
        self.assertEqual(root["description"], tools["postfader_continue_run"].description)
        expected_annotations = tools["postfader_continue_run"].annotations.model_dump(
            mode="json", by_alias=True, exclude_none=True)
        self.assertEqual(root["annotations"], expected_annotations)
        root["annotations"]["readOnlyHint"] = "changed by caller"
        self.assertEqual(read("postfader_continue_run")["annotations"], expected_annotations)
        self.assertEqual(root["schema_fragment"], {k: v for k, v in original.items() if k != "$defs"})
        self.assertIn("/$defs/ProductionRunDelta", root["references"])
        delta = read("postfader_continue_run", json_pointer="/$defs/ProductionRunDelta")
        self.assertNotIn("description", delta)
        self.assertNotIn("annotations", delta)
        self.assertEqual(delta["schema_fragment"], original["$defs"]["ProductionRunDelta"])
        # This precise continuation was impossible to form from `delta: unknown`.
        request = {"run_id": "0" * 32, "delta": {"mode": "resume", "operations": []}}
        jsonschema.validate(request, {**root["schema_fragment"], "$defs": original["$defs"]})
        from fl_studio_mcp.production_runs import ProductionRunDelta
        self.assertEqual(ProductionRunDelta.model_validate(request["delta"]).mode, "resume")
        output = read("postfader_get_run", schema_section="output")
        self.assertEqual(output["schema_fragment"], {k: v for k, v in
            tools["postfader_get_run"].output_schema.items() if k != "$defs"})
        self.assertIn("$defs", original)  # Reading fragments must not mutate the live catalog.
        annotations = tools["fl_get_tool_contract"].annotations
        self.assertTrue(annotations.read_only_hint)
        self.assertFalse(annotations.open_world_hint)


if __name__ == "__main__":
    unittest.main()
