"""Check this installation through a fresh, read-only standard MCP connection."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Support the documented direct execution as well as module imports in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import mac_host
from scripts.host_platform import family
from scripts.mac_capabilities import NO_MAC_ROUTE


REQUIRED_TOOLS = (
    "fl_get_capabilities", "piano_roll_create_pattern", "piano_roll_inspect_score",
    "piano_roll_replace_range", "fl_list_installed_generators", "fl_add_generator",
    "fl_load_generator_state", "fl_create_automation_clip", "fl_replace_automation_points",
    "fl_inspect_native_arrangement", "fl_place_pattern_clip", "fl_set_playlist_time_selection",
    "fl_get_project_file", "fl_save_project", "fl_save_project_as",
)


# The owned route each platform must expose before musical work can start.
READINESS_ROW = {'windows': 'native_pattern_placement',
                 'macos': 'editable_note_creation_and_range_revision'}


def assess(report, tools, platform='windows'):
    connection = report['connection']
    issues = []
    if not connection['connected'] or not connection['compatible']:
        issues.append(connection.get('error') or connection['compatibility_reason'])
    if connection.get('bridge_provenance') != 'matching':
        issues.append("Deploy the owned controller, then reload Fruity Commander in FL Script output.")
    missing = sorted(set(REQUIRED_TOOLS) - set(tools))
    if missing:
        issues.append("Launcher is missing owned tools: " + ', '.join(missing))
    rows = {row['capability']: row for row in report['capabilities']}
    owned = rows.get(READINESS_ROW.get(platform, READINESS_ROW['windows']))
    # macOS routes are unqualified, so the report cannot say "available" there yet.
    ready = ('available',) if platform != 'macos' else ('available', 'partial', 'unvalidated')
    if owned is None:
        issues.append("Use scripts/postfader_server.py and restart the MCP connection to load owned capabilities.")
    elif owned['status'] not in ready:
        issues.extend(owned['limitations'] or [f"{owned['capability']} is not ready: {owned['status']}"])
    return list(dict.fromkeys(issues))


def windows_only(report):
    """Owned operations whose only implemented route is the Windows native helper."""
    return sorted(row['capability'] for row in report['capabilities']
                  if row['status'] == 'unavailable' and NO_MAC_ROUTE in row['limitations'])


async def check(options):
    environment = dict(os.environ, FL_BRIDGE_ENABLE_MIDI='1', FL_BRIDGE_ENABLE_WRITES='0')
    if options.user_data:
        environment['FL_STUDIO_USER_DATA_DIR'] = str(options.user_data.resolve())
    if options.midi_port:
        environment['FL_BRIDGE_MIDI_PORT'] = options.midi_port
    server = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).with_name('postfader_server.py').resolve())], env=environment)
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            initialized = await session.initialize()
            catalog = await session.list_tools()
            response = await session.call_tool('fl_get_capabilities', {})
            if response.is_error:
                raise RuntimeError(response.content)
            report = response.structured_content or json.loads(response.content[0].text)
            tools = [tool.name for tool in catalog.tools]
            platform = family()
            issues = assess(report, tools, platform)
            if platform == 'macos':
                issues.extend(mac_host.permission_issues())
            result = {'ready': not issues, 'platform': platform, 'tool_count': len(tools),
                      'server_instructions': initialized.instructions,
                      'issues': issues, 'windows_only': windows_only(report),
                      'capabilities': report,
                      'scope': 'Fresh SDK connection; no musical writes, playback or script startup performed.'}
            if options.output:
                options.output.parent.mkdir(parents=True, exist_ok=True)
                options.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(f"{'Ready' if not issues else 'Setup needs attention'}: {len(tools)} tools discovered.")
            for issue in issues:
                print('- ' + issue)
            if result['windows_only']:
                print('Not yet available on this OS: ' + ', '.join(result['windows_only']))
            print('No project edits performed. This does not refresh an already-running agent connection.')
            return bool(issues)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-data', type=Path, help='FL user-data directory; otherwise use host configuration')
    parser.add_argument('--midi-port', help='Existing virtual MIDI port; otherwise use host configuration')
    parser.add_argument('--output', type=Path, help='Optional detailed JSON report')
    return asyncio.run(check(parser.parse_args()))


if __name__ == '__main__':
    raise SystemExit(main())
