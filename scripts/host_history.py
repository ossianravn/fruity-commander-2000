# Appended to the pinned controller. History movement must restore project data.


def _history_snapshot():
    count = _strict_integer(general.getUndoHistoryCount(), "undo history count")
    depth = _strict_integer(general.getUndoHistoryLast(), "undo history depth")
    # The native history is a ring. getUndoHistoryPos is its insertion cursor;
    # getUndoHistoryLast is the restored depth, newest=0. Expose a logical
    # one-based position so callers can compare consecutive undo/redo states.
    if count < 0 or depth < 0 or (count and depth >= count):
        raise ValueError("FL reported inconsistent undo-history bounds")
    position = count - depth
    return {"position": position, "count": count, "last_position": depth,
            "level_hint": general.getUndoLevelHint() or "",
            "project_dirty_flag": general.getChangedFlag(),
            "can_undo": position > 1, "can_redo": depth > 0}


def fc_move_history(a, direction):
    _check_session_precondition(a)
    session = SESSION_FINGERPRINT
    before = _history_snapshot()
    expected = _track_b_expected(
        a, {"position", "count", "project_dirty_flag"}, "project history")
    for key in ("position", "count", "project_dirty_flag"):
        _expect_track_b_value(expected, key, before[key], "history " + key)
    if not before["can_" + direction]:
        raise ValueError("No project history level available for " + direction)
    target = before["position"] + (-1 if direction == "undo" else 1)
    # setUndoHistoryPos changes bookkeeping only. These invoke FL's edit history.
    if direction == "undo":
        general.undoUp()
    else:
        general.undoDown()
    yield
    if session != SESSION_FINGERPRINT:
        raise ValueError("FL session changed during project history restoration")
    after = _history_snapshot()
    return {"command": "project." + direction, "direction": direction,
            "requested_position": target, "before": before, "after": after,
            "verified": after["position"] == target, "undo_point_created": None,
            **_precondition_report(a)}


def fc_undo(a):
    return (yield from fc_move_history(a, "undo"))


def fc_redo(a):
    return (yield from fc_move_history(a, "redo"))


HANDLERS["project.undo"] = fc_undo
HANDLERS["project.redo"] = fc_redo
