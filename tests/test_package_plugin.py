"""A cached plugin must keep launching the owned runtime, not a missing copied venv."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.package_plugin import ROOT, package


class PackagePluginTest(unittest.TestCase):
    def test_relocated_bundle_preserves_runtime_connection_and_owned_assets(self):
        with tempfile.TemporaryDirectory(prefix='fruity plugin ') as temp:
            base = Path(temp)
            runtime = base / 'installed product'
            for name in ['.codex-plugin/plugin.json', '.agents/skills/fruity-commander/SKILL.md',
                         'assets/icon.png']:
                target = runtime / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            python = runtime / '.venv/Scripts/python.exe'
            shutil.copytree(ROOT / '.agents/skills/fruity-commander/references',
                            runtime / '.agents/skills/fruity-commander/references')
            data = base / 'FL data'
            bundle = package(base / 'output', root=runtime, interpreter=python,
                             user_data=data, midi_port='Fixture MIDI')
            cached = base / 'cache/fruity-commander-2000'
            shutil.copytree(bundle, cached)
            manifest = json.loads((cached / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
            config = json.loads((cached / '.mcp.json').read_text(encoding='utf-8'))
            self.assertEqual(config['mcpServers']['fruity-commander'], {
                'type': 'stdio', 'command': str(python),
                'args': ['-B', str(runtime / 'scripts/postfader_server.py')],
                'env': {'FL_STUDIO_USER_DATA_DIR': str(data), 'FL_BRIDGE_ENABLE_MIDI': '1',
                        'FL_BRIDGE_MIDI_PORT': 'Fixture MIDI', 'FL_BRIDGE_ENABLE_WRITES': '0'},
            })
            self.assertEqual(manifest['name'], cached.name)
            self.assertEqual(manifest['skills'], './skills/')
            self.assertEqual((cached / 'skills/fruity-commander/SKILL.md').read_bytes(),
                             (ROOT / '.agents/skills/fruity-commander/SKILL.md').read_bytes())
            for field in ['composerIcon', 'logo', 'logoDark']:
                self.assertEqual((cached / manifest['interface'][field]).read_bytes(),
                                 (ROOT / 'assets/icon.png').read_bytes())
            self.assertIn(str(runtime / 'SETUP.md'), (cached / 'SETUP.md').read_text(encoding='utf-8'))
            self.assertFalse((cached / '.venv').exists())
            reference = cached / 'skills/fruity-commander/references'
            self.assertIn('splice_search_owned', (reference / 'samples.md').read_text(encoding='utf-8'))
            self.assertIn(str(runtime / 'SETUP.md'), (reference / 'setup.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
