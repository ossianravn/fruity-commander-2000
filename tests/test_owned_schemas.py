"""Real registry serialization of retained host evidence and incomplete outcomes."""

import asyncio
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema

from scripts.postfader_server import prepare_server


class OwnedSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = prepare_server()
        cls.tools = {t.name: t for t in asyncio.run(cls.server.mcp.list_tools())}
        cls.recorded = json.loads(Path(__file__).with_name("fixtures").joinpath(
            "owned_results.json").read_text(encoding="utf-8"))
        curve = cls.recorded["fl_replace_automation_points"]["result"]["automation"]
        cls.bindings = {
            "fl_list_installed_generators": ("scripts.plugin_loading.list_generators", {}),
            "fl_add_generator": ("scripts.plugin_loading.add_generator",
                {"preset_path": "fixture.fst", "expected_plugin_name": "MPC Beats"}),
            "fl_load_generator_state": ("scripts.plugin_state.load_state",
                {"channel_index": 1, "target_fingerprint": "fixture", "preset_path": "fixture.fst"}),
            "fl_extract_generator_preset": ("scripts.generator_presets.extract_preset",
                {"project_path": "fixture.flp", "channel_index": 1,
                 "template_path": "template.fst", "destination_path": "fixture.fst"}),
            "fl_create_automation_clip": ("scripts.automation_tool.create_automation", {"request": {
                "channel_index": 1, "parameter_index": 0, "target_fingerprint": "fixture",
                "track": 1, "start_qn": 0, "length_qn": 4,
                "points": [{"time_qn": 0, "value": 0}, {"time_qn": 4, "value": 1}]}}),
            "fl_replace_automation_points": ("scripts.automation_edit.replace_points", {"request": {
                "source_event": curve["source_event"], "expected_points": curve["points"],
                "points": [{"time_qn": 0, "value": 0},
                           {"time_qn": curve["points"][-1]["time_qn"], "value": 1}]}}),
            "fl_place_pattern_clip": ("scripts.playlist_tool.place_pattern", {"request": {
                "pattern_number": 1, "expected_name": "Fixture", "track": 1,
                "start_qn": 0, "length_qn": 4}}),
            "fl_set_playlist_time_selection": ("scripts.playlist_selection.select_time", {}),
            "piano_roll_start_session": ("scripts.score_startup.ensure_score_session",
                {"channel_index": 1, "pattern_number": 1}),
        }

    def assert_result(self, name, result):
        target, arguments = self.bindings[name]
        with patch(target, return_value=result):
            response = asyncio.run(self.server.mcp.call_tool(name, arguments))
        self.assertFalse(response.is_error)
        self.assertEqual(response.structured_content, result)
        self.assertEqual(json.loads(response.content[0].text), result)
        schema = self.tools[name].output_schema
        self.assertIsNotNone(schema)
        jsonschema.validate(result, schema)

    def test_recorded_results_retain_targets_units_and_native_evidence(self):
        # Recorded host outcomes replayed at the operation boundary, not new live writes.
        for name, fixture in self.recorded.items():
            with self.subTest(tool=name, source=fixture["source"]):
                self.assert_result(name, fixture["result"])

    def test_uncertain_mutations_preserve_evidence_without_asserting_success(self):
        result_keys = {
            "fl_create_automation_clip": ("automation", "clip"),
            "fl_replace_automation_points": ("automation",),
            "fl_place_pattern_clip": ("clip",),
            "fl_add_generator": ("channel", "channel_index"),
        }
        for name, keys in result_keys.items():
            with self.subTest(tool=name):
                result = copy.deepcopy(self.recorded[name]["result"])
                for key in keys:
                    result.pop(key)
                result.update(status="unknown", verification="none", message="Target changed",
                              next_action="Inspect the returned observations before another edit.")
                self.assert_result(name, result)
                result.update(status="partial", message="Native operation incomplete")
                result["native"]["native_callback_completed"] = False
                self.assert_result(name, result)
                for key in ("native", "observed", "new_channels", "observed_channel_count"):
                    result.pop(key, None)
                result.update(status="unknown", message="Dispatch and readback unavailable")
                self.assert_result(name, result)

    def test_state_selection_and_startup_do_not_fabricate_optional_verification(self):
        state = copy.deepcopy(self.recorded["fl_load_generator_state"]["result"])
        state.pop("verification")
        state.pop("native")
        state.update(status="unknown", channel=None, staged_state_path="retained.fxb",
                     message="Native completion unknown")
        self.assert_result("fl_load_generator_state", state)
        state["staging_cleanup_error"] = "Staging cleanup unavailable"
        self.assert_result("fl_load_generator_state", state)

        selection = copy.deepcopy(self.recorded["fl_set_playlist_time_selection"]["result"])
        for key in ("verification", "after", "native"):
            selection.pop(key)
        selection.update(status="unknown", message="Selection readback unavailable")
        self.assert_result("fl_set_playlist_time_selection", selection)
        self.assert_result("piano_roll_start_session", {
            "ready": True, "verification": "earlier_signed_receipt_this_process"})


if __name__ == "__main__":
    unittest.main()
