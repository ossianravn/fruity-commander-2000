"""Off Windows, owned routes must fail clearly and report their actual availability."""

import unittest
from datetime import datetime, timezone
from unittest import mock

from fl_studio_mcp import readonly_inspector
from fl_studio_mcp.contracts import CapabilitiesReport, CapabilityRecord, ConnectionInfo

from scripts import capabilities, host_platform, native_host, windows_project
from scripts.check_setup import REQUIRED_TOOLS, assess, windows_only
from scripts.mac_capabilities import ASSISTED_SCORE, NO_MAC_ROUTE, OTHER_OS, macos_report


def on(family):
    return mock.patch.object(host_platform, "platform_family", return_value=family)


def report(connected=True):
    return CapabilitiesReport(generated_at=datetime.now(timezone.utc),
        connection=ConnectionInfo(connected=connected, compatible=connected,
                                  compatibility_reason="fixture", bridge_provenance="matching"),
        capabilities=[CapabilityRecord(capability=name, status="unavailable") for name in
            ("playlist_clip_enumeration", "automation_curve_inspection_and_crud",
             "piano_roll_note_snapshot", "raw_audio_buffer_access")])


class PlatformBoundaryTest(unittest.TestCase):
    def test_native_routes_fail_before_any_win32_access_on_macos(self):
        explode = mock.Mock(side_effect=AssertionError("Win32 API was opened"))
        with on("macos"), mock.patch.object(windows_project, "_windows_api", explode):
            with self.assertRaisesRegex(host_platform.HostRouteUnavailable, "no macOS route"):
                windows_project.ProjectReader().__enter__()
            with self.assertRaisesRegex(OSError, "fl_get_capabilities"):
                native_host.native_api()
        explode.assert_not_called()

    def test_windows_keeps_the_qualified_native_route(self):
        with on("windows"):
            self.assertIsNone(host_platform.require_windows_native("Fixture"))
        with on("other"), self.assertRaisesRegex(OSError, "this operating system"):
            host_platform.require_windows_native("Fixture")


class MacCapabilityTest(unittest.TestCase):
    def rows(self, **kwargs):
        connected = kwargs.pop("connected", True)
        return {row.capability: row for row in
                macos_report(report(connected), **kwargs).capabilities}

    def test_native_helper_operations_are_unavailable_not_unvalidated(self):
        rows = self.rows()
        for name in ("native_pattern_placement", "automation_curve_inspection_and_crud",
                     "playlist_clip_enumeration", "project_save", "native_project_save_as",
                     "sample_import_and_placement", "native_mixer_effect_loading",
                     "native_generator_loading_and_setup"):
            self.assertEqual(rows[name].status, "unavailable", name)
            self.assertIn(NO_MAC_ROUTE, rows[name].limitations)
        self.assertIn("Cmd+S", " ".join(rows["project_save"].limitations))
        self.assertEqual(rows["raw_audio_buffer_access"].status, "unavailable")

    def test_assisted_routes_stay_unvalidated_until_a_real_mac_run(self):
        rows = self.rows()
        for name in ("editable_note_creation_and_range_revision", "piano_roll_note_snapshot"):
            self.assertEqual(rows[name].status, "unvalidated")
            self.assertIn(ASSISTED_SCORE, rows[name].limitations)
        loading = rows["macos_add_menu_plugin_loading"]
        self.assertEqual(loading.access_path, "plugins_list_available / plugins_load")
        self.assertIn("Accessibility", " ".join(loading.limitations))
        disconnected = self.rows(connected=False)
        self.assertIn("IAC", disconnected["editable_note_creation_and_range_revision"].limitations[0])

    def test_unsupported_os_never_offers_a_route(self):
        rows = self.rows(macos=False)
        self.assertEqual(rows["editable_note_creation_and_range_revision"].status, "unavailable")
        self.assertEqual(rows["macos_add_menu_plugin_loading"].limitations, [OTHER_OS])

    def test_installed_report_skips_native_identity_off_windows(self):
        original = readonly_inspector.ReadOnlyInspector.capabilities

        def fake(self):
            return report()
        try:
            readonly_inspector.ReadOnlyInspector.capabilities = fake
            capabilities.install()
            with mock.patch.object(capabilities, "family", return_value="macos"), \
                    mock.patch.object(capabilities, "native_context",
                                      side_effect=AssertionError("native read")):
                result = readonly_inspector.ReadOnlyInspector.capabilities(object())
        finally:
            readonly_inspector.ReadOnlyInspector.capabilities = original
        names = {row.capability for row in result.capabilities}
        self.assertIn("macos_add_menu_plugin_loading", names)


class MacSetupCheckTest(unittest.TestCase):
    def test_macos_readiness_does_not_require_windows_native_routes(self):
        result = macos_report(report()).model_dump(mode="json")
        self.assertEqual(assess(result, REQUIRED_TOOLS, "macos"), [])
        self.assertTrue(assess(result, REQUIRED_TOOLS, "windows"))
        self.assertIn("native_pattern_placement", windows_only(result))
        self.assertNotIn("editable_note_creation_and_range_revision", windows_only(result))

    def test_unsupported_platform_rows_are_not_ready(self):
        result = macos_report(report(), macos=False).model_dump(mode="json")
        self.assertIn(OTHER_OS, assess(result, REQUIRED_TOOLS, "macos"))


if __name__ == "__main__":
    unittest.main()
