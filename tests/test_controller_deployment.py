"""Deployment and connection diagnostics describe the same composed source."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from fl_studio_mcp import bridge_install, readonly_inspector

from scripts.controller_deployment import configure, controller_sources, expected_deployment


class ControllerDeploymentTest(unittest.TestCase):
    def test_deployed_extensions_are_stamped_and_installation_is_repeatable(self):
        original = bridge_install.bridge_source_path().read_bytes()
        configure()
        deployed, digest = expected_deployment()
        source = b"\n\n".join(path.read_bytes() for path in controller_sources())
        self.assertEqual(digest, hashlib.sha256(source).hexdigest())
        compile(deployed, "deployed controller", "exec")
        self.assertIn(b'HANDLERS["patterns.list"] = fc_patterns_list', deployed)
        self.assertIn(b'HANDLERS["creative.prepare_piano_roll"] = fc_prepare_piano_roll', deployed)
        self.assertEqual(readonly_inspector.expected_bridge_deployment(), (deployed, digest))
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "Settings" / "Hardware").mkdir(parents=True)
            first = bridge_install.deploy(directory)
            second = bridge_install.deploy(directory)
            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            self.assertEqual(first["target"].read_bytes(), deployed)
        self.assertEqual(bridge_install.bridge_source_path().read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
