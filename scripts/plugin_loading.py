"""Add an installed generator through FL, retaining partial and observed identity."""

from pathlib import Path

import anyio
from fl_studio_mcp import creative

from scripts.native_host import NativeExecutionError, dispatch
from scripts.plugin_catalog import list_generators
from scripts.windows_project import ProjectReader
from scripts.plugin_results import GeneratorCatalogToolResult, GeneratorLoadingToolResult
from scripts.mcp_results import structured_result


def validate_preset(preset_path, expected_plugin_name):
    path = Path(preset_path)
    if not path.is_absolute() or path.suffix.lower() != ".fst" or not path.is_file():
        raise ValueError("Provide an existing absolute .fst generator preset path")
    with path.open("rb") as stream:
        if stream.read(4) != b"FLhd":
            raise ValueError("The requested file is not an FL preset")
    if not expected_plugin_name.strip():
        raise ValueError("The expected loaded plugin name is required for identity verification")
    return path.resolve()


def add_generator(preset_path, expected_plugin_name, session_fingerprint=None):
    path = validate_preset(preset_path, expected_plugin_name)
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        before = client.call("channels.list", global_count=True)
        count = before["channel_count"]
        result = {"status": "unknown", "project_saved": False, "automatic_retry": False,
                  "verification": "none", "preset_path": str(path),
                  "expected_plugin_name": expected_plugin_name, "session_fingerprint": session}
        with ProjectReader() as reader:
            identity = reader.identity()
            try:
                result["native"] = dispatch(reader.window, reader.pid, 3, path=str(path),
                                             project=identity["path"] or "",
                                             expected_channels=count, timeout_ms=60000)
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, RuntimeError, ValueError) as error:
                result["message"] = str(error)
            # Inspect once even after lost acknowledgement: a plugin may have loaded.
            # Never submit insertion again or silently delete a partially created channel.
            try:
                after = client.call("channels.list", global_count=True)
                result["observed_channel_count"] = after["channel_count"]
                result["new_channels"] = after["channels"][count:]
                if reader.identity() != identity or client.ping().get("session_fingerprint") != session:
                    raise ValueError("Project changed during generator loading")
                unchanged = (after["channel_count"] == count + 1 and
                             [row["channel_fingerprint"] for row in before["channels"]] ==
                             [row["channel_fingerprint"] for row in after["channels"][:count]])
                channel = next((row for row in after["channels"] if row["index"] == count), None)
                if unchanged and channel and channel["plugin"].casefold() == expected_plugin_name.casefold():
                    return {**result, "status": "loaded", "verification": "host_plugin_identity_readback",
                            "channel_index": count, "channel": channel,
                            "message": "The requested generator is loaded in the new channel."}
                native = result.get("native", {})
                result["status"] = "partial" if native.get("stage", 0) >= 1 else "unknown"
                result.setdefault("message", "FL did not verify the expected newly loaded generator")
            except (OSError, RuntimeError, ValueError, KeyError) as error:
                result["message"] = str(error)
            result["next_action"] = "Inspect the returned channel inventory and plugin state before another load; do not resend."
            return result


def register(server):
    @server.mcp.tool(annotations=server.READ_ONLY)
    async def fl_list_installed_generators(query: str = "") -> GeneratorCatalogToolResult:
        """Find FL generator preset entries by name; includes paths and available plugin metadata.

        An entry establishes discovery, not successful loading or authorization.
        Preserve variants and exact paths; resolve ambiguous matches before loading.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: list_generators(query)))

    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_add_generator(preset_path: str, expected_plugin_name: str,
                               session_fingerprint: str | None = None) -> GeneratorLoadingToolResult:
        """Load an installed generator's .fst into a new Channel Rack channel.

        Requires existing write mode. Use an explicit path from discovery and the
        expected plugin identity; verifies the loaded plugin through FL readback.
        Insertion does not verify internal setup. A configured VST2 bank may need
        fl_load_generator_state using the returned target_fingerprint; a blank
        database preset can leave the instrument unconfigured.
        Does not replace a channel, create notes, place
        clips, or save. Partial/unknown results require inspection.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: add_generator(preset_path, expected_plugin_name, session_fingerprint)))
