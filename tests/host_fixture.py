"""Load the production host handlers with only their FL API dependencies faked."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fl_studio_mcp.bridge_install import bridge_source_path


def controller_namespace():
    tree = ast.parse(bridge_source_path().read_text(encoding="ascii"))
    names = {"_fl_bool", "_strict_integer", "_pattern_summary", "cmd_patterns_list",
             "_precondition_report", "_track_b_expected", "_expected_before",
             "_precondition_failure", "_expect_track_b_value"}
    selected = ast.Module(body=[node for node in tree.body
                                if isinstance(node, ast.FunctionDef) and node.name in names],
                          type_ignores=[])
    patterns = Mock()
    patterns.patternNumber.return_value = 9
    patterns.isPatternDefault.side_effect = lambda i: int(i not in (2, 7))
    patterns.isPatternSelected.side_effect = lambda i: int(i == 5)
    patterns.getPatternName.side_effect = lambda i: "Named empty" if i == 7 else f"Pattern {i}"
    patterns.getPatternColor.return_value = 0
    patterns.getPatternLength.return_value = 16
    namespace = {
        "patterns": patterns, "general": SimpleNamespace(getChangedFlag=lambda: 0),
        "PATTERNS_PER_TICK": 3, "_pattern_bounds": lambda: (2, 12),
        "_safe": lambda call, default: call(), "_fl_color_word": lambda value: value,
        "HANDLERS": {},
    }
    exec(compile(selected, str(bridge_source_path()), "exec"), namespace)
    return namespace


def install_extension(namespace, name):
    path = Path(__file__).resolve().parents[1] / "scripts" / name
    exec(compile(path.read_text(encoding="ascii"), str(path), "exec"), namespace)


def finish(generator):
    while True:
        try:
            next(generator)
        except StopIteration as result:
            return result.value
