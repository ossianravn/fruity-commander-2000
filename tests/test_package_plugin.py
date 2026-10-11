"""A cached plugin must keep launching the owned runtime, not a missing copied venv."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from zipfile import ZipFile

from scripts.package_plugin import ROOT, package, plugin_files


class PackagePluginTest(unittest.TestCase):
    def test_relocated_bundle_preserves_runtime_connection_and_owned_assets(self):
        with tempfile.TemporaryDirectory(prefix='fruity plugin ') as temp:
            base = Path(temp)
            runtime = base / 'installed product'
            for name in ['.codex-plugin/plugin.json', '.claude-plugin/plugin.json',
                         '.agents/skills/fruity-commander/SKILL.md',
                         'assets/icon.png']:
                target = runtime / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            claude_source = runtime / '.claude-plugin/plugin.json'
            metadata = json.loads(claude_source.read_text(encoding='utf-8'))
            metadata['description'] = 'Claude-specific fixture description'
            claude_source.write_text(json.dumps(metadata), encoding='utf-8')
            python = runtime / '.venv/Scripts/python.exe'
            shutil.copytree(ROOT / '.agents/skills/fruity-commander/references',
                            runtime / '.agents/skills/fruity-commander/references')
            data = base / 'FL data'
            bundle = package(base / 'output', root=runtime, interpreter=python,
                             user_data=data, midi_port='Fixture MIDI', archive=True)
            cached = base / 'cache/fruity-commander-2000'
            with ZipFile(bundle.with_suffix('.zip')) as archive:
                archive.extractall(cached)
            manifest = json.loads((cached / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
            claude = json.loads((cached / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))
            self.assertEqual(claude['name'], manifest['name'])
            self.assertEqual(claude['description'], metadata['description'])
            self.assertEqual(claude['mcpServers'], './.mcp.json')
            self.assertEqual(claude['skills'], './skills/')
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
            self.assertIn('fl_add_mixer_effect', (reference / 'effects.md').read_text(encoding='utf-8'))
            self.assertIn(str(runtime / 'SETUP.md'), (reference / 'setup.md').read_text(encoding='utf-8'))

    def test_macos_bundle_uses_the_iac_default_and_mac_guide(self):
        with tempfile.TemporaryDirectory(prefix='fruity mac ') as temp:
            base = Path(temp)
            python = base / 'runtime/.venv/bin/python'
            name, files = plugin_files(ROOT, python, user_data=base / 'FL data',
                                       platform_name='darwin')
            server = json.loads(files['.mcp.json'])['mcpServers']['fruity-commander']
            self.assertEqual(server['command'], str(python))
            self.assertEqual(server['env']['FL_BRIDGE_MIDI_PORT'], 'IAC Driver')
            setup = files['SETUP.md'].decode('utf-8')
            self.assertIn(str(ROOT / 'SETUP-macOS.md'), setup)
            self.assertIn('local macOS sessions', setup)
            self.assertNotIn('native helper', setup)
            self.assertIn('skills/fruity-commander/references/macos.md', sorted(files))


if __name__ == '__main__':
    unittest.main()
