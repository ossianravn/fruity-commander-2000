"""Exercise full names from public contracts through host mutation/readback."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import jsonschema

from scripts.pattern_identity import ExpectedIdentity, set_pattern_identity
from scripts.pattern_tool import PatternCreation
from scripts.postfader_server import prepare_server
from host_fixture import controller_namespace, finish, install_extension


class PatternIdentityTest(unittest.TestCase):
    def setUp(self):
        self.host = controller_namespace()
        self.name = "Long phrase — Æøå " * 8
        self.observed = "Original"
        self.host.update(
            SESSION_FINGERPRINT="a" * 32, _pattern_index=lambda i: i,
            _check_session_precondition=Mock(), _save_undo=Mock(return_value=True),
            _fl_color_argument=lambda value: value,
            _fl_colors_equivalent=lambda a, b: a == b)
        self.host["patterns"].getPatternName.side_effect = lambda i: self.observed
        self.host["patterns"].setPatternName.side_effect = self.store_name
        install_extension(self.host, "host_identity.py")

    def store_name(self, index, name):
        self.observed = name

    def call(self, command, arguments, *, session_fingerprint, expected_before):
        arguments["session_fingerprint"] = session_fingerprint
        if expected_before is not None:
            arguments["expected_before"] = expected_before.model_dump(exclude_none=True)
        return finish(self.host["HANDLERS"][command](arguments))

    def test_long_unicode_name_round_trip_precondition_and_mcp_schemas(self):
        request = PatternCreation(name=self.name, phrase_length_qn=4, notes=[])
        writer = SimpleNamespace(_call=self.call)
        result = set_pattern_identity(writer, pattern_number=7, name=request.name)
        self.assertTrue(result.verified)
        self.assertEqual(result.after.name, self.name)
        prior = ExpectedIdentity(name=self.name)
        restored = set_pattern_identity(writer, pattern_number=7, name="Original",
                                        expected_before=prior)
        self.assertTrue(restored.verified)
        self.assertEqual(restored.before.name, self.name)
        tools = asyncio.run(prepare_server().mcp.list_tools())
        tool = next(t for t in tools if t.name == "fl_set_pattern_identity")
        jsonschema.validate({"pattern_number": 7, "name": self.name,
                             "expected_before": {"name": self.name}}, tool.input_schema)
        jsonschema.validate(result.model_dump(mode="json"), tool.output_schema)
        jsonschema.validate(restored.model_dump(mode="json"), tool.output_schema)
        self.host["patterns"].setPatternName.reset_mock()
        with self.assertRaisesRegex(ValueError, "precondition failed"):
            set_pattern_identity(writer, pattern_number=7, name="New", expected_before=prior)
        self.host["patterns"].setPatternName.assert_not_called()

    def test_changed_host_name_is_unverified_and_session_change_cannot_verify(self):
        def shorten(index, name):
            self.observed = name[:64]
        self.host["patterns"].setPatternName.side_effect = shorten
        writer = SimpleNamespace(_call=self.call)
        result = set_pattern_identity(writer, pattern_number=7, name=self.name)
        self.assertFalse(result.verified)
        self.assertEqual(result.after.name, self.name[:64])
        self.host["patterns"].setPatternName.assert_called_once()
        operation = self.host["HANDLERS"]["pattern.set_identity"](
            {"pattern": 7, "name": "Next"})
        next(operation)
        self.host["SESSION_FINGERPRINT"] = "b" * 32
        with self.assertRaisesRegex(ValueError, "session changed"):
            next(operation)


if __name__ == "__main__":
    unittest.main()
