"""Build a local Codex plugin connected to this installed Fruity Commander runtime."""

import argparse
import json
import sys
from pathlib import Path

from fl_studio_mcp.client_config import configuration_facts
from fl_studio_mcp.host_config import HostConfigurationError


ROOT = Path(__file__).resolve().parents[1]


def plugin_files(root, interpreter, *, user_data=None, midi_port=None):
    """Resolve installed paths once; package metadata, never the Python/native runtime."""
    root = Path(root).resolve()
    # Keep a virtual-environment interpreter path even when it is a symlink.
    facts = configuration_facts(repository_root=root, interpreter=Path(interpreter).absolute(),
                                user_data_dir=user_data, transport='midi',
                                midi_port=midi_port, server_name='fruity-commander')
    manifest = json.loads((root / '.codex-plugin/plugin.json').read_text(encoding='utf-8'))
    manifest.update(skills='./skills/', mcpServers='./.mcp.json')
    config = {'mcpServers': {facts.server_name: {
        'type': 'stdio', 'command': str(facts.interpreter),
        'args': ['-B', str(root / 'scripts/postfader_server.py')],
        'env': {**facts.environment, 'FL_BRIDGE_ENABLE_WRITES': '0'},
    }}}
    setup = (
        '# Fruity Commander local installation\n\n'
        f'This plugin connects to the installed runtime at `{root}`.\n'
        'Keep that installation in place; the plugin cache contains its icon and\n'
        'workflow, while Python, dependencies and the native helper stay there.\n\n'
        f'Read the installation and troubleshooting guide at [{root / "SETUP.md"}]'
        f'(<{root / "SETUP.md"}>).\n'
        f'Configured FL user data: `{facts.environment["FL_STUDIO_USER_DATA_DIR"]}`.\n'
        f'Configured MIDI port: `{facts.environment["FL_BRIDGE_MIDI_PORT"]}`.\n\n'
        'If the installation moves, regenerate this bundle and reinstall it.\n'
        'Use one active Fruity Commander connection: this plugin replaces the\n'
        'separate manual MCP registration when you activate it.\n'
    )
    files = {
        '.codex-plugin/plugin.json': (json.dumps(manifest, indent=2) + '\n').encode('utf-8'),
        '.mcp.json': (json.dumps(config, indent=2) + '\n').encode('utf-8'),
        'skills/fruity-commander/SKILL.md':
            (root / '.agents/skills/fruity-commander/SKILL.md').read_bytes(),
        'assets/icon.png': (root / 'assets/icon.png').read_bytes(),
        'SETUP.md': setup.encode('utf-8'),
    }
    references = root / '.agents/skills/fruity-commander/references'
    for path in references.rglob('*.md'):
        relative = path.relative_to(references).as_posix()
        files[f'skills/fruity-commander/references/{relative}'] = path.read_bytes()
    files['skills/fruity-commander/references/setup.md'] = setup.encode('utf-8')
    return manifest['name'], files


def package(output_dir, *, root=ROOT, interpreter=sys.executable, user_data=None, midi_port=None):
    name, files = plugin_files(root, interpreter, user_data=user_data, midi_port=midi_port)
    destination = Path(output_dir).resolve() / name
    for relative, content in files.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / '.local/plugins',
                        help='Parent directory for the generated fruity-commander-2000 bundle')
    parser.add_argument('--user-data-dir', type=Path,
                        help='FL user-data directory; otherwise use configured/default host path')
    parser.add_argument('--midi-port', help='Existing virtual MIDI query; otherwise use host configuration')
    options = parser.parse_args()
    try:
        destination = package(options.output_dir, user_data=options.user_data_dir,
                              midi_port=options.midi_port)
    except (OSError, ValueError, HostConfigurationError) as error:
        parser.exit(1, f'Plugin packaging failed: {error}\n')
    print(f'Local plugin bundle: {destination}')
    print('The bundle uses this installed runtime. No client registration or FL settings changed.')


if __name__ == '__main__':
    main()
