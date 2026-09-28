"""Target a visible but obscured/wrong editor and verify later host focus."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import editor_contract
from scripts.editor_contract import FocusedPianoRollTarget
from host_fixture import controller_namespace, finish, install_extension


class EditorPreparationTest(unittest.TestCase):
    def test_desktop_foreground_precedes_host_focus_request(self):
        calls = []
        with patch.object(editor_contract.sys, "platform", "win32"), \
                patch("scripts.windows_shortcut.focus_fl_window", side_effect=lambda: calls.append("focus")), \
                patch.object(editor_contract, "_original_target",
                             side_effect=lambda *a, **kw: calls.append("target")):
            editor_contract.focused_target(5, 3, navigation_only=True)
        self.assertEqual(calls, ["focus", "target"])

    def setUp(self):
        self.host = controller_namespace()
        self.ui = Mock()
        self.ui.getVisible.return_value = 1
        self.ui.getFocused.return_value = 1
        self.host.update(
            ui=self.ui, midi=SimpleNamespace(widPianoRoll=3, REC_Chan_PianoRoll=10, EE_PR=1),
            channels=Mock(), _require_global_scope=Mock(), _channel_index=lambda i: i,
            _pattern_index=lambda i: i, _check_session_precondition=Mock(),
            _selected_channels=lambda: [5], SESSION_FINGERPRINT="a" * 32,
        )
        def event_id(index, use_global=False):
            if not use_global:
                raise RuntimeError("Index outside the filtered Channel Rack group")
            return 1000
        self.host["channels"].getRecEventId.side_effect = event_id
        install_extension(self.host, "host_editor.py")
        self.arguments = {"channel": 5, "pattern": 9, "index_scope": "global",
                          "session_fingerprint": "a" * 32}

    def test_visible_matching_selection_still_retargets_and_focuses(self):
        self.ui.getFocused.side_effect = [0, 1]
        operation = self.host["HANDLERS"]["creative.prepare_piano_roll"](self.arguments)
        next(operation)
        self.ui.openEventEditor.assert_called_once_with(1010, 1, 0)
        self.ui.setFocused.assert_called_once_with(3)
        self.ui.getFocused.assert_called_once_with(3)
        receipt = FocusedPianoRollTarget.model_validate(finish(operation))
        self.assertTrue(receipt.piano_roll_focused)
        self.assertEqual(receipt.editor_event_id, 1010)

    def test_already_focused_target_is_not_toggled_to_previous_editor(self):
        result = finish(self.host["fc_prepare_piano_roll"](self.arguments))
        self.assertTrue(result["piano_roll_focused"])
        self.ui.openEventEditor.assert_not_called()
        self.ui.hideWindow.assert_not_called()

    def test_automation_selection_does_not_toggle_existing_instrument_editor_closed(self):
        state = {'selected': [6], 'visible': True}
        self.host['_selected_channels'] = lambda: state['selected']
        self.ui.getVisible.side_effect = lambda window: state['visible']
        # Automation creation selects an automation channel but leaves the
        # instrument's editor open. Selecting its hidden rack row clears selection.
        self.host['channels'].selectOneChannel.side_effect = lambda *args: state.update(selected=[])
        self.ui.hideWindow.side_effect = lambda window: state.update(visible=False)

        def open_editor(*args):
            if state['visible']:
                state['visible'] = False
            else:
                state.update(visible=True, selected=[5])

        def show_window(window):
            if not state['visible']:
                state.update(visible=True, selected=[6])

        self.ui.openEventEditor.side_effect = open_editor
        self.ui.showWindow.side_effect = show_window
        result = finish(self.host['fc_prepare_piano_roll'](self.arguments))
        self.assertEqual(result['after_channel_indices'], [5])
        self.assertTrue(result['piano_roll_visible_after'])

    def test_focus_failure_or_session_change_cannot_report_ready(self):
        self.ui.getFocused.return_value = 0
        with self.assertRaisesRegex(ValueError, "focused Piano Roll"):
            finish(self.host["fc_prepare_piano_roll"](self.arguments))

        self.host["_check_session_precondition"].side_effect = [None, ValueError("Session changed")]
        with self.assertRaisesRegex(ValueError, "Session changed"):
            finish(self.host["fc_prepare_piano_roll"](self.arguments))

    def test_pattern_switch_settles_before_selecting_instrument(self):
        self.host["patterns"].patternNumber.side_effect = [3, 9, 9]
        operation = self.host["fc_prepare_piano_roll"](self.arguments)
        next(operation)
        self.host["channels"].selectOneChannel.assert_not_called()
        self.ui.openEventEditor.assert_not_called()
        result = finish(operation)
        self.assertEqual(result["after_channel_indices"], [5])
        self.host["channels"].selectOneChannel.assert_called_once_with(5, True)


if __name__ == "__main__":
    unittest.main()
