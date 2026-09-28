"""Capability reporting must not confuse fixture evidence with current readiness."""

import unittest
from datetime import datetime, timezone

from fl_studio_mcp.contracts import CapabilitiesReport, CapabilityRecord, ConnectionInfo
from scripts.capabilities import owned_report


class CapabilityTest(unittest.TestCase):
    def report(self, connected=True):
        return CapabilitiesReport(generated_at=datetime.now(timezone.utc),
            connection=ConnectionInfo(connected=connected, compatible=connected,
                                      compatibility_reason="fixture"),
            capabilities=[CapabilityRecord(capability=name, status="unavailable") for name in
                ("playlist_clip_enumeration", "automation_curve_inspection_and_crud",
                 "piano_roll_note_snapshot", "raw_audio_buffer_access")])

    def rows(self, **kwargs):
        result = owned_report(self.report(kwargs.pop('connected', True)), **kwargs)
        return {row.capability: row for row in result.capabilities}

    def test_owned_paths_replace_stale_limits_without_promoting_unimplemented_operations(self):
        rows = self.rows(identity={"engine_sha256": "qualified"}, error=None, helper_present=True)
        self.assertEqual(rows['playlist_clip_enumeration'].status, 'available')
        self.assertEqual(rows['automation_curve_inspection_and_crud'].status, 'partial')
        self.assertEqual(rows['raw_audio_buffer_access'].status, 'unavailable')
        self.assertTrue(rows['piano_roll_note_snapshot'].mutates_project)
        self.assertEqual(rows['project_save'].status, 'available')

    def test_missing_helper_leaves_independent_reads_and_save_available(self):
        rows = self.rows(identity={"engine_sha256": "qualified"}, error=None, helper_present=False)
        self.assertEqual(rows['native_pattern_placement'].status, 'unvalidated')
        self.assertIn('build_native.ps1', ' '.join(rows['native_pattern_placement'].limitations))
        self.assertEqual(rows['playlist_clip_enumeration'].limitations, [])
        self.assertEqual(rows['project_save'].status, 'available')

    def test_unqualified_engine_or_disconnected_host_cannot_become_ready_from_fixture_evidence(self):
        for connected, identity, error in [(True, None, 'Engine not qualified'),
                                           (False, {'engine_sha256': 'qualified'}, None)]:
            rows = self.rows(connected=connected, identity=identity, error=error, helper_present=True)
            self.assertEqual(rows['native_pattern_placement'].status, 'unvalidated')
            self.assertEqual(rows['project_save'].status, 'unvalidated')
