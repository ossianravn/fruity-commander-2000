"""Pattern inventory extensions, assembled into the pinned FL controller.

The sparse-index scan follows kaupau/flai-mcp b6f9eec; FL defines default
patterns as empty and unchanged. The active/picker selections remain visible.
Names and indices below are read from FL, never inferred from pattern count.
"""


def fc_patterns_list(arguments):
    if arguments:
        raise ValueError("patterns.list accepts no arguments")
    count, maximum = _pattern_bounds()
    current = patterns.patternNumber()
    rows = []
    for index in range(1, maximum + 1):
        default = _fl_bool(patterns.isPatternDefault(index))
        selected = _fl_bool(patterns.isPatternSelected(index))
        if default is None or selected is None:
            raise ValueError("FL did not report pattern occupancy/selection at %d" % index)
        if not default or selected or index == current:
            row = _pattern_summary(index)
            row.update(name=patterns.getPatternName(index), default=default,
                       selected=selected, current=index == current)
            rows.append(row)
        if index % PATTERNS_PER_TICK == 0 and index < maximum:
            yield
    return {
        "command": "patterns.list",
        "inventory_scope": "nondefault_and_selected",
        "current_pattern": current,
        "pattern_count": count,
        "pattern_max": maximum,
        "patterns": rows,
        "unsaved_changes": general.getChangedFlag(),
    }


HANDLERS["patterns.list"] = fc_patterns_list
