"""Effect insertion contract: observe the target and preserve existing mixer state."""

import copy
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import effect_loading as loading
from scripts.native_host import NativeExecutionError


class EffectLoadingTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.preset = self.root / "Fruity Reeverb 2.fst"
        self.preset.write_bytes(b"FLhd" + bytes(20))
        self.client = Mock()
        self.client.ping.return_value = {"session_fingerprint": "session"}
        stack.enter_context(patch.object(loading.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "session")))
        self.old = {"slot": 8, "name": "Existing", "target_fingerprint": "old"}
        self.new = {"slot": 3, "name": "Fruity Reeverb 2", "target_fingerprint": "new"}
        self.before = {"index": 10, "name": "Bus", "volume": 0.8, "peak_l": 0.1,
                       "plugins": [self.old], "routes": [{"to": 0, "level": 0.8}]}
        self.after = copy.deepcopy(self.before)
        self.after.update(plugins=[self.new, self.old], peak_l=0.3)
        self.client.call.side_effect = [self.before, self.after]
        self.reader = Mock(window=123, pid=45)
        self.reader.identity.return_value = {"path": "fixture.flp"}
        reader = stack.enter_context(patch.object(loading, "ProjectReader"))
        reader.return_value.__enter__.return_value = self.reader
        stack.enter_context(patch.object(loading, "effect_target", return_value=b"target"))
        self.dispatch = stack.enter_context(patch.object(loading, "dispatch", return_value={"stage": 2}))

    def load(self):
        return loading.add_effect(10, 3, str(self.preset), "Fruity Reeverb 2")

    def test_lost_ack_is_resolved_by_actual_plugin_and_preservation_without_resend(self):
        self.dispatch.side_effect = NativeExecutionError("outcome unknown", {"stage": 1})
        result = self.load()
        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["effect"]["target_fingerprint"], "new")
        self.assertTrue(result["mixer_preserved"])
        self.dispatch.assert_called_once_with(123, 45, 13, path=str(self.preset),
            project="fixture.flp", payload=b"target", timeout_ms=60000)

    def test_changed_existing_effect_or_route_cannot_be_reported_as_success(self):
        self.after["routes"] = []
        result = self.load()
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["mixer_preserved"])
        self.assertNotIn("effect", result)
        self.assertFalse(result["automatic_retry"])
        self.assertFalse(loading.preserved_mixer(self.before,
            {**self.before, "plugins": [{**self.old, "target_fingerprint": "replaced"}]}, 3))

    def test_wrong_plugin_or_changed_session_is_not_verified(self):
        self.new["name"] = "Wrong effect"
        self.assertEqual(self.load()["status"], "partial")
        self.client.call.side_effect = [self.before, self.after]
        self.client.ping.return_value = {"session_fingerprint": "other session"}
        result = self.load()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["verification"], "none")

    def test_occupied_slot_is_preserved_without_native_dispatch(self):
        self.before["plugins"].append(self.new)
        with self.assertRaisesRegex(ValueError, "occupied"):
            self.load()
        self.dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
