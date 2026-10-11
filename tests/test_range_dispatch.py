"""Failure contracts at the existing bridge boundary; no desktop input in tests."""

import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import range_tool


class RangeDispatchTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        directory = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.target = SimpleNamespace(selected_target_verified=True,
                                      piano_roll_visibility_verified=True,
                                      session_fingerprint="project-one")
        creative = range_tool.creative
        self.stack.enter_context(patch.object(range_tool, "ensure_locked_score_session"))
        self.target_call = self.stack.enter_context(
            patch.object(creative, "_target_piano_roll", return_value=self.target))
        self.stack.enter_context(patch.object(creative, "piano_roll_scripts_directory",
                                             return_value=directory))
        self.stack.enter_context(patch.object(creative, "_piano_roll_receipt_path",
                                             return_value=directory / "receipt.json"))
        self.dispatch = self.stack.enter_context(
            patch.object(range_tool, "run_score_script", return_value={}))
        self.receipt = self.stack.enter_context(patch.object(range_tool, "read_receipt"))
        self.stack.enter_context(patch.object(creative, "PIANO_ROLL_RECEIPT_WAIT_SECONDS", 0))
        self.client = Mock()
        self.stack.enter_context(patch.object(range_tool, "get_client", return_value=self.client))
        self.request = range_tool.RangeReplacement(range_start_qn=4, range_end_qn=8, notes=[])

    def run_request(self):
        return range_tool.replace_range(self.request, 5, 2)

    def test_native_failure_and_lost_ack_are_unknown_without_resend(self):
        self.dispatch.side_effect = RuntimeError("Native outcome unknown")
        self.assertEqual(self.run_request()["status"], "unknown")
        self.receipt.assert_not_called()
        self.dispatch.reset_mock()
        self.dispatch.side_effect = None
        self.receipt.side_effect = FileNotFoundError("No host acknowledgement")
        result = self.run_request()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["verification"], "none")
        self.dispatch.assert_called_once()
        self.assertIn("do not resend", result["next_action"])

    def test_unavailable_or_wrong_target_prevents_note_dispatch(self):
        self.target_call.side_effect = RuntimeError("FL bridge unavailable")
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            self.run_request()
        self.target_call.side_effect = None
        self.target.selected_target_verified = False
        with self.assertRaisesRegex(ValueError, "requested Piano Roll target"):
            self.run_request()
        self.dispatch.assert_not_called()

    def test_project_change_invalidates_even_an_applied_receipt(self):
        self.receipt.return_value = {"status": "applied", "message": "Score inspected"}
        self.client.call.return_value = {"channel_indices": [5], "pattern_number": 2,
                                         "session_fingerprint": "different-project"}
        result = self.run_request()
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["observed"]["status"], "applied")
        self.dispatch.assert_called_once()

    def test_failed_receipt_does_not_claim_score_readback(self):
        self.receipt.return_value = {"status": "failed", "message": "Host rejected notes"}
        self.client.call.return_value = {"channel_indices": [5], "pattern_number": 2,
                                         "session_fingerprint": "project-one"}
        result = self.run_request()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["verification"], "host_receipt")
        self.assertEqual(result["observed"], self.receipt.return_value)
        self.dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
