"""Published persistence schemas preserve observations, uncertainty and MCP errors."""

import asyncio
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema
from mcp.types import CallToolRequestParams

from scripts.postfader_server import prepare_server


class ProjectSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = prepare_server()
        cls.tools = {tool.name: tool for tool in asyncio.run(cls.server.mcp.list_tools())}
        cls.recorded = json.loads(Path(__file__).with_name("fixtures").joinpath(
            "project_results.json").read_text(encoding="utf-8"))

    def call(self, name, result=None, error=None):
        bindings = {
            "fl_get_project_file": ("scripts.project_save.inspect_project_file", {}),
            "fl_save_project": ("scripts.project_save.save_project", {}),
            "fl_save_project_as": ("scripts.project_save_as.save_project_as",
                {"destination_path": self.recorded["save_as"]["result"]["destination_path"]}),
        }
        target, arguments = bindings[name]
        with patch(target, return_value=result, side_effect=error):
            response = asyncio.run(self.server.mcp._handle_call_tool(
                None, CallToolRequestParams(name=name, arguments=arguments)))
        return response.model_dump(mode="json", by_alias=True)

    def assert_result(self, name, result):
        wire = self.call(name, result)
        self.assertFalse(wire.get("isError", False))
        self.assertEqual(wire["structuredContent"], result)
        self.assertEqual(json.loads(wire["content"][0]["text"]), result)
        schema = self.tools[name].output_schema
        self.assertIsNotNone(schema)
        jsonschema.validate(wire["structuredContent"], schema)

    def test_recorded_persistence_results_survive_serialization(self):
        # Recorded FL26.1.6 results, including an uncertain Save As, not new live edits.
        for case, fixture in self.recorded.items():
            with self.subTest(case=case):
                self.assert_result(fixture["tool"], fixture["result"])

    def test_incomplete_evidence_is_not_fabricated_or_promoted_to_saved(self):
        unnamed = copy.deepcopy(self.recorded["file"]["result"])
        unnamed.update(path=None, saved_file=None)
        self.assert_result("fl_get_project_file", unnamed)

        saved = self.recorded["save"]["result"]
        not_saved = {key: value for key, value in saved.items()
                     if key not in ("before_file", "after_file", "host")}
        not_saved.update(path=None, project_saved=False, status="not_saved",
                         verification="none", message="Project needs Save As")
        self.assert_result("fl_save_project", not_saved)

        lost_ack = {**not_saved, "path": saved["path"], "before_file": saved["before_file"],
                    "status": "unknown", "message": "Acknowledgement lost",
                    "next_action": "Inspect the project and file; do not resend."}
        self.assert_result("fl_save_project", lost_ack)
        mismatched = {**lost_ack, "host": {"command": "unexpected", "session_fingerprint": "other"}}
        self.assert_result("fl_save_project", mismatched)
        unchanged = {**lost_ack, "host": saved["host"], "after_file": saved["before_file"]}
        self.assert_result("fl_save_project", unchanged)

        interrupted = copy.deepcopy(self.recorded["save_as_unknown"]["result"])
        interrupted.pop("observed_identity")
        interrupted.update(submitted=False, dialog_cleanup_error="Dialog could not close")
        self.assert_result("fl_save_project_as", interrupted)

    def test_preflight_error_remains_an_mcp_error_without_persistence_evidence(self):
        wire = self.call("fl_save_project_as", error=ValueError("Destination unavailable"))
        self.assertTrue(wire["isError"])
        self.assertIsNone(wire.get("structuredContent"))
        self.assertIn("Destination unavailable", wire["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
