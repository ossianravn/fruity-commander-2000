"""MCP note contracts: serialized results and truthful operation metadata."""

import asyncio
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import jsonschema

from scripts.postfader_server import prepare_server


class NoteSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = prepare_server()
        cls.tools = {tool.name: tool for tool in asyncio.run(cls.server.mcp.list_tools())}
        cls.recorded = json.loads(Path(__file__).with_name("fixtures").joinpath(
            "note_results.json").read_text(encoding="utf-8"))

    def test_catalog_accepts_serialized_note_and_rejects_unknown_fields(self):
        from fl_studio_mcp.piano_roll import PianoRollObservedNote

        schema = self.tools["piano_roll_read_notes"].output_schema
        note_schema = {
            "$ref": "#/$defs/PianoRollObservedNote", "$defs": schema["$defs"]
        }
        note = PianoRollObservedNote(
            note_index=0, pitch=60, start_ticks=480, length_ticks=120, ppq=240,
            velocity=0.75, pan=0.5, release=0.5, color=0,
            pitch_offset_tenths=0, slide=False, portamento=False,
            muted=False, selected=False,
        ).model_dump(mode="json")
        jsonschema.validate(note, note_schema)
        self.assertEqual((note["start_beats"], note["duration_beats"]), (2, 0.5))
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**note, "unrecognized": True}, note_schema)

    def test_note_annotations_distinguish_editor_effects_from_note_writes(self):
        for name, destructive in (("piano_roll_inspect_score", False),
                                  ("piano_roll_create_pattern", True),
                                  ("piano_roll_replace_range", True)):
            with self.subTest(tool=name):
                annotation = self.tools[name].annotations
                self.assertIsNotNone(annotation)
                hints = annotation.model_dump(by_alias=True)
                # Even inspection prepares the editor and can add undo/dirty state.
                self.assertFalse(hints["readOnlyHint"])
                self.assertEqual(hints["destructiveHint"], destructive)
                self.assertFalse(hints["idempotentHint"])
                self.assertTrue(hints["openWorldHint"])

    def assert_note_result(self, name, result):
        bindings = {
            "piano_roll_inspect_score": ("scripts.range_tool.dispatch_score",
                {"channel_index": 1, "pattern_number": 2}),
            "piano_roll_replace_range": ("scripts.range_tool.replace_range",
                {"channel_index": 1, "pattern_number": 2, "request": {
                    "range_start_qn": 4, "range_end_qn": 8, "notes": []}}),
            "piano_roll_create_pattern": ("scripts.pattern_tool.create_pattern",
                {"channel_index": 1, "request": {
                    "name": "Contract fixture", "phrase_length_qn": 8, "notes": []}}),
        }
        target, arguments = bindings[name]
        with patch(target, return_value=result):
            response = asyncio.run(self.server.mcp.call_tool(name, arguments))
        wire = response.model_dump(mode="json", by_alias=True)
        self.assertFalse(wire.get("isError", False))
        self.assertEqual(wire["structuredContent"], result)
        self.assertEqual(json.loads(wire["content"][0]["text"]), result)
        schema = self.tools[name].output_schema
        self.assertIsNotNone(schema)
        jsonschema.validate(wire["structuredContent"], schema)

    def test_recorded_note_readbacks_survive_mcp_serialization(self):
        # Retained FL26.1.6 evidence, replayed through real MCP serialization.
        for name, result in self.recorded.items():
            with self.subTest(tool=name):
                self.assert_note_result(name, result)

    def test_incomplete_results_preserve_available_evidence_without_fabrication(self):
        created = copy.deepcopy(self.recorded["piano_roll_create_pattern"])
        created.pop("request_id")
        created.pop("observed")
        created.update(status="partial", verification="none", message="Named; dispatch unavailable",
                       next_action="Inspect the prepared pattern before another creation.")
        self.assert_note_result("piano_roll_create_pattern", created)

        revised = copy.deepcopy(self.recorded["piano_roll_replace_range"])
        revised.update(status="unknown", verification="none", message="Target changed",
                       next_action="Inspect target and score; do not resend.")
        self.assert_note_result("piano_roll_replace_range", revised)
        revised.update(status="partial", verification="host_receipt", message="Edit interrupted")
        revised["observed"] = {"request_id": revised["request_id"], "status": "partial",
                               "message": "Edit interrupted", "removed_count": 1, "added_count": 0,
                               "next_action": "Read the score before correcting it."}
        self.assert_note_result("piano_roll_replace_range", revised)

        # An inspection may lack an acknowledgement and therefore any observed score.
        inspected = {key: value for key, value in revised.items() if key != "observed"}
        inspected.update(status="unknown", verification="none", message="No receipt")
        self.assert_note_result("piano_roll_inspect_score", inspected)


if __name__ == "__main__":
    unittest.main()
