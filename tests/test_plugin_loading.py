"""Loading contracts use host doubles; native lifecycle has its own process test."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import plugin_loading as loading
from scripts.plugin_catalog import generator_entries
from scripts.native_host import NativeExecutionError


class PluginLoadingTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.preset = self.root / "MPC Beats.fst"
        self.preset.write_bytes(b"FLhd" + bytes(20))
        self.client = Mock()
        stack.enter_context(patch.object(loading.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "session")))
        self.client.ping.return_value = {"session_fingerprint": "session"}
        self.old = {"index": 0, "plugin": "Existing", "channel_fingerprint": "old"}
        self.new = {"index": 1, "plugin": "MPC Beats", "channel_fingerprint": "new"}
        self.client.call.side_effect = [
            {"channel_count": 1, "channels": [self.old]},
            {"channel_count": 2, "channels": [self.old, self.new]},
        ]
        self.reader = Mock(window=123, pid=45)
        self.reader.identity.return_value = {"path": "fixture.flp"}
        reader = stack.enter_context(patch.object(loading, "ProjectReader"))
        reader.return_value.__enter__.return_value = self.reader
        self.dispatch = stack.enter_context(patch.object(loading, "dispatch",
                                              return_value={"stage": 2, "created_channel": 1}))

    def load(self):
        return loading.add_generator(str(self.preset), "MPC Beats")

    def test_lost_native_ack_can_be_resolved_by_actual_plugin_without_resend(self):
        self.dispatch.side_effect = NativeExecutionError("outcome unknown", {"stage": 1})
        result = self.load()
        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["channel_index"], 1)
        self.assertEqual(result["verification"], "host_plugin_identity_readback")
        self.dispatch.assert_called_once()

    def test_wrong_plugin_is_partial_and_changed_project_is_unknown(self):
        self.new["plugin"] = "Sampler"
        result = self.load()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["new_channels"][0]["plugin"], "Sampler")
        self.dispatch.assert_called_once()
        self.client.call.side_effect = [
            {"channel_count": 1, "channels": [self.old]},
            {"channel_count": 2, "channels": [self.old, self.new]},
        ]
        self.client.ping.return_value = {"session_fingerprint": "different"}
        self.assertEqual(self.load()["status"], "unknown")

    def test_catalog_preserves_duplicate_names_and_fails_invalid_preset_before_dispatch(self):
        other = self.root / "Other"
        other.mkdir()
        (other / self.preset.name).write_bytes(self.preset.read_bytes())
        self.preset.with_suffix(".nfo").write_text("ps_name=MPC Beats\nps_file_vendorname_0=Akai", encoding="utf-8")
        entries = generator_entries([self.root], "mpc")
        self.assertEqual(len(entries), 2)
        self.assertNotEqual(entries[0]["preset_path"], entries[1]["preset_path"])
        self.preset.write_bytes(b"not a preset")
        with self.assertRaisesRegex(ValueError, "not an FL preset"):
            self.load()
        self.dispatch.assert_not_called()
