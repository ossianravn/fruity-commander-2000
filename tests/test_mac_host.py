"""osascript targeting: data through argv, verified focus, explicit permission errors."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import mac_host, mac_probe


def completed(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


class OsascriptTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"FL_BRIDGE_SANDBOXED": "0"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_arguments_travel_through_argv_never_source(self):
        with mock.patch.object(subprocess, "run", return_value=completed('{"ok": true}')) as run:
            self.assertEqual(mac_host.osascript("function run(argv) {}", 12, "press"), {"ok": True})
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["osascript", "-l", "JavaScript", "-e", "function run(argv) {}"])
        self.assertEqual(command[5:], ["12", "press"])

    def test_permission_failures_explain_the_required_grant(self):
        denied = completed(returncode=1, stderr="osascript is not allowed to send keystrokes. (1002)")
        with mock.patch.object(subprocess, "run", return_value=denied):
            with self.assertRaisesRegex(RuntimeError, "Privacy & Security.*Accessibility"):
                mac_host.osascript("source")

    def test_offline_environment_never_runs_osascript(self):
        with mock.patch.dict(os.environ, {"FL_BRIDGE_SANDBOXED": "1"}), \
                mock.patch.object(subprocess, "run", side_effect=AssertionError("ran")):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                mac_host.osascript("source")

    def test_process_identity_requires_exactly_one_fl(self):
        rows = [{"pid": 7, "launched": 1.5, "architecture": 0x0100000C}]
        with mock.patch.object(mac_host, "osascript", return_value=rows) as script:
            self.assertEqual(mac_host.running_fl()["architecture"], "arm64")
        self.assertEqual(script.call_args.args[1], mac_host.FL_BUNDLE_ID)
        with mock.patch.object(mac_host, "osascript", return_value=rows * 2):
            with self.assertRaisesRegex(RuntimeError, "found 2"):
                mac_host.running_fl()

    def test_shortcut_is_pressed_only_through_the_verified_front_script(self):
        with mock.patch.object(mac_host, "osascript", return_value={}) as script:
            dispatch = mac_host.trigger_run_last_script({"pid": 9})
        self.assertTrue(dispatch.hotkey_dispatched)
        self.assertEqual(dispatch.shortcut, "Cmd+Opt+Y")
        self.assertEqual(script.call_args.args[1:], (9, "press"))
        self.assertIn("frontmost()", script.call_args.args[0])
        with mock.patch.object(mac_host, "osascript", side_effect=RuntimeError("not front")):
            dispatch = mac_host.trigger_run_last_script({"pid": 9})
        self.assertFalse(dispatch.hotkey_dispatched)
        self.assertEqual(dispatch.error, "not front")

    def test_permission_check_reports_disabled_ui_scripting(self):
        with mock.patch.object(mac_host, "osascript", return_value={"enabled": True}):
            self.assertEqual(mac_host.permission_issues(), [])
        with mock.patch.object(mac_host, "osascript", return_value={"enabled": False}):
            self.assertIn("Accessibility is off", mac_host.permission_issues()[0])
        with mock.patch.object(mac_host, "osascript", side_effect=RuntimeError("-1743")):
            self.assertIn("Could not confirm", mac_host.permission_issues()[0])


class ProbeTest(unittest.TestCase):
    def test_home_paths_are_redacted_recursively(self):
        home = mac_probe.HOME
        value = {"a": [f"{home}/Documents/x"], "b": 3}
        self.assertEqual(mac_probe.redact(value), {"a": ["~/Documents/x"], "b": 3})

    def test_entitlements_parse_xml_after_a_blob_header(self):
        plist = (b'junk<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict>'
                 b'<key>com.apple.security.cs.disable-library-validation</key><true/></dict></plist>')
        with mock.patch.object(mac_probe, "run", return_value={"returncode": 0, "stdout": plist}):
            self.assertEqual(mac_probe.entitlements(Path("FL")),
                             {"com.apple.security.cs.disable-library-validation": True})
        with mock.patch.object(mac_probe, "run", return_value={"returncode": 0, "stdout": b""}):
            self.assertEqual(mac_probe.entitlements(Path("FL")), {})

    def test_plugin_databases_are_found_inside_the_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / "FL Studio 2026.app"
            (bundle / "Contents/Resources/FL/Data/Patches/Plugin database/Generators").mkdir(parents=True)
            self.assertEqual(mac_probe.plugin_databases(bundle),
                             [str(Path("Contents/Resources/FL/Data/Patches/Plugin database"))])

    def test_probe_failures_are_reported_not_raised(self):
        self.assertIn("ValueError", mac_probe.guarded(lambda: int("x"))["error"])
        json.dumps(mac_probe.guarded(lambda: {"ok": 1}))


if __name__ == "__main__":
    unittest.main()
