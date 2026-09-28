"""Host doubles cover uncertain imports; live evidence is recorded separately."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch
import soundfile
from scripts import sample_import as sample
from scripts.native_host import NativeExecutionError


class SampleImportTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.path = self.root / "Kick Æøå.wav"
        soundfile.write(self.path, [0, .1, -.1, 0], 44100)
        self.client = Mock()
        self.client.ping.return_value = {"session_fingerprint": "session"}
        self.client.call.side_effect = [{"channel_count": 1}, {"channel_count": 2, "channels": [{}, {}]}]
        stack.enter_context(patch.object(sample.creative, "_writable_preflight",
            return_value=(self.client, {}, "session")))
        self.reader = Mock(window=1, pid=12)
        self.reader.identity.return_value = {"path": "project.flp"}
        self.reader.snapshot.return_value = {"clips": []}
        self.reader.channel_objects.side_effect = [[123], [123, 456]]
        self.source = {"kind": "sampler", "file_exists": True, "resolved_path": str(self.path)}
        self.reader.source.return_value = self.source
        stack.enter_context(patch.object(sample, "SampleReader")).return_value.__enter__.return_value = self.reader
        self.dispatch = stack.enter_context(patch.object(sample, "dispatch",
            side_effect=NativeExecutionError("ack lost", {"stage": 1})))

    def test_lost_ack_resolved_from_host_path_without_reinsertion(self):
        result = sample.import_sample(str(self.path))
        self.assertEqual(result["status"], "imported")
        self.assertEqual(result["file"]["frames"], 4)
        self.assertFalse(result["playback_verified"])
        self.dispatch.assert_called_once()

    def test_different_loaded_file_is_partial_not_success(self):
        self.source["resolved_path"] = str(self.root / "Other.wav")
        result = sample.import_sample(str(self.path))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["verification"], "none")
        self.dispatch.assert_called_once()

    def test_invalid_wav_does_not_insert_channel(self):
        self.path.write_text("not audio", encoding="utf-8")
        with self.assertRaises(soundfile.LibsndfileError):
            sample.import_sample(str(self.path))
        self.dispatch.assert_not_called()
