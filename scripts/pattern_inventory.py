"""Preserve sparse host identities at all existing pattern-list callers."""

from typing import Literal

from pydantic import Field

from fl_studio_mcp import performance
from fl_studio_mcp.track_b_contracts import PatternList, PatternSummary


class ObservedPattern(PatternSummary):
    # Reading a host name must not inherit a dependency's setter restriction.
    name: str
    length_beats: int | None = Field(default=None, ge=0, description=
        'Legacy raw FL length: sixteenth-note steps on the qualified host, not quarter notes. '
        'Use piano_roll_inspect_score for exact phrase extent in quarter notes.')


class PatternInventory(PatternList):
    patterns: list[ObservedPattern]
    inventory_scope: Literal["nondefault_and_selected"] = "nondefault_and_selected"


def list_patterns(self):
    connection = self._require_compatible()
    raw = self.gateway.call("patterns.list")
    if raw.get("command") != "patterns.list":
        raise ValueError("FL bridge returned the wrong pattern-list command")
    if raw.get("inventory_scope") != "nondefault_and_selected":
        raise ValueError("The running controller lacks sparse pattern discovery. "
                         "Deploy Fruity Commander's controller and reload it in FL.")
    maximum = performance._strict_int(raw.get("pattern_max"), "pattern_max",
                                      low=1, high=performance.MAX_PATTERN_NUMBER)
    current = performance._strict_int(raw.get("current_pattern"), "current_pattern",
                                      low=1, high=maximum)
    count = performance._strict_int(raw.get("pattern_count"), "pattern_count",
                                    low=0, high=maximum)
    rows = raw.get("patterns")
    if not isinstance(rows, list):
        raise ValueError("FL bridge returned malformed pattern rows")
    parsed, previous = [], 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("FL bridge returned a malformed pattern row")
        number = performance._strict_int(row.get("pattern"), "pattern number",
                                         low=1, high=maximum)
        if number <= previous:
            raise ValueError("FL bridge returned duplicate or unordered pattern IDs")
        previous = number
        active = performance._strict_bool(row, "current")
        if active != (number == current):
            raise ValueError("FL bridge returned inconsistent current pattern identity")
        parsed.append(ObservedPattern(
            pattern_number=number, name=row.get("name"),
            color=performance._bridge_color(row.get("color"), "pattern"),
            length_beats=performance._optional_int(row.get("length")),
            current=active,
            selected_in_picker=performance._strict_bool(row, "selected"),
            default_empty=performance._strict_bool(row, "default"),
        ))
    if not any(row.current for row in parsed):
        raise ValueError("FL bridge omitted the current pattern")
    return PatternInventory(
        observed_at=performance._now(), current_pattern_number=current,
        reported_pattern_count=count, maximum_pattern_number=maximum,
        patterns=parsed, project_dirty_flag=performance._dirty(raw.get("unsaved_changes")),
        warnings=performance._warnings(raw, list(connection.warnings)),
    )


def install():
    performance.TrackBInspector.list_patterns = list_patterns


def register(server):
    # Replace the existing public tool so its schema accepts full host names.
    server.mcp.remove_tool("fl_list_patterns")

    @server.mcp.tool(name="fl_list_patterns", annotations=server.READ_ONLY)
    async def fl_list_patterns() -> PatternInventory:
        """Read nondefault and selected patterns, preserving actual sparse IDs.

        Includes named-empty patterns and the current/picker selection. Host
        pattern count is metadata, not the highest ID or returned row count.
        The legacy length_beats field is raw FL length (sixteenth steps on the
        qualified host); use piano_roll_inspect_score for exact quarter notes.
        """
        return await server._performance_read("list_patterns")
