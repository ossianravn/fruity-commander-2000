# Fruity Commander 2000

Fruity Commander is a local MCP product for creating and revising editable music
in FL Studio. It combines PostFader with owned note, sample and native host operations.

The workflow supports:

- Creating and inspecting Piano Roll patterns, then revising selected note ranges.
- Loading installed generators and restoring supported VST2 instrument state.
- Loading installed mixer effects into empty slots, configuring their controls
  and routing instruments through them.
- Creating linked native Automation Clips and revising linear curves.
- Placing note patterns and Audio Clips in the Playlist.
- Searching and downloading owned Splice sounds, then importing WAVs as Samplers
  or Audio Clips.
- Controlling playback and saving projects, including Save As to an explicit path.

Required musical operations run through MCP. The bundled workflow skill explains
target selection, tool discovery and how to distinguish an edit from playback or
save evidence. Sample files remain referenced at their existing locations;
automatic tempo fitting and asset collection are not implemented.

## Setup

Start with the [Windows setup guide](SETUP.md) or the
[macOS preview setup](SETUP-macOS.md), then use the
[workflow skill](.agents/skills/fruity-commander/SKILL.md). The
[sample workflow](.agents/skills/fruity-commander/references/samples.md) covers
owned Splice sounds, WAV import and placement. The
[effects workflow](.agents/skills/fruity-commander/references/effects.md) covers
Windows effect loading, parameter discovery and sends.

Install the [Codex plugin](SETUP.md#activate-or-update-the-codex-plugin) or the
[Claude Code desktop plugin](SETUP.md#install-the-plugin-in-claude-code) after
runtime setup. Both use the same workflow and local MCP server. The repository
contains separate [Codex](.codex-plugin/plugin.json) and
[Claude](.claude-plugin/plugin.json) manifests; the shared packager adds the
workflow, [icon](assets/icon.png) and connection paths for your installation.
Each user generates their own bundle. Its Python environment and native helper
stay in the installed checkout.

## Current support

The complete host workflow is qualified on Windows with FL Studio Producer Edition
26.1.6 build 5639. Native operations verify the engine binary before execution.
Other FL builds need further qualification.

macOS is a preview that has not yet run on a real Mac. Connection, mixing,
playback, plugin parameters, editable notes (one FL click per launch) and Add-menu
instrument/effect loading have Mac routes. Automation Clips, Playlist placement,
sample import, preset/state loading and saving are Windows-only for now; see the
[macOS setup](SETUP-macOS.md) for what to test and report.

Codex and OpenCode have actual-client editing evidence; Claude has read-only
evidence. Sample import and Reeverb 2/Delay 3 insertion, parameter changes, sends,
playback signal and save/reopen have passed live checks.
Meters establish signal, not listening-based musical quality. Fresh-machine
installation and standalone distribution remain unqualified.

## Development

Install dependencies and build the native helper as described in [setup](SETUP.md).
Run the automated tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Maintained code files stay within 300 physical lines. PostFader remains an external
Apache-2.0 dependency pinned by revision in `requirements.txt`.
