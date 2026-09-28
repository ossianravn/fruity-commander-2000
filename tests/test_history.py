"""History restoration calls real host operations, not position metadata setters."""

import unittest
from unittest.mock import Mock

from host_fixture import controller_namespace, finish, install_extension


class HistoryTest(unittest.TestCase):
    def test_restore_both_directions_and_reject_stale_history(self):
        host = controller_namespace()
        state = {"position": 2, "count": 2, "project_dirty_flag": 1,
                 "can_undo": True, "can_redo": False}
        host.update(SESSION_FINGERPRINT="a" * 32, _check_session_precondition=Mock(),
                    _precondition_report=lambda a: {})
        host["general"].getUndoHistoryCount = lambda: 2
        host["general"].getUndoHistoryLast = lambda: 2 - state["position"]
        host["general"].getUndoHistoryPos = lambda: 2
        host["general"].getUndoLevelHint = lambda: "History entry"

        def move(delta):
            state.update(position=state["position"] + delta, can_redo=delta < 0)

        host["general"].undoUp = Mock(side_effect=lambda: move(-1))
        host["general"].undoDown = Mock(side_effect=lambda: move(1))
        host["general"].setUndoHistoryPos = Mock()
        install_extension(host, "host_history.py")
        for direction, position in (("undo", 1), ("redo", 2)):
            result = finish(host["HANDLERS"]["project." + direction]({}))
            self.assertTrue(result["verified"])
            self.assertEqual(result["after"]["position"], position)
        host["general"].setUndoHistoryPos.assert_not_called()
        with self.assertRaisesRegex(ValueError, "precondition failed"):
            finish(host["HANDLERS"]["project.undo"]({"expected_before": {"position": 1}}))
        host["general"].undoUp.assert_called_once()


if __name__ == "__main__":
    unittest.main()
