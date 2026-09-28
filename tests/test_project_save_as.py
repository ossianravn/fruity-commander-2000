"""Save As needs native path adoption and completed-file evidence, not a dialog."""

import struct
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch
from scripts import project_save_as as save
from scripts.native_host import NativeExecutionError


class SaveAsTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.directory = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        self.destination = self.directory / "New Æøå.flp"
        self.identity = {"path": str(self.directory / "untitled.flp"), "process_id": 12}
        self.reader = Mock(window=1, pid=12)
        self.reader.identity.side_effect = lambda: dict(self.identity)
        stack.enter_context(patch.object(save, "ProjectReader")).return_value.__enter__.return_value = self.reader
        self.client = Mock()
        self.client.ping.return_value = {"session_fingerprint": "a" * 32}
        stack.enter_context(patch.object(save.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "a" * 32)))
        self.dispatch = stack.enter_context(patch.object(save, "dispatch", side_effect=self.write))
        stack.enter_context(patch.object(save, "TIMEOUT", 0))

    def write(self, *args, **kwargs):
        self.identity["path"] = str(self.destination)
        self.destination.write_bytes(b"FLhd" + struct.pack("<IHHH", 6, 0, 1, 96)
                                     + b"FLdt" + struct.pack("<I", 4) + b"data")
        return {"stage": 3}

    def test_untitled_unicode_save_verified_despite_lost_acknowledgement(self):
        def lost(*args, **kwargs):
            self.write()
            raise NativeExecutionError("ack lost", {"stage": 2})
        self.dispatch.side_effect = lost
        result = save.save_project_as(str(self.destination))
        self.assertTrue(result["project_saved"])
        self.assertEqual(result["observed_identity"]["path"], str(self.destination))
        self.assertEqual(result["after_file"]["size_bytes"], 26)
        self.assertIsNone(result["before_file"])
        self.dispatch.assert_called_once_with(1, 12, 10, path=str(self.destination),
            project=str(self.directory / "untitled.flp"), timeout_ms=60000)

    def test_unadopted_path_incomplete_file_or_changed_session_remains_unknown(self):
        original = dict(self.identity)
        for mode in ("unadopted", "incomplete", "changed_session"):
            with self.subTest(mode=mode):
                self.identity.update(original)
                self.destination.unlink(missing_ok=True)
                self.dispatch.reset_mock()
                def write(*args, **kwargs):
                    self.write()
                    if mode == "unadopted":
                        self.identity.update(original)
                    elif mode == "incomplete":
                        self.destination.write_bytes(b"FLhd")
                    else:
                        self.client.ping.return_value = {"session_fingerprint": "b" * 32}
                    return {"stage": 2}
                self.dispatch.side_effect = write
                result = save.save_project_as(str(self.destination))
                self.assertEqual(result["status"], "unknown")
                self.assertFalse(result["project_saved"])
                self.dispatch.assert_called_once()

    def test_invalid_destination_rejected_before_dispatch(self):
        with self.assertRaisesRegex(ValueError, "absolute .flp"):
            save.save_project_as("relative.flp")
        self.dispatch.assert_not_called()
