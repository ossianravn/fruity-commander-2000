"""Run pinned PostFader with qualified, narrowly scoped compatibility fixes."""

import sys
from pathlib import Path

# Support both direct execution by Codex and module imports in contract tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def prepare_server():
    from scripts.startup_schemas import reuse_startup_schemas

    with reuse_startup_schemas():
        return _prepare_server()


def _prepare_server():
    from scripts.controller_deployment import configure
    from scripts.pattern_inventory import install, register as register_inventory
    from scripts.editor_contract import install as install_editor, register as register_editor
    from scripts.pattern_identity import install as install_identity, register as register_identity

    configure()
    install()
    install_editor()
    install_identity()
    from scripts.capabilities import install as install_capabilities
    install_capabilities()
    from fl_studio_mcp import creative, piano_roll
    from fl_studio_mcp.piano_roll import (
        PianoRollNoteSnapshot,
        PianoRollObservedNote,
    )

    # MCP 2 generates output schemas in validation mode. These output-only
    # notes serialize computed beat fields, which must be in their schema.
    # Input validation and extra-field rejection remain enabled.
    PianoRollObservedNote.model_config["json_schema_mode_override"] = "serialization"
    PianoRollObservedNote.model_rebuild(force=True)
    PianoRollNoteSnapshot.model_rebuild(force=True)

    if sys.platform == "win32":
        from scripts.windows_score import trigger_owned_score_script

        creative._trigger_piano_roll_shortcut = trigger_owned_score_script
        piano_roll._trigger_piano_roll_shortcut = trigger_owned_score_script
    elif sys.platform == "darwin":
        # Target FL by bundle identifier and verify it is frontmost before the key.
        from scripts.mac_host import trigger_run_last_script

        creative._trigger_piano_roll_shortcut = trigger_run_last_script
        piano_roll._trigger_piano_roll_shortcut = trigger_run_last_script

    # Register tools only after rebuilding their return model.
    from fl_studio_mcp import mcp_server
    from scripts.host_platform import family
    from scripts.server_guidance import instructions
    mcp_server.mcp._lowlevel_server.instructions = instructions(family())

    from scripts.range_tool import register
    from scripts.pattern_tool import register as register_patterns
    from scripts.project_save import register as register_save
    from scripts.score_startup import register as register_startup
    from scripts.project_save_as import register as register_save_as
    from scripts.plugin_loading import register as register_loading
    from scripts.automation_tool import register as register_automation
    from scripts.playlist_tool import register as register_playlist
    from scripts.generator_presets import register as register_presets
    from scripts.playlist_selection import register as register_selection
    from scripts.plugin_state import register as register_state
    from scripts.automation_edit import register as register_automation_edit
    from scripts.tool_contracts import register as register_contracts
    from scripts.transport_observation import register as register_transport
    from scripts.playlist_inventory import register as register_playlist_inventory
    from scripts.sample_import import register as register_samples
    from scripts.audio_clip_tool import register as register_audio_clip
    from scripts.splice_tools import register as register_splice
    from scripts.effect_loading import register as register_effects

    register(mcp_server)
    register_patterns(mcp_server)
    register_inventory(mcp_server)
    register_editor(mcp_server)
    register_identity(mcp_server)
    register_save(mcp_server)
    register_startup(mcp_server)
    register_save_as(mcp_server)
    register_loading(mcp_server)
    register_automation(mcp_server)
    register_playlist(mcp_server)
    register_presets(mcp_server)
    register_selection(mcp_server)
    register_state(mcp_server)
    register_automation_edit(mcp_server)
    register_contracts(mcp_server)
    register_transport(mcp_server)
    register_playlist_inventory(mcp_server)
    register_samples(mcp_server)
    register_audio_clip(mcp_server)
    register_splice(mcp_server)
    register_effects(mcp_server)

    return mcp_server


if __name__ == "__main__":
    raise SystemExit(prepare_server().main())
