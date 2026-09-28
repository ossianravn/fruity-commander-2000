"""Playlist operation contracts with a doubled host; real placement is separately qualified."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from scripts import playlist_tool as tool
from scripts.native_host import NativeExecutionError


class PlaylistTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.request = tool.PatternPlacement(pattern_number=7, expected_name="Sparse", track=2,
                                              start_qn=13.125, length_qn=4)
        self.client = Mock()
        self.pattern = {"pattern": 7, "name": "Sparse"}
        self.client.call.side_effect = lambda op, **kw: ({"patterns": [self.pattern]} if op == "patterns.list"
                                                        else {"ppq": 96})
        self.client.ping.return_value = {"session_fingerprint": "session"}
        stack.enter_context(patch.object(tool.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "session")))
        self.reader = Mock(base=0x1000, window=123, pid=45)
        self.reader.value.return_value = 0x2000
        self.before = {"project": {"path": "fixture.flp"}, "arrangement_index": 0,
                       "clips": [], "automation": [], "links": []}
        self.clip = {"index": 0, "start_tick": 1260, "length_tick": 384,
                     "track": 2, "source_id": 0x50075000, "muted": False}
        self.after = {**self.before, "clips": [self.clip]}
        self.reader.snapshot.side_effect = [self.before, self.after]
        reader = stack.enter_context(patch.object(tool, "ArrangementReader"))
        reader.return_value.__enter__.return_value = self.reader
        self.dispatch = stack.enter_context(patch.object(tool, "dispatch"))
        self.dispatch.side_effect = NativeExecutionError("Lost acknowledgement", {"stage": 3})

    def test_sparse_pattern_fractional_placement_resolves_lost_ack_once(self):
        result = tool.place_pattern(self.request)
        self.assertEqual(result["status"], "placed")
        self.assertEqual(result["clip"]["start_tick"], 1260)
        self.assertEqual(len(self.dispatch.call_args.kwargs["payload"]), 32)
        self.dispatch.assert_called_once()

    def test_wrong_source_is_partial_and_stale_pattern_prevents_dispatch(self):
        self.clip["source_id"] += 0x10000
        self.assertEqual(tool.place_pattern(self.request)["status"], "partial")
        self.dispatch.reset_mock()
        self.pattern["name"] = "Different"
        with self.assertRaisesRegex(ValueError, "identity changed"):
            tool.place_pattern(self.request)
        self.dispatch.assert_not_called()
