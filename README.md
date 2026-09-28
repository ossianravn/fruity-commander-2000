# Fruity Commander 2000

Fruity Commander is a local MCP product for creating and revising editable music
in FL Studio. It combines PostFader with owned note, sample and native host operations.

The workflow supports:

- Creating and inspecting Piano Roll patterns, then revising selected note ranges.
- Loading installed generators and restoring supported VST2 instrument state.
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

Start with the [Windows setup guide](SETUP.md), then use the
[workflow skill](.agents/skills/fruity-commander/SKILL.md). The
[sample workflow](.agents/skills/fruity-commander/references/samples.md) covers
owned Splice sounds, WAV import and placement.

The [local Codex plugin](SETUP.md#activate-or-update-the-codex-plugin) includes
the supplied [icon](assets/icon.png), workflow skill and installed-runtime MCP
connection. Its Python environment and native helper stay in the installed checkout.

## Current support

The complete host workflow is qualified on Windows with FL Studio Producer Edition
26.1.6 build 5639. Native operations verify the engine binary before execution.
Other FL builds and macOS need further implementation and qualification.

Codex and OpenCode have actual-client editing evidence; Claude has read-only
evidence. Sample import, playback signal and save/reopen have passed live checks.
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
