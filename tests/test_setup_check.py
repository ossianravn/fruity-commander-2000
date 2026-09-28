"""A connected bridge alone must not make an incomplete installation ready."""

import unittest

from scripts.check_setup import REQUIRED_TOOLS, assess


class SetupCheckTest(unittest.TestCase):
    def test_connected_stale_launcher_and_unavailable_native_route_need_attention(self):
        report = {'connection': {'connected': True, 'compatible': True,
                                 'bridge_provenance': 'matching'},
                  'capabilities': []}
        self.assertTrue(assess(report, REQUIRED_TOOLS))
        report['capabilities'] = [{'capability': 'native_pattern_placement',
                                   'status': 'unvalidated', 'limitations': []}]
        self.assertTrue(assess(report, REQUIRED_TOOLS))
        report['capabilities'][0]['status'] = 'available'
        self.assertEqual(assess(report, REQUIRED_TOOLS), [])
        self.assertTrue(assess(report, REQUIRED_TOOLS[:-1]))
