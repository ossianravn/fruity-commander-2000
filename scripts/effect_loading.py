"""Load an installed mixer effect and verify its instance without resubmission."""

import anyio
from fl_studio_mcp import creative

from scripts.effect_results import EffectCatalogToolResult, EffectLoadingToolResult
from scripts.mcp_results import structured_result
from scripts.native_host import NativeExecutionError, dispatch
from scripts.plugin_catalog import list_effects, validate_preset
from scripts.windows_effects import effect_target
from scripts.windows_project import ProjectReader


def preserved_mixer(before, after, slot_index):
    # Meter samples and selection are observations, not preserved musical state.
    ignored = {"peak_l", "peak_r", "selected", "plugins"}
    old_state = {key: value for key, value in before.items() if key not in ignored}
    new_state = {key: value for key, value in after.items() if key not in ignored}
    old_plugins = {row["slot"]: row for row in before["plugins"]}
    other_plugins = {row["slot"]: row for row in after["plugins"] if row["slot"] != slot_index}
    return old_state == new_state and old_plugins == other_plugins


def add_effect(track_index, slot_index, preset_path, expected_plugin_name, session_fingerprint=None):
    path = validate_preset(preset_path, expected_plugin_name)
    if type(track_index) is not int or track_index < 0:
        raise ValueError("Mixer track index must be a nonnegative integer")
    if type(slot_index) is not int or not 0 <= slot_index < 10:
        raise ValueError("Effect slot index must be an integer from 0 to 9")
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        before = client.call("mixer.track", track=track_index)
        if any(row["slot"] == slot_index for row in before["plugins"]):
            raise ValueError("The requested effect slot is occupied; existing effects are preserved")
        result = {"status": "unknown", "verification": "none", "project_saved": False,
                  "automatic_retry": False, "preset_path": str(path),
                  "expected_plugin_name": expected_plugin_name, "session_fingerprint": session,
                  "track_index": track_index, "slot_index": slot_index}
        with ProjectReader() as reader:
            identity = reader.identity()
            payload = effect_target(reader, track_index, slot_index)
            try:
                result["native"] = dispatch(reader.window, reader.pid, 13, path=str(path),
                                             project=identity["path"] or "", payload=payload, timeout_ms=60000)
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, RuntimeError, ValueError) as error:
                result["message"] = str(error)
            try:
                after = client.call("mixer.track", track=track_index)
                result["observed_effects"] = after["plugins"]
                if reader.identity() != identity or client.ping().get("session_fingerprint") != session:
                    raise ValueError("Project changed during effect loading")
                preserved = preserved_mixer(before, after, slot_index)
                result["mixer_preserved"] = preserved
                effects = [row for row in after["plugins"] if row["slot"] == slot_index]
                effect = effects[0] if len(effects) == 1 else None
                if effect and preserved and effect["name"].casefold() == expected_plugin_name.casefold():
                    return {**result, "status": "loaded", "effect": effect,
                            "verification": "host_plugin_identity_and_mixer_preservation_readback",
                            "message": "The requested effect is loaded; existing effects, track settings and outgoing routes are preserved."}
                result["status"] = "partial" if result.get("native", {}).get("stage", 0) >= 1 else "unknown"
                result.setdefault("message", "FL did not verify the requested effect with preserved mixer state")
            except (OSError, RuntimeError, ValueError, KeyError) as error:
                result["message"] = str(error)
            result["next_action"] = "Inspect this mixer track and its effects before another load; do not resend."
            return result


def register(server):
    @server.mcp.tool(annotations=server.READ_ONLY)
    async def fl_list_installed_effects(query: str = "") -> EffectCatalogToolResult:
        """Find installed mixer-effect .fst entries by name on the qualified Windows host.

        Returns exact paths and plugin metadata; discovery does not establish loading.
        Preserve distinct variants and resolve the intended effect before insertion.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: list_effects(query)))

    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_add_mixer_effect(track_index: int, slot_index: int, preset_path: str,
                                  expected_plugin_name: str,
                                  session_fingerprint: str | None = None) -> EffectLoadingToolResult:
        """Load an installed effect into an empty Windows mixer slot and read its actual identity.

        Track and slot are zero-based: track 0 is Master, slots 0..9 appear as 1..10
        in FL. Use fl_inspect_mixer_track to choose an empty slot and
        fl_list_installed_effects for the exact .fst path and expected plugin name.
        Requires existing write mode. Preserves occupied slots, track settings and
        outgoing routes. Returns the observed effect identity and target_fingerprint.
        Loading does not configure parameters or sends, establish sound, or save.
        Inspect partial/unknown outcomes before continuing; never automatically resend.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: add_effect(track_index, slot_index, preset_path, expected_plugin_name, session_fingerprint)))
