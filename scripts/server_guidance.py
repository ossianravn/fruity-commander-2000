"""Shared MCP guidance; operation-specific contracts belong on their tools.

Codex repeats server instructions in each deferred tool description. Keep this
shared context compact without relying on a client-specific skill for correctness.
"""

INSTRUCTIONS = """\
Fruity Commander edits FL Studio through MCP. Read fl_get_capabilities for current
owned operation routes, availability and qualified engine. Inspect the project and
intended targets before editing. Tool descriptions supply units, effects and setup.
Enable existing write mode for authorized edits, respecting client permissions;
a clear edit request needs no additional product approval. Inspect partial/unknown
outcomes before further writes; never automatically resend a mutation.

Edits do not save automatically. Save completion and reopening are separate evidence.
Use native clips for requested Automation Clips, not streamed knobs or pattern events.
Use Song playback for placed notes and automation. Meters establish signal, not sound
quality. Saved-project rendering uses the saved FLP, excluding unsaved edits.
Plugin parameter indices differ from MIDI controller numbers; physical units require
a verified mapping. Instrument identity alone does not verify internal setup or sound.

Owned sounds: splice_search_owned and splice_download_owned acquire local WAVs.
fl_import_sample loads a Sampler or Audio Clip; fl_inspect_sample reads its source.
Sequence Samplers with notes; place timeline audio with fl_place_audio_clip.
Download, import, playback and save are separate evidence. External files stay referenced.

Production Run/readiness tools describe their own pipeline, not orchestration of the
owned native workflow. Report completed changes separately from remaining steps.
"""

MACOS = """
macOS preview: owned automation clips, Playlist placement, sample import, preset
loading and save tools are Windows-only; capabilities mark them unavailable. Say so
plainly and ask the user to save with Cmd+S. Note tools need the user to run
Postfader Apply in the Piano Roll once per FL launch; relay that step and wait.
plugins_list_available and plugins_load add named instruments and effects.
"""


def instructions(platform):
    return INSTRUCTIONS + MACOS if platform == "macos" else INSTRUCTIONS
