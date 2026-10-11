"""Read explicit host focus evidence through the existing preparation route."""

from typing import Literal
import sys

import anyio
from fl_studio_mcp import creative


class FocusedPianoRollTarget(creative.PianoRollTargetReceipt):
    piano_roll_focused: Literal[True]
    editor_event_id: int


_original_target = creative._target_piano_roll


def focused_target(channel_index, pattern_number, *, session_fingerprint=None,
                   target_fingerprint=None, navigation_only=False):
    if sys.platform == "win32":
        from scripts.windows_shortcut import focus_fl_window

        focus_fl_window()
    elif sys.platform == "darwin":
        from scripts.mac_host import focus_fl

        focus_fl()
    return _original_target(channel_index, pattern_number,
                            session_fingerprint=session_fingerprint,
                            target_fingerprint=target_fingerprint,
                            navigation_only=navigation_only)


def install():
    creative.PianoRollTargetReceipt = FocusedPianoRollTarget
    creative._target_piano_roll = focused_target


def register(server):
    @server.mcp.tool(annotations=server.WORKFLOW_STATE)
    async def piano_roll_prepare_target(
        channel_index: int, pattern_number: int,
        session_fingerprint: str | None = None,
    ) -> FocusedPianoRollTarget:
        """Open the intended Piano Roll and verify host selection, visibility and focus.

        Does not write notes, run a score script, enable musical writes or save.
        This establishes editor readiness separately from score-script startup.
        """
        def prepare():
            with creative._PIANO_ROLL_DISPATCH_LOCK:
                return creative._target_piano_roll(
                    channel_index, pattern_number, session_fingerprint=session_fingerprint,
                    navigation_only=True)
        return await anyio.to_thread.run_sync(prepare)
