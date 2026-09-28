"""Native automation operation contracts with FL/native doubles; not live evidence."""

import copy
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from scripts import automation_tool as tool
from scripts.automation_contract import AutomationCreation
from scripts.native_host import NativeExecutionError


class AutomationTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.request = AutomationCreation(channel_index=0, parameter_index=2, target_fingerprint="target",
            track=3, start_qn=1, length_qn=4,
            points=[{"time_qn": 0, "value": .2}, {"time_qn": 4, "value": .8}])
        self.target = {"index": 0, "plugin": "Synth", "target_fingerprint": "target",
                       "reported_parameter_count": 3}
        self.client = Mock()
        self.client.call.side_effect = lambda op, **kw: ({"ppq": 96} if op == "project.info" else
                                                        {"channel_count": 1, "channels": [self.target]})
        self.client.ping.return_value = {"session_fingerprint": "session"}
        stack.enter_context(patch.object(tool.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "session")))
        self.before = {"project": {"path": "fixture.flp"}, "arrangement_index": 0,
                       "automation": [], "clips": [], "links": []}
        self.after = {**self.before, "automation": [{"channel_index": 1, "source_event": 0x10000,
                     "points": self.request.encoded(96)[3]}],
                     "links": [{"source_event": 0x10000, "target_event": 0x8002}],
                     "clips": [{"index": 0, "source_id": 0x15000, "track": 3,
                                "start_tick": 96, "length_tick": 384, "muted": False}]}
        self.reader = Mock(window=123, pid=45)
        self.reader.channel_objects.return_value = [456]
        self.reader.value.return_value = 0
        self.reader.snapshot.side_effect = [self.before, self.after]
        reader = stack.enter_context(patch.object(tool, "ArrangementReader"))
        reader.return_value.__enter__.return_value = self.reader
        self.dispatch = stack.enter_context(patch.object(tool, "dispatch"))
        self.dispatch.side_effect = NativeExecutionError("Lost acknowledgement", {"stage": 2})

    def test_lost_ack_resolves_only_from_link_points_and_placement(self):
        result = tool.create_automation(self.request)
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["automation"]["points"][0]["value"], 0.20000000298023224)
        self.dispatch.assert_called_once()
        self.assertEqual(len(self.dispatch.call_args.kwargs["payload"]), 56)
        altered = copy.deepcopy(self.after)
        altered["links"][0]["target_event"] += 1
        self.reader.snapshot.side_effect = [self.before, altered]
        self.assertEqual(tool.create_automation(self.request)["status"], "partial")

    def test_unrelated_clip_change_prevents_success_and_stale_target_prevents_mutation(self):
        self.before["clips"] = [{"index": 0, "source_id": 0x50015000, "track": 1,
                                 "start_tick": 0, "length_tick": 96, "muted": False}]
        result = tool.create_automation(self.request)
        self.assertEqual(result["status"], "partial")
        self.dispatch.reset_mock()
        self.target["target_fingerprint"] = "changed"
        with self.assertRaisesRegex(ValueError, "identity changed"):
            tool.create_automation(self.request)
        self.dispatch.assert_not_called()

    def test_invalid_curve_and_tick_representation(self):
        data = self.request.model_dump()
        data["points"][1]["time_qn"] = 3
        with self.assertRaises(ValueError):
            AutomationCreation(**data)
        data = self.request.model_dump()
        data.update(start_qn=0x7fffffff, length_qn=4)
        with self.assertRaisesRegex(ValueError, "tick range"):
            AutomationCreation(**data).encoded(96)
