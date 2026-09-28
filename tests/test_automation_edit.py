"""Revision contracts with native doubles; live undo/persistence tested separately."""

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from scripts import automation_edit as tool
from scripts.automation_contract import encode_points
from scripts.native_host import NativeExecutionError


class AutomationRevisionTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        old = [{"time_qn": 0., "value": .25, "tension": 0., "curve": 0},
               {"time_qn": 4., "value": .5, "tension": 0., "curve": 0}]
        self.request = tool.AutomationRevision(source_event=65536, expected_points=old,
            points=[{"time_qn": 0, "value": .4}, {"time_qn": 2, "value": .7}, {"time_qn": 4, "value": .1}])
        self.before = {"project": {"path": "fixture.flp"}, "arrangement_index": 0,
                       "automation": [{"channel_index": 1, "source_event": 65536, "points": old}],
                       "clips": [{"source_id": 0x15000, "track": 3}],
                       "links": [{"source_event": 65536, "target_event": 0x8002}], "time_selection": {}}
        self.after = copy.deepcopy(self.before)
        self.after["automation"][0]["points"] = encode_points(self.request.points)[1]
        self.client = Mock()
        self.client.ping.return_value = {"session_fingerprint": "session"}
        stack.enter_context(patch.object(tool.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "session")))
        self.reader = Mock(window=123, pid=45)
        self.reader.channel_objects.return_value = [456, 789]
        self.reader.value.return_value = 1000
        self.reader.read.return_value = bytes(64)
        self.reader.curve.return_value = self.before["automation"][0]
        self.reader.snapshot.side_effect = [self.before, self.after]
        reader = stack.enter_context(patch.object(tool, "ArrangementReader"))
        reader.return_value.__enter__.return_value = self.reader
        self.dispatch = stack.enter_context(patch.object(tool, "dispatch"))
        self.dispatch.side_effect = NativeExecutionError("Lost acknowledgement", {"stage": 2})

    def test_lost_ack_resolved_by_points_and_preserved_associations(self):
        result = tool.replace_points(self.request)
        self.assertEqual(result["status"], "revised")
        self.assertEqual(result["automation"]["points"], self.after["automation"][0]["points"])
        self.dispatch.assert_called_once()
        self.assertEqual(len(self.dispatch.call_args.kwargs["payload"]), 32 + 64 + 24)
        self.after["links"][0]["target_event"] += 1
        self.reader.snapshot.side_effect = [self.before, self.after]
        self.assertEqual(tool.replace_points(self.request)["status"], "partial")

    def test_stale_curve_prevents_dispatch(self):
        self.before["automation"][0]["points"][0]["value"] = .75
        with self.assertRaisesRegex(ValueError, "points changed"):
            tool.replace_points(self.request)
        self.dispatch.assert_not_called()

    def test_extent_and_float_delta_rounding_are_not_silently_changed(self):
        data = self.request.model_dump()
        data["points"][-1]["time_qn"] = 5
        with self.assertRaisesRegex(ValueError, "extent"):
            tool.AutomationRevision(**data)
        data = self.request.model_dump()
        data["points"][1]["time_qn"] = .1
        with self.assertRaisesRegex(ValueError, "float deltas"):
            tool.replace_points(tool.AutomationRevision(**data))
        self.dispatch.assert_not_called()
