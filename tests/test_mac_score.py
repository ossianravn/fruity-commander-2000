"""macOS score startup: one user run per FL launch, then signed automatic reruns."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fl_studio_mcp import creative
from fl_studio_mcp.creative import HotkeyDispatch

from scripts import mac_host, mac_score, score_startup


FL = {"pid": 4242, "launched": 1760000000.25}
SENT = HotkeyDispatch(platform="macos", shortcut="Cmd+Opt+Y", fl_window_found=True,
                      fl_window_focused=True, hotkey_dispatched=True)
REFUSED = HotkeyDispatch(platform="macos", shortcut="Cmd+Opt+Y", fl_window_found=True,
                         fl_window_focused=False, hotkey_dispatched=False,
                         error="Accessibility denied")


class MacScoreTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="fc scripts ")
        self.scripts = Path(self.directory.name)
        patches = [mock.patch.dict(os.environ, {creative.PIANO_ROLL_SCRIPTS_DIR_ENV: str(self.scripts)}),
                   mock.patch.object(mac_host, "running_fl", return_value=FL),
                   mock.patch.object(mac_host, "trigger_run_last_script", return_value=SENT),
                   mock.patch.object(creative, "_await_arm_receipt", return_value=(True, None))]
        self.mocks = [patch.start() for patch in patches]
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(self.directory.cleanup)
        self.trigger, self.receipt = self.mocks[2], self.mocks[3]
        self.registry = SimpleNamespace(_prepared=False, _armed=False, _arm_receipt_path=None,
                                        _arm_receipt_secret=None, _arm_request_id=None)
        self.prepared = 0

    def prepare(self, registry):
        self.prepared += 1
        registry._prepared, registry._armed = True, False
        registry._arm_request_id, registry._arm_receipt_secret = f"r{self.prepared}", "ab"
        registry._arm_receipt_path = self.scripts / f"receipt-{self.prepared}.json"

    def marker(self, value):
        mac_score.marker_path().write_text(json.dumps(value), encoding="ascii")

    def test_first_launch_asks_the_user_without_pressing_any_key(self):
        with self.assertRaisesRegex(mac_score.ScoreRuntimeNeedsUser, "Postfader Apply"):
            mac_score.arm(self.registry, self.prepare)
        self.trigger.assert_not_called()
        self.assertTrue(self.registry._prepared)
        self.assertFalse(mac_score.marker_path().exists())

    def test_user_run_receipt_arms_and_records_this_fl_launch(self):
        with self.assertRaises(mac_score.ScoreRuntimeNeedsUser):
            mac_score.arm(self.registry, self.prepare)
        self.registry._arm_receipt_path.write_text("{}", encoding="ascii")
        result = mac_score.arm(self.registry, self.prepare)
        self.assertEqual(result["startup_route"], "macos_user_ran_script")
        self.assertEqual(self.prepared, 1, "the user-run bootstrap must not be replaced")
        self.receipt.assert_called_with(self.registry._arm_receipt_path, receipt_secret="ab",
                                        request_id="r1")
        self.trigger.assert_not_called()
        self.assertEqual(mac_score.read_marker(), {"process_id": 4242, "launched": FL["launched"]})

    def test_same_fl_launch_reruns_the_script_once_with_signed_proof(self):
        self.marker({"process_id": 4242, "launched": FL["launched"]})
        result = mac_score.arm(self.registry, self.prepare)
        self.assertEqual(result["startup_route"], "macos_rerun_last_script")
        self.trigger.assert_called_once_with(FL)
        self.assertTrue(result["script_path"].endswith(creative.PIANO_ROLL_SCRIPT_NAME))

    def test_unproven_rerun_asks_the_user_and_never_repeats_the_key(self):
        self.marker({"process_id": 4242, "launched": FL["launched"]})
        self.receipt.return_value = (False, "no receipt")
        with self.assertRaisesRegex(mac_score.ScoreRuntimeNeedsUser, "no receipt"):
            mac_score.arm(self.registry, self.prepare)
        self.trigger.assert_called_once()

    def test_refused_shortcut_reports_permission_error(self):
        self.marker({"process_id": 4242, "launched": FL["launched"]})
        self.trigger.return_value = REFUSED
        with self.assertRaisesRegex(mac_score.ScoreRuntimeNeedsUser, "Accessibility denied"):
            mac_score.arm(self.registry, self.prepare)
        self.receipt.assert_not_called()

    def test_marker_from_another_fl_launch_is_not_trusted(self):
        self.marker({"process_id": 4242, "launched": FL["launched"] - 60})
        with self.assertRaises(mac_score.ScoreRuntimeNeedsUser):
            mac_score.arm(self.registry, self.prepare)
        self.trigger.assert_not_called()

    def test_later_edits_require_a_sent_shortcut(self):
        self.assertTrue(mac_score.run_owned_score_script()["script_path"])
        self.trigger.return_value = REFUSED
        with self.assertRaisesRegex(RuntimeError, "Accessibility denied"):
            mac_score.run_owned_score_script()


class ScoreRouteSelectionTest(unittest.TestCase):
    def test_macos_uses_the_assisted_route_and_windows_the_native_helper(self):
        with mock.patch.object(score_startup, "is_macos", return_value=True), \
                mock.patch.object(mac_score, "arm", return_value={"startup_route": "x"}) as arm, \
                mock.patch.object(mac_score, "run_owned_score_script", return_value="mac"), \
                mock.patch.object(score_startup, "run_owned_score_script",
                                  side_effect=AssertionError("native helper")):
            self.assertEqual(score_startup.start_runtime("registry"), {"startup_route": "x"})
            arm.assert_called_once_with("registry", score_startup.prepare_locked)
            self.assertEqual(score_startup.run_score_script(), "mac")
        with mock.patch.object(score_startup, "is_macos", return_value=False), \
                mock.patch.object(score_startup, "run_owned_score_script", return_value="win"):
            self.assertEqual(score_startup.run_score_script(), "win")


if __name__ == "__main__":
    unittest.main()
