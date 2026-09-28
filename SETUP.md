# Local Windows setup

These instructions are for Windows. macOS needs additional host integration and
qualification and is not currently supported.

This installation is qualified on FL Studio Producer Edition 26.1.6 build 5639
and Codex 0.153.2. Other builds are untested.
Automatic score startup, generator loading, configured VST2 state,
editable notes, native linear automation, Playlist placement and saving have live
MCP evidence. Fresh-machine installation and standalone distribution remain unqualified.

## Installation once

Run from your repository checkout. Examples below use
`C:\CodexApp\fruity-commander-2000`; adjust paths to your installation:

```powershell
uv venv .venv --python 3.13
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
uv pip check --python .venv\Scripts\python.exe
```

The pinned PostFader dependency is Apache-2.0. The tested environment resolved
35 packages, including MCP 2.0.1. No separate model API key is needed.

For owned Splice downloads, also install the optional dependencies:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements-splice.txt
uv pip check --python .venv\Scripts\python.exe
```

The combined tested environment has39 compatible packages. Local owned-library
search needs no optional packages. Downloads use running, signed-in Splice Desktop
(qualified5.4.13), its local catalog and its own service; no separate sample project
or account-token extraction is needed. Existing files are decoded and hash-checked.
Actual downloads also compare credits. The plugin exposes no purchase operation.
See the bundled [sample workflow](.agents/skills/fruity-commander/references/samples.md)
for WAV import as a Sampler or Audio Clip, editable sequencing and Playlist placement.
Files stay referenced; automatic tempo fitting and asset collection are not implemented.

Install/run loopMIDI from its [author's site](https://www.tobias-erichsen.de/software/loopmidi.html)
and create one port named `Fruity Commander`. This machine uses loopMIDI
1.0.16.27 and teVirtualMIDI64 1.3.0.43. Keep loopMIDI running while connected;
autostart has not been enabled by this project.

Launch FL Studio once so it creates `Settings/Hardware` in its user-data folder.
Then deploy the controller from this repository root:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.controller_deployment --user-data-dir 'C:\Users\YourName\Documents\Image-Line\FL Studio'
```

This composes the pinned dependency with the owned pattern/editor/naming/save handlers and
stamps their combined source. Do not use the upstream installer for updates: it
would omit these extensions. No installed dependency source is edited.

If FL is already running, open **View → Script output**, select the
**Fruity Commander** tab, and click **Reload script** at the bottom right.
The controller type/file is called Universal Bridge, but the Script output tab
uses the MIDI device name. Restart the MCP connection too when client code changes.
This activates controller updates; score-runtime startup is handled separately below.
Verify `bridge_provenance: matching` from a newly launched client. The installer
retains its existing backup behavior for a replaced controller.

In FL Options → MIDI settings, enable the Fruity Commander input, choose
**Universal Bridge** as controller type, and assign port 0. Assign the paired
output to port 0 as well. The actual endpoint names are `Fruity Commander 0`
and `Fruity Commander 1`; runtime substring selection works. The upstream
setup wizard's identical-name check does not handle these suffixes.
Exit FL normally once after configuration, then reopen it and confirm the
connection. A crash before normal exit lost these preferences during testing.

Build the native helper with installed MSVC x64 C++ tools and a Windows SDK:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_native.ps1
```

This builds the owned DLL and isolated dispatch fixture into `.local/native`.
The server loads it for each native operation, then removes its thread hook;
Windows releases it through FL's message pump. No service or third-party native
SDK is installed. Rebuild after native source updates (current protocol v3).
A packaged, signed distribution remains work.

### MPC Beats setup, when using MPC

Launch MPC Beats once to initialize its settings, then close MPC and FL normally.
Run the approved one-time setup command before reopening FL:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.mpc_setup
```

This enables MPC's global MIDI mapping preference for all its projects. It changes
only that value, preserves the other settings bytes, and reports Already enabled
on repeat. `--settings PATH` selects an existing settings file explicitly. FL/MPC
must be closed because their in-memory settings can overwrite the edit on exit.
Other hosts running MPC must also be closed; the process check recognizes FL,
MPC and FL's plugin bridge. The command does not restart applications.

