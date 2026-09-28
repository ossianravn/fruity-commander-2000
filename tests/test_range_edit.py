"""Exercise host-object preservation and pre-mutation timing validation."""

import copy
import unittest
from types import SimpleNamespace

from scripts.range_runtime import NOTE_FIELDS, replace_range, ticks
from scripts.range_tool import RangeReplacement


def note(time=0, length=240):
    values = dict.fromkeys(NOTE_FIELDS, 0)
    values.update(number=48, time=time, length=length, velocity=0.75,
                  pan=0.25, fcut=0.7, fres=0.3, repeats=4, group=2,
                  host_only_data=object())
    return SimpleNamespace(**values)


class Score:
    PPQ = 240

    def __init__(self, notes):
        self.notes = notes
        self.markers = []

    @property
    def markerCount(self):
        return len(self.markers)

    def getMarker(self, index):
        return self.markers[index]

    def addMarker(self, marker):
        self.markers.append(copy.copy(marker))

    @property
    def noteCount(self):
        return len(self.notes)

    def getNote(self, index):
        return self.notes[index]

    def deleteNote(self, index):
        del self.notes[index]

    def addNote(self, value):
        self.notes.append(copy.copy(value))

    def getDefaultNoteProperties(self):
        return note()


class RangeEditTest(unittest.TestCase):
    def test_onset_scope_preserves_overlap_end_boundary_and_host_objects(self):
        preceding, first, last, endpoint = note(720, 480), note(960), note(1919), note(1920)
        score = Score([preceding, first, last, endpoint])
        result = replace_range(SimpleNamespace(score=score), {
            "range_start_qn": 4, "range_end_qn": 8,
            "notes": [{"pitch": 60, "start_qn": 4, "duration_qn": 0.5, "velocity": 0.6}],
        })
        self.assertEqual(result["status"], "applied")
        self.assertEqual((result["removed_count"], result["added_count"]), (2, 1))
        self.assertIs(score.notes[0], preceding)
        self.assertIs(score.notes[1], endpoint)
        self.assertEqual((preceding.length, preceding.repeats, preceding.fcut), (480, 4, 0.7))

    def test_invalid_or_subtick_notes_fail_before_existing_notes_are_removed(self):
        score = Score([note(960)])
        source = {"pitch": 60, "start_qn": 4, "duration_qn": 0.0001, "velocity": 0.6}
        request = {"range_start_qn": 4, "range_end_qn": 8, "notes": [source]}
        with self.assertRaisesRegex(ValueError, "zero ticks"):
            replace_range(SimpleNamespace(score=score), request)
        self.assertEqual(score.noteCount, 1)
        self.assertEqual(ticks(0.0125, 120), 2)
        with self.assertRaises(ValueError):
            RangeReplacement.model_validate({**request, "notes": [{**source, "start_qn": 8}]})
        with self.assertRaises(ValueError):
            RangeReplacement.model_validate({**request, "notes": [{**source, "velocity": float("nan")}]})

    def test_host_failure_after_deletion_reports_partial_without_retry_or_rollback(self):
        score = Score([note(960), note(1920)])
        def fail_add(value):
            raise RuntimeError("Host rejected insertion")
        score.addNote = fail_add
        result = replace_range(SimpleNamespace(score=score), {
            "range_start_qn": 4, "range_end_qn": 8,
            "notes": [{"pitch": 60, "start_qn": 4, "duration_qn": 1, "velocity": 0.6}],
        })
        self.assertEqual(result["status"], "partial")
        self.assertEqual((result["removed_count"], result["added_count"]), (1, 0))
        self.assertEqual([n.time for n in score.notes], [1920])


if __name__ == "__main__":
    unittest.main()
