"""One-time MPC setup preserves unrelated settings and respects the live-state owner."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.mpc_setup import enable_mapping, enabled_settings


class MpcSetupTest(unittest.TestCase):
    def test_enable_preserves_every_other_byte_and_is_idempotent(self):
        before = (b'<?xml version="1.0" encoding="UTF-8"?>\r\n<PROPERTIES>\r\n'
                  b'  <!-- keep this -->\r\n  <VALUE name="Other" val="0"/>\r\n'
                  b'  <VALUE name="MidiLearnEnabled" val="0"/>\r\n</PROPERTIES>\r\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MPC Beats.settings"
            path.write_bytes(before)
            with patch("scripts.mpc_setup.running_applications", return_value=[]), \
                    patch("scripts.mpc_setup.sys.platform", "win32"):
                self.assertTrue(enable_mapping(path)["changed"])
                self.assertFalse(enable_mapping(path)["changed"])
            self.assertEqual(path.read_bytes(), before.replace(b'MidiLearnEnabled" val="0', b'MidiLearnEnabled" val="1'))

    def test_running_host_leaves_file_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MPC Beats.settings"
            path.write_bytes(b"unchanged")
            with patch("scripts.mpc_setup.running_applications", return_value=["FL64.exe"]), \
                    patch("scripts.mpc_setup.sys.platform", "win32"):
                with self.assertRaisesRegex(RuntimeError, "in-memory preferences"):
                    enable_mapping(path)
            self.assertEqual(path.read_bytes(), b"unchanged")

    def test_unrecognized_or_ambiguous_settings_are_not_replaced(self):
        for content in (b"<PROPERTIES/>", b'<PROPERTIES><VALUE name="MidiLearnEnabled" val="2"/></PROPERTIES>',
                        b'<PROPERTIES><VALUE name="MidiLearnEnabled" val="0"/>'
                        b'<VALUE name="MidiLearnEnabled" val="1"/></PROPERTIES>'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                enabled_settings(content)


if __name__ == "__main__":
    unittest.main()
