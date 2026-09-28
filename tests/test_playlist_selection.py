"""Playlist time ownership, tick conversion, and lost-acknowledgement resolution."""

import struct
import unittest
from unittest.mock import Mock, patch

from scripts import playlist_selection as tool
from scripts.native_host import NativeExecutionError


class SelectionTest(unittest.TestCase):
    def test_select_and_clear_from_actual_playlist_readback(self):
        client = Mock()
        client.call.return_value = {"ppq": 96}
        client.ping.return_value = {"session_fingerprint": "session"}
        reader = Mock(window=123, pid=45)
        reader.identity.return_value = {"path": "project.flp"}
        current = {"owner": 100, "start_tick": 0, "end_tick": 6144, "active": True}
        reader.time_selection.side_effect = lambda: dict(current)

        def apply(*args, payload, **kwargs):
            owner, start, end = struct.unpack("<Qii", payload)
            current.update(owner=owner, start_tick=start, end_tick=end, active=end > start >= 0)
            raise NativeExecutionError("Acknowledgement lost", {"stage": 2})

        with patch.object(tool.creative, "_writable_preflight", return_value=(client, {}, "session")), \
                patch.object(tool, "ArrangementReader") as factory, \
                patch.object(tool, "dispatch", side_effect=apply) as dispatch:
            factory.return_value.__enter__.return_value = reader
            result = tool.select_time(13.125, 16)
            self.assertEqual(result["status"], "selected")
            self.assertEqual(result["after"]["start_tick"], 1260)
            self.assertEqual(tool.select_time()["status"], "cleared")
            self.assertEqual(dispatch.call_count, 2)
            with self.assertRaises(ValueError):
                tool.select_time(4, 2)
            self.assertEqual(dispatch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