Project CC assignments still come from the configured instrument state. This is
installation configuration, not a live mapping readback. If mapping is later
disabled inside MPC, this command can restore it for the next launch; it cannot
activate an already-running plugin. See the qualified control check below.

### Prepare the local Codex plugin

After installing the runtime above, generate a bundle from this checkout:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.package_plugin --midi-port 'Fruity Commander'
```

The bundle is `.local/plugins/fruity-commander-2000`. It includes the supplied
icon, workflow skill and `.mcp.json` pointing to this Python environment and owned
launcher. `--user-data-dir` selects a custom FL data folder; otherwise the existing
host resolver uses configured settings or the Windows Documents folder.
`--output-dir` changes the parent directory of the generated bundle.

This is a local integration package: keep the installed checkout, environment and
native helper in place. Copying the bundle into a plugin cache does not relocate
the runtime. Moving the runtime requires regenerating the bundle. Repeated
generation refreshes its generated files without changing active client settings.
It does not install a marketplace entry or activate a second connection. Normal
Codex plugin activation/update now passes on this workstation. The plugin replaces
the manual registration; use the steps below for one configured connection.
The bundle is machine-specific and is not a standalone public distribution.

### Activate or update the Codex plugin

The examples use the personal marketplace `local-personal` and source bundle
`%USERPROFILE%\plugins\fruity-commander-2000`. Use the actual marketplace name
reported by the helper. Codex discovers the personal marketplace automatically;
no `codex plugin marketplace add` is needed.

For the initial entry, use Codex's bundled Plugin Creator helpers. Read an existing
marketplace's name before changing it; on a new profile the scaffold creates the
default personal marketplace. Skip the scaffold when this plugin entry exists:

```powershell
$pluginHelpers = Join-Path $env:USERPROFILE '.codex/skills/.system/plugin-creator/scripts'
if (Test-Path (Join-Path $env:USERPROFILE '.agents/plugins/marketplace.json')) {
    python "$pluginHelpers/read_marketplace_name.py"
}
python "$pluginHelpers/create_basic_plugin.py" fruity-commander-2000 --with-marketplace
```

Then generate the actual bundle into that personal source directory. For updates,
start here; regeneration uses the source version, so apply the cachebuster after it:

```powershell
$pluginHelpers = Join-Path $env:USERPROFILE '.codex/skills/.system/plugin-creator/scripts'
$pluginParent = Join-Path $env:USERPROFILE 'plugins'
$pluginBundle = Join-Path $pluginParent 'fruity-commander-2000'
.\.venv\Scripts\python.exe -B -m scripts.package_plugin --output-dir $pluginParent --midi-port 'Fruity Commander'
python "$pluginHelpers/read_marketplace_name.py"
python "$pluginHelpers/update_plugin_cachebuster.py" $pluginBundle
codex plugin add fruity-commander-2000@local-personal --json
```

Stop if a helper fails; use the marketplace name it prints if it differs. These helper paths
belong to the installed Codex development tooling, not a runtime dependency.
When migrating the manual connection, retain its configuration, then remove it:

```powershell
codex mcp get fruity-commander --json
codex mcp remove fruity-commander
```

Do this migration once, after plugin installation; skip it on later plugin updates.
A same-name manual `enabled=false` entry also suppresses plugin tools, so remove
the old entry instead of leaving it disabled. Start a new Codex chat to load the
updated skill and connection. Ask it to inspect the current FL project without
editing; a connection should discover157 tools and return the actual project state.
Keep the working runtime in place. If migration fails, remove the plugin with
`codex plugin remove fruity-commander-2000@local-personal` and restore the saved
manual settings using the registration example below.

Installation and a subsequent cache update both passed in fresh Codex sessions
outside this repository on the qualified workstation.
This does not qualify a fresh Windows/FL/MIDI installation or refresh an old chat.

### Connect an MCP client

Use these absolute paths and environment settings in the client's stdio MCP setup:

| Setting | Value on this installation |
| --- | --- |
| Command | `C:\CodexApp\fruity-commander-2000\.venv\Scripts\python.exe` |
| Argument | `C:\CodexApp\fruity-commander-2000\scripts\postfader_server.py` |
| `FL_BRIDGE_ENABLE_MIDI` | `1` |
| `FL_BRIDGE_MIDI_PORT` | `Fruity Commander` |
| `FL_STUDIO_USER_DATA_DIR` | `C:\Users\YourName\Documents\Image-Line\FL Studio` |
| `FL_BRIDGE_ENABLE_WRITES` | `0` |

Adjust paths to the actual installation. Use the owned launcher to include all
extensions and workflow guidance. OpenCode2.0.18 now passes note creation,
inspection, revision and save using this entrypoint. Claude has a read-only smoke
test; its musical editing remains unqualified.

For Codex without the plugin, register the launcher while preserving other
connections. Skip this manual registration when using the plugin above:

```powershell
codex mcp add fruity-commander --env 'FL_BRIDGE_ENABLE_MIDI=1' --env 'FL_BRIDGE_MIDI_PORT=Fruity Commander' --env 'FL_STUDIO_USER_DATA_DIR=C:\Users\YourName\Documents\Image-Line\FL Studio' --env 'FL_BRIDGE_ENABLE_WRITES=0' -- 'C:\CodexApp\fruity-commander-2000\.venv\Scripts\python.exe' 'C:\CodexApp\fruity-commander-2000\scripts\postfader_server.py'
codex mcp get fruity-commander
```

These registration commands passed locally. Fresh SDK and actual Codex clients
discover 157 tools. An already-running chat can retain an old catalog or a closed
transport; restart its MCP connection after launcher updates. This is separate
from reloading FL's controller after controller-source updates.

Find candidate names with the client's native lookup. For focused metadata, or
when a client presents a contract as `unknown`, use `fl_get_tool_contract` with
the exact tool name and `schema_section` (`input` or `output`). The root returns
the original purpose, effects annotations and schema without expanding its entire
definition graph. Follow needed reference pointers with `json_pointer`; child
fragments omit repeated tool metadata. Full native definitions remain available.
Reuse retrieved metadata and batch independent lookups. This reads server metadata
and requires no FL action. The repository skill carries the discovery workflow.

### OpenCode

Save this as `.local/opencode.json`, adjusting the installation paths:

```json
{
  "mcp": {
    "fruity-commander": {
      "type": "local",
      "command": [
        "C:/CodexApp/fruity-commander-2000/.venv/Scripts/python.exe",
        "C:/CodexApp/fruity-commander-2000/scripts/postfader_server.py"
      ],
      "enabled": true,
      "environment": {
        "FL_BRIDGE_ENABLE_MIDI": "1",
        "FL_BRIDGE_MIDI_PORT": "Fruity Commander",
        "FL_STUDIO_USER_DATA_DIR": "C:/Users/YourName/Documents/Image-Line/FL Studio",
        "FL_BRIDGE_ENABLE_WRITES": "0"
      }
    }
  }
}
```

Run `opencode auth login` once to connect your chosen model provider. In the
terminal used to start OpenCode, set `OPENCODE_CONFIG` to that file's absolute
path. Launch `opencode --standalone` for an interactive session, or use the
qualified CLI form below for a read-only check:

```powershell
$env:OPENCODE_CONFIG = 'C:/CodexApp/fruity-commander-2000/.local/opencode.json'
opencode run --standalone --format json 'Use Fruity Commander MCP to report the current FL project and whether playback is stopped. Do not edit.'
```

Config sources merge with existing settings. The private server follows the CLI
session lifetime. No permission-bypass flag is needed.

OpenCode2.0.18/DeepSeek Flash passed the actual note workflow. Initial MCP-list
queries can be empty while configuration and connections start asynchronously.
The skill uses OpenCode's server-specific resource listing to await readiness,
then refreshes discovery in the next execute call. An actual cold resume passes.
This lists metadata; it does not prove FL is reachable. Transport reads accept
optional `wait_seconds` for spaced playback observations. Immediate reads remain
the default. Inspect uncertain writes before any resend. See the
[OpenCode MCP configuration reference](https://opencode.ai/docs/mcp-servers/).

### Check the installation

With FL and loopMIDI running, and no competing diagnostic connection:

```powershell
.\.venv\Scripts\python.exe -X utf8 -B scripts/check_setup.py --user-data 'C:\Users\YourName\Documents\Image-Line\FL Studio' --midi-port 'Fruity Commander'
```

This opens a fresh standard MCP connection and checks controller provenance,
required owned tools, qualified native access and helper availability. It reports
specific setup issues and exits nonzero when attention is needed. It does not edit
the project, start playback or refresh another client's connection. A ready report
establishes these checks, not a full musical or save/reopen test. Use `--output`
with a JSON path for the detailed capability report and initialization guidance.

## Session startup

1. Start loopMIDI and FL; open the intended project.
2. Let the MCP client call `fl_get_project_summary` and `fl_list_channels` to establish
   the real host and targets. Keep one MIDI-owning MCP client at a time.
3. For requested edits, use upstream `fl_set_write_mode(enabled=true,
   confirm_user_present=true)` with the existing user authorization. This changes
   the FL bridge session; restarting only the MCP process does not necessarily
   reset a write mode already enabled in FL.

### Automatic score startup

Owned creation, range, and inspection tools automatically start their score runtime
in a fresh MCP process, including when FL has never selected a script in that process.
`piano_roll_start_session(channel_index, pattern_number)` exposes startup separately
and works with musical writes disabled. It prepares/focuses the editor, initializes
FL's script inventory, resolves the owned path, runs FL's script callback on its main
thread, and requires a signed host receipt.
No user-run confirmation flag is needed. Inspecting a score still uses upstream
editor-selection write mode. FL may add undo history and dirty state when a script
runs, even when its notes are unchanged.

Cold startup and unchanged note/marker readback passed through standard MCP.
Use the owned creation/range/inspection tools: legacy upstream tools still retain
their shortcut/manual-bootstrap contracts and were not qualified by this proof.
`piano_roll_prepare_target` still exposes target/focus preparation independently.

Native project-path and last-script reads are qualified for the exact Windows
26.1.6.5639 engine binary identified by `scripts/windows_project.py`. These reads remain external;
score execution now uses the approved in-process helper. An unqualified engine
reports a capability error. Broader build/platform qualification remains work.

## Ordinary editing

Use the [workflow skill](.agents/skills/fruity-commander/SKILL.md) for targeting,
creation, range revisions, VST control, and capability status.
Rebuild the native helper after source updates; its current mapping protocol is v3.
`fl_list_installed_generators(query)` returns FL preset paths and available plugin
metadata, preserving variants. `fl_add_generator(preset_path, expected_plugin_name)`
loads a chosen `.fst` into a new channel and verifies the loaded identity. Loading
does not initialize a plugin's internal instrument or select a musical preset.

`fl_inspect_native_arrangement` reads native points, controller links and Playlist
records. `fl_create_automation_clip(request)` creates a linked generator-parameter
clip and places it. Its explicit input uses a generator target fingerprint, parameter
index, 1-based track, quarter-note start/length and linear normalized-value points.
Get the fingerprint through `plugins_scan_loaded_plugins` with generators included.
Inspect existing target automation first. Float-quantized host points and actual
placement are returned; partial or unknown results must be inspected before another
creation. These tools do not save. `fl_replace_automation_points` revises an existing
source using its complete observed `expected_points`; all Playlist copies share
that source. Linear same-extent revision passes undo/redo and save/reopen checks.
Other interpolation shapes, extent changes and deletion remain work.

Use `fl_place_pattern_clip(request)` to arrange existing notes. Supply the actual
`pattern_number`, full `expected_name`, 1-based `track`, and quarter-note
`start_qn`/`length_qn`. The source window begins at zero. Placement preserves
other clips and reports native readback; it does not save.

To extract a saved generator setup, `fl_extract_generator_preset(project_path, channel_index,
template_path, destination_path)` extracts that saved channel into a new `.fst`.
Use an installed generator database preset as the envelope template. Unsaved
changes are not included; external assets remain referenced, not packaged. Load
the generator with `fl_add_generator`. Its identity readback does not establish
internal setup: the MPC test loaded a blank instance. The new
`fl_load_generator_state(channel_index, target_fingerprint, preset_path)` dispatches
the embedded VST2 bank through the existing Fruity Wrapper instance. It converts
the qualified FL envelope to FXB internally. Its acceptance receipt explicitly
does not verify musical setup; the MPC workflow has separate live proof. Verify
internal state, isolated instrument audio, automation and save/reopen separately.
On this installation additional MPC instances remain uninitialized while one is
already running. The fresh-instrument proof uses one MPC instance in a separate
project. This is an instrument limitation, not a product-wide instance limit.
VST3, non-bank formats and arbitrary internal program selection remain work.

`fl_get_project_file` reads the actual current path and saved-file snapshot;
`fl_save_project` saves an existing named FLP and observes its completed file rewrite.
`fl_save_project_as(destination_path)` assigns an explicit absolute `.flp` path in
an existing directory and verifies native path adoption plus completed-file writing.
It replaces an existing FLP at that explicitly requested destination. Both save tools
require existing write mode. Save As uses the owned native helper's direct FLP writer
and path adoption, independent of editor focus and first-save dialogs. Named and
untitled sources, explicit overwrites and save/reopen pass on this FL build. Build
the current helper after updating the runtime; other builds need qualification.
No agent desktop tool or user dialog handoff is required.
File-write verification does not establish save/reopen or verify every saved field.
The product goal is to own these steps without agent Computer Use or recurring
user handoffs supplying missing implementation.

For MPC, both the global mapping preference and the project-specific MIDI Learn
assignment must be active. The qualified example maps channel1/AbsCC74 to
Plugin001 LPF Cutoff with FL owning the notes. Preset/bank acceptance and a disk
preference do not establish live control; verify the actual target response.
MPC writes its global preference on normal exit, so the disk file can be stale
while FL is running. Live activation after an in-session toggle remains unavailable.
MPC presets can reference shared external project data. Saving may rewrite those
assets; copying an FLP does not isolate them.

## Diagnostics

Stop any competing diagnostic/client connection before starting another.
For a persistent SDK MCP session:

```powershell
.\.venv\Scripts\python.exe -u scripts\mcp_session.py --midi-port 'Fruity Commander' --user-data 'C:\Users\YourName\Documents\Image-Line\FL Studio' --log .local\proof\mcp-session.jsonl
```

Send one JSON line at a time, for example:

```json
{"action":"call","name":"fl_get_project_summary","arguments":{}}
{"action":"schema","name":"piano_roll_replace_range"}
{"action":"quit"}
```

A read-only Codex client diagnostic, with the path adjusted to your CLI installation:

```powershell
.\.venv\Scripts\python.exe -B -u scripts\codex_connection_probe.py --codex-js 'C:\Users\YourName\AppData\Roaming\npm\node_modules\@openai\codex\bin\codex.js'
```

It starts the installed app-server, checks skill/tool discovery, and makes one
read in an ephemeral context. It creates no persisted chat and starts no model
turn. Evidence goes to ignored `.local/proof/codex-connection.json`.
For authorized qualification, `--commands PATH` executes ordered JSONL entries
of the form `{"tool":"fl_get_project_file","arguments":{}}`; `--evidence PATH`
keeps a separate result file. Calls are recorded immediately. Tool errors stop
execution without retries; inspect semantic partial/unknown results before
issuing dependent writes. This exercises Codex's MCP client, not a model turn.

The probe follows the installed CLI's generated protocol schemas and the
[official app-server protocol](https://learn.chatgpt.com/docs/app-server).

Playlist playback range: `fl_inspect_native_arrangement` reports the actual
Playlist time selection. `fl_set_playlist_time_selection(start_qn, end_qn)` sets
it; omit both endpoints to clear it. A shorter selection can loop before newly
placed clips. The generic upstream selection getter follows the focused editor
on this FL build and can read the Piano Roll instead.
