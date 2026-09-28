# Appended to the pinned controller; reuses its mutation and undo contracts.


def fc_pattern_identity(index):
    return {"name": patterns.getPatternName(index),
            "color": _fl_color_word(patterns.getPatternColor(index))}


def fc_set_pattern_identity(a):
    index = _pattern_index(a.get("pattern"))
    requested = {}
    if "name" in a:
        if not isinstance(a["name"], str):
            raise ValueError("pattern name must be text")
        requested["name"] = a["name"]
    if "color" in a:
        _fl_color_argument(a["color"])
        requested["color"] = a["color"]
    if not requested:
        raise ValueError("pattern.set_identity requires name, color, or both")
    _check_session_precondition(a)
    session = SESSION_FINGERPRINT
    before = fc_pattern_identity(index)
    expected = _track_b_expected(a, {"name", "color"}, "pattern identity")
    if expected is not None:
        if "name" in expected and expected["name"] != before["name"]:
            _precondition_failure("pattern name", expected["name"], before["name"])
        if "color" in expected:
            _fl_color_argument(expected["color"])
            if not _fl_colors_equivalent(expected["color"], before["color"]):
                _precondition_failure("pattern color", expected["color"], before["color"])
    undone = _save_undo("Fruity Commander: pattern %d identity" % index)
    if "name" in requested:
        patterns.setPatternName(index, requested["name"])
    if "color" in requested:
        patterns.setPatternColor(index, _fl_color_argument(requested["color"]))
    yield
    if session != SESSION_FINGERPRINT:
        raise ValueError("FL session changed before pattern identity readback")
    after = fc_pattern_identity(index)
    fields = {}
    if "name" in requested:
        fields["name"] = after["name"] == requested["name"]
    if "color" in requested:
        fields["color"] = _fl_colors_equivalent(after["color"], requested["color"])
    return {"command": "pattern.set_identity", "pattern": index,
            "requested": requested, "before": before, "after": after,
            "verified_fields": fields, "verified": all(fields.values()),
            "undo_point_created": undone, **_precondition_report(a)}


HANDLERS["pattern.set_identity"] = fc_set_pattern_identity
