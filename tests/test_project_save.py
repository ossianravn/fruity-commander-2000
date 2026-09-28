"""Save dispatch plus actual file evidence; FL host and native path use doubles."""

import os
import struct
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import project_save as save
from host_fixture import controller_namespace, finish, install_extension


class ProjectSaveTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.path = Path(stack.enter_context(tempfile.TemporaryDirectory())) / "Test.flp"
        self.path.write_bytes(b"FLhd" + struct.pack("<IHHH", 6, 0, 1, 96)
                             + b"FLdt" + struct.pack("<I", 4) + b"data")
        self.identity = {"process_id": 12, "path": str(self.path)}
        self.reader = Mock()
        self.reader.identity.return_value = self.identity
        factory = stack.enter_context(patch.object(save, "ProjectReader"))
        factory.return_value.__enter__.return_value = self.reader
        self.host = controller_namespace()
        self.host.update(SESSION_FINGERPRINT="a" * 32,
                         _check_session_precondition=Mock(), LEAN_WRITE_COMMANDS=set(),
                         midi=SimpleNamespace(FPT_Save=92, GT_Cannot=-1), transport=Mock())
        self.host["transport"].globalTransport.side_effect = self.rewrite
        install_extension(self.host, "host_save.py")
        self.client = Mock()
        self.client.ping.return_value = {"session_fingerprint": "a" * 32}
        self.client.call.side_effect = lambda command, **args: finish(self.host["HANDLERS"][command](args))
        stack.enter_context(patch.object(save.creative, "_writable_preflight",
                                        return_value=(self.client, {}, "a" * 32)))
        stack.enter_context(patch.object(save, "TIMEOUT", 0))

    def rewrite(self, command, value):
        # Same bytes with a new modification time is a real save of a clean project.
        stat = self.path.stat()
        os.utime(self.path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        return 8

    def test_named_project_save_requires_completed_file_write_even_when_clean(self):
        result = save.save_project()
        self.assertTrue(result["project_saved"])
        self.assertEqual(result["verification"], "host_save_and_completed_file_write")
        self.assertEqual(result["before_file"]["sha256"], result["after_file"]["sha256"])
        self.assertNotEqual(result["before_file"]["modified_ns"], result["after_file"]["modified_ns"])
        self.host["transport"].globalTransport.assert_called_once_with(92, 1)
        self.assertEqual(result["host"]["dirty_after"], 0)

    def test_clean_ack_without_write_and_lost_ack_cannot_claim_saved_or_retry(self):
        for mode in ("no_write", "lost_ack"):
            with self.subTest(mode=mode):
                self.client.call.reset_mock()
                if mode == "no_write":
                    self.host["transport"].globalTransport.side_effect = lambda *args: 8
                else:
                    def lost(command, **args):
                        self.rewrite(92, 1)
                        raise RuntimeError("Acknowledgement lost")
                    self.client.call.side_effect = lost
                result = save.save_project()
                self.assertFalse(result["project_saved"])
                self.assertEqual(result["status"], "unknown")
                self.client.call.assert_called_once()

    def test_project_switch_invalidates_write_and_incomplete_flp_prevents_dispatch(self):
        self.reader.identity.side_effect = [self.identity, self.identity,
                                           {**self.identity, "path": "Other.flp"}]
        self.assertEqual(save.save_project()["status"], "unknown")
        self.reader.identity.side_effect = None
        self.client.call.reset_mock()
        self.path.write_bytes(b"FLhd\0")
        with self.assertRaisesRegex(ValueError, "complete FLP"):
            save.save_project()
        self.client.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
