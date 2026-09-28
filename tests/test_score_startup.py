"""Automatic startup requires owned script identity and its signed receipt."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import score_startup as startup


class ScoreStartupTest(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.directory = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        c = startup.creative
        self.registry = c._PianoRollRegistry()
        stack.enter_context(patch.object(c, "PIANO_ROLL", self.registry))
        stack.enter_context(patch.object(c, "piano_roll_scripts_directory", return_value=self.directory))
        stack.enter_context(patch.object(c, "PIANO_ROLL_RECEIPT_WAIT_SECONDS", 0))
        self.target = SimpleNamespace(selected_target_verified=True,
                                      piano_roll_visibility_verified=True,
                                      session_fingerprint="a" * 32)
        stack.enter_context(patch.object(c, "_target_piano_roll", return_value=self.target))
        self.client = Mock()
        self.client.call.return_value = {"channel_indices": [5], "pattern_number": 3,
                                         "session_fingerprint": "a" * 32}
        stack.enter_context(patch.object(startup, "get_client", return_value=self.client))
        self.trigger = stack.enter_context(patch.object(startup, "run_owned_score_script",
                                                        side_effect=self.execute_bootstrap))

    def execute_bootstrap(self):
        script = self.directory / startup.creative.PIANO_ROLL_SCRIPT_NAME
        # Execute the real no-note-change bootstrap with ordinary Python, not FL.
        exec(compile(script.read_text(), str(script), "exec"), {})
        return {"script_path": str(script)}

    def test_fresh_process_arms_from_correlated_receipt_without_user_confirmation(self):
        result = startup.ensure_score_session(5, 3)
        self.assertEqual(result["verification"], "signed_host_bootstrap_receipt")
        self.assertTrue(self.registry.status().armed_this_session)
        self.assertTrue(startup.ensure_score_session(5, 3)["ready"])
        self.trigger.assert_called_once()

    def test_native_failure_does_not_arm_or_resend(self):
        self.trigger.side_effect = RuntimeError("Native outcome unknown")
        with self.assertRaisesRegex(RuntimeError, "unknown"):
            startup.ensure_score_session(5, 3)
        self.assertFalse(self.registry.status().armed_this_session)
        self.trigger.assert_called_once()

    def test_missing_receipt_or_changed_project_cannot_arm(self):
        self.trigger.side_effect = lambda: {"script_path": "Owned.pyscript"}
        with self.assertRaisesRegex(ValueError, "arming proof"):
            startup.ensure_score_session(5, 3)
        self.assertFalse(self.registry.status().armed_this_session)
        self.trigger.side_effect = self.execute_bootstrap
        self.client.call.return_value["session_fingerprint"] = "b" * 32
        with self.assertRaisesRegex(ValueError, "target changed"):
            startup.ensure_score_session(5, 3)
        self.assertFalse(self.registry.status().armed_this_session)


if __name__ == "__main__":
    unittest.main()
