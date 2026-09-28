"""Wrapper acceptance does not establish musical setup or justify a retry."""

import tempfile
import struct
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import plugin_state as state
from scripts.native_host import NativeExecutionError
from tests.test_generator_presets import image
from scripts.vst_state import vst2_bank


def configured_preset():
    chunk = b"opaque-bank\0external-project.xpj"
    state = struct.pack("<iBiqi", -9, 8, -2, len(chunk), 0) + chunk
    fields = [(51, b"Test"), (53, state)]
    wrapper = struct.pack("<I", 12) + b"".join(
        struct.pack("<IQ", tag, len(data)) + data for tag, data in fields)
    return image([(201, "Fruity Wrapper\0".encode("utf-16-le")), (213, wrapper)]), chunk


class PluginStateTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.path = root / "Configured.fst"
        self.path.write_bytes(configured_preset()[0])
        self.client = Mock()
        self.channel = {"index": 0, "target_fingerprint": "target", "mixer_track": 6}
        self.client.call.return_value = {"channels": [self.channel]}
        self.client.ping.return_value = {"session_fingerprint": "session"}
        stack.enter_context(patch.object(state.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "session")))
        self.reader = Mock(window=123, pid=45)
        self.reader.identity.return_value = {"path": "fixture.flp"}
        self.reader.channel_objects.return_value = [1000]
        self.reader.value.side_effect = lambda address: {1056: 2000, 2044: 3000}[address]
        reader = stack.enter_context(patch.object(state, "ArrangementReader"))
        reader.return_value.__enter__.return_value = self.reader
        self.dispatch = stack.enter_context(patch.object(state, "dispatch",
            return_value={"native_callback_completed": True, "stage": 2}))

    def load(self):
        return state.load_state(0, "target", str(self.path))

    def test_acceptance_retains_instance_without_claiming_sound_or_save(self):
        result = self.load()
        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["verification"], "wrapper_accepted_file_and_instance_retained")
        self.assertFalse(result["musical_setup_verified"])
        self.assertFalse(result["project_saved"])
        self.assertEqual(result["channel"]["mixer_track"], 6)
        self.dispatch.assert_called_once()

    def test_lost_ack_stays_unknown_even_when_channel_identity_is_unchanged(self):
        self.dispatch.side_effect = NativeExecutionError("timed out", {"stage": 1})
        result = self.load()
        self.assertEqual(result["status"], "unknown")
        self.assertFalse(result["automatic_retry"])
        staged = Path(result["staged_state_path"])
        self.addCleanup(staged.unlink)
        self.assertTrue(staged.exists())
        self.dispatch.assert_called_once()

    def test_bank_translation_preserves_plugin_bytes_and_rejects_bad_lengths(self):
        preset, chunk = configured_preset()
        bank = vst2_bank(preset)
        self.assertEqual(bank[:4], b"CcnK")
        self.assertEqual(bank[8:12], b"FBCh")
        self.assertEqual(struct.unpack_from(">I", bank, 156)[0], len(chunk))
        self.assertEqual(bank[160:], chunk)
        with self.assertRaisesRegex(ValueError, "truncated"):
            vst2_bank(preset.replace(struct.pack("<Q", 21 + len(chunk)), struct.pack("<Q", 999)))


if __name__ == "__main__":
    unittest.main()
