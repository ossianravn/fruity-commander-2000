"""Sparse host enumeration and public MCP parsing form one contract."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import jsonschema

from scripts.pattern_inventory import list_patterns
from scripts.postfader_server import prepare_server
from host_fixture import controller_namespace, finish, install_extension


class PatternInventoryTest(unittest.TestCase):
    def test_sparse_inventory_keeps_used_named_empty_and_selected_ids_and_full_names(self):
        host = controller_namespace()
        install_extension(host, "host_patterns.py")
        long_name = "Long name — Æøå " * 8
        host["patterns"].getPatternName.side_effect = lambda i: long_name if i == 7 else f"Pattern {i}"
        raw = finish(host["HANDLERS"]["patterns.list"]({}))
        reader = SimpleNamespace(
            _require_compatible=lambda: SimpleNamespace(warnings=[]), gateway=Mock())
        reader.gateway.call.return_value = raw
        result = list_patterns(reader)
        self.assertEqual([p.pattern_number for p in result.patterns], [2, 5, 7, 9])
        self.assertEqual(result.reported_pattern_count, 2)
        self.assertEqual(result.patterns[2].name, long_name)
        self.assertTrue(result.patterns[1].selected_in_picker)
        self.assertFalse(result.patterns[2].default_empty)
        self.assertTrue(result.patterns[-1].current)
        host["patterns"].jumpToPattern.assert_not_called()
        server = prepare_server()
        tools = asyncio.run(server.mcp.list_tools())
        schema = next(t.output_schema for t in tools if t.name == "fl_list_patterns")
        jsonschema.validate(result.model_dump(mode="json"), schema)

    def test_old_controller_and_duplicate_ids_cannot_look_like_complete_inventory(self):
        host = controller_namespace()
        reader = SimpleNamespace(
            _require_compatible=lambda: SimpleNamespace(warnings=[]), gateway=Mock())
        reader.gateway.call.return_value = finish(host["cmd_patterns_list"]({}))
        self.assertEqual([r["pattern"] for r in reader.gateway.call.return_value["patterns"]],
                         [1, 2])  # The pinned host loses occupied pattern 7.
        with self.assertRaisesRegex(ValueError, "Deploy Fruity Commander"):
            list_patterns(reader)
        install_extension(host, "host_patterns.py")
        raw = finish(host["HANDLERS"]["patterns.list"]({}))
        raw["patterns"].insert(1, raw["patterns"][0])
        reader.gateway.call.return_value = raw
        with self.assertRaisesRegex(ValueError, "duplicate"):
            list_patterns(reader)


if __name__ == "__main__":
    unittest.main()
