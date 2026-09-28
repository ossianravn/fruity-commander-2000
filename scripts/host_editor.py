"""Target-specific Piano Roll preparation in FL's controller context.

Uses the event-editor/focus technique inspected in calvinw/MacFLStudioMCP
bc08255. Preserve PostFader's session and plugin identity checks, and require
observed focus instead of swallowing errors or resetting the playhead.
"""


def fc_editor_plugin_check(arguments, channel):
    expected = arguments.get("target_fingerprint")
    if expected is None:
        return
    if (not isinstance(expected, str) or len(expected) != 64
            or any(c not in "0123456789abcdef" for c in expected)):
        raise ValueError("target_fingerprint must be 64 lowercase hex characters")
    target = {"target_kind": "channel_generator", "index": channel,
              "channel": channel, "slot": -1, "use_global_index": True,
              "index_scope": "global"}
    if _plugin_observation(target)["target_fingerprint"] != expected:
        raise ValueError("Plugin target changed while preparing the Piano Roll")


def fc_prepare_piano_roll(arguments):
    _require_global_scope(arguments)
    channel = _channel_index(arguments.get("channel"))
    pattern = _pattern_index(arguments.get("pattern"))
    _check_session_precondition(arguments)
    fc_editor_plugin_check(arguments, channel)
    before_channels = _selected_channels()
    before_pattern = patterns.patternNumber()
    window = midi.widPianoRoll
    before_visible = _fl_bool(ui.getVisible(window))
    already_targeted = (before_channels == [channel] and before_pattern == pattern
                        and before_visible and _fl_bool(ui.getFocused(window)))
    if before_pattern != pattern:
        patterns.jumpToPattern(pattern)
        # Pattern switching can select its first populated channel on the next
        # idle tick. Let that finish before establishing the requested editor.
        yield
        _check_session_precondition(arguments)
        fc_editor_plugin_check(arguments, channel)
        if patterns.patternNumber() != pattern:
            raise ValueError("The pattern changed before Piano Roll targeting")
    event_id = channels.getRecEventId(channel, True) + midi.REC_Chan_PianoRoll
    channels.selectOneChannel(channel, True)
    # Rack selection can change while the instrument's editor remains open.
    # openEventEditor toggles that editor closed; generic showWindow then opens
    # the first filtered rack channel. Hide before explicitly opening our event.
    if not already_targeted:
        ui.hideWindow(window)
        ui.openEventEditor(event_id, midi.EE_PR, 0)
    ui.setFocused(window)
    yield
    _check_session_precondition(arguments)
    fc_editor_plugin_check(arguments, channel)
    after_channels = _selected_channels()
    after_pattern = patterns.patternNumber()
    visible = _fl_bool(ui.getVisible(window))
    focused = _fl_bool(ui.getFocused(window))
    if after_channels != [channel] or after_pattern != pattern:
        raise ValueError("Piano Roll target changed: channels=%r pattern=%r" %
                         (after_channels, after_pattern))
    if visible is not True or focused is not True:
        raise ValueError("FL did not establish visible, focused Piano Roll targeting")
    return {
        "command": "creative.prepare_piano_roll",
        "channel_index": channel,
        "target_fingerprint": arguments.get("target_fingerprint"),
        "pattern_number": pattern,
        "before_channel_indices": before_channels,
        "after_channel_indices": after_channels,
        "before_pattern_number": before_pattern,
        "after_pattern_number": after_pattern,
        "piano_roll_visible_before": before_visible,
        "piano_roll_visible_after": visible,
        "selected_target_verified": True,
        "piano_roll_visibility_verified": True,
        "piano_roll_focused": focused,
        "editor_event_id": event_id,
        "session_fingerprint": SESSION_FINGERPRINT,
        "session_precondition_applied": arguments.get("session_fingerprint") is not None,
        "project_saved": False,
    }


HANDLERS["creative.prepare_piano_roll"] = fc_prepare_piano_roll
