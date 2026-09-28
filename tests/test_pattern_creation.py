"""Creation semantics at the score boundary and partial preparation reporting."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import pattern_tool
from scripts.range_runtime import create_score, replace_range
from test_range_edit import Score, note


def marker():
    return SimpleNamespace(time=0, name="", mode=0, tsnum=4, tsden=4)


class PatternCreationTest(unittest.TestCase):
    def test_native_defaults_fractional_extent_and_range_preservation(self):
        score = Score([])
        flp = SimpleNamespace(score=score, Marker=marker)
        data = {"phrase_length_qn": 13.125, "expected_ppq": 240,
                "notes": [{"pitch": 60, "start_qn": 0.0125,
                           "duration_qn": 0.025, "velocity": 0.6}]}
        result = create_score(flp, data)
        self.assertEqual(result["status"], "applied")
        self.assertEqual((score.notes[0].time, score.notes[0].length), (3, 6))
        self.assertEqual((score.notes[0].pan, score.notes[0].fcut), (0.25, 0.7))
        self.assertEqual((score.markers[0].time, score.markers[0].mode), (3150, 6))
        self.assertEqual(result["phrase_length_qn"], 13.125)
        native_marker = score.markers[0]
        cleared = replace_range(flp, {"range_start_qn": 0, "range_end_qn": 1, "notes": []})
        self.assertEqual(cleared["status"], "applied")
        self.assertTrue(cleared["markers_preserved"])
        self.assertIs(score.markers[0], native_marker)
        self.assertEqual(score.noteCount, 0)

    def test_changed_empty_target_or_ppq_prevents_writing(self):
        score = Score([note()])
        flp = SimpleNamespace(score=score, Marker=marker)
        data = {"phrase_length_qn": 4, "expected_ppq": 240, "notes": []}
        with self.assertRaisesRegex(ValueError, "no longer empty"):
            create_score(flp, data)
        score.notes.clear()
        with self.assertRaisesRegex(ValueError, "PPQ changed"):
            create_score(flp, {**data, "expected_ppq": 96})
        self.assertEqual(score.markerCount, 0)

    def test_subtick_input_prevents_allocation_and_named_failure_is_partial(self):
        client = Mock()
        client.call.side_effect = lambda op, **kw: ({"channel_count": 7} if op == "channels.list" else
                                                  {"ppq": 96, "channel_count": 2, "current_pattern": 2})
        inspector, controller = Mock(), Mock()
        inspector.find_empty_pattern.return_value.empty_pattern_number = 3
        for action in (controller.select_pattern, controller.set_pattern_identity):
            action.return_value.verified = True
            action.return_value.model_dump.return_value = {"verified": True}
        creative = pattern_tool.creative
        with patch.object(pattern_tool, "ensure_locked_score_session"), \
                patch.object(creative, "_writable_preflight", return_value=(client, {}, "one")), \
                patch.object(creative, "TrackBInspector", return_value=inspector), \
                patch.object(creative, "TrackBController", return_value=controller), \
                patch.object(pattern_tool, "dispatch_locked_score") as dispatch:
            request = pattern_tool.PatternCreation(name="Phrase", phrase_length_qn=4, notes=[
                {"pitch": 60, "start_qn": 0, "duration_qn": 0.0001, "velocity": 0.7}])
            with self.assertRaisesRegex(ValueError, "zero ticks"):
                pattern_tool.create_pattern(request, 5)
            inspector.find_empty_pattern.assert_not_called()
            dispatch.return_value = {"status": "failed", "message": "Host rejected notes"}
            result = pattern_tool.create_pattern(request.model_copy(update={"notes": []}), 5)
            self.assertEqual((result["status"], result["pattern_number"]), ("partial", 3))
            self.assertIn("pattern was named", result["message"])
            dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
