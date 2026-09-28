"""Load configured FL presets into an existing wrapped generator instance."""

import struct
import tempfile
from pathlib import Path
import anyio
from fl_studio_mcp import creative

from scripts.vst_state import vst2_bank
from scripts.native_host import NativeExecutionError, dispatch
from scripts.windows_arrangement import ArrangementReader
from scripts.plugin_results import GeneratorStateToolResult
from scripts.mcp_results import structured_result


def load_state(channel_index, target_fingerprint, preset_path, session_fingerprint=None):
    path = Path(preset_path)
    if not path.is_absolute() or path.suffix.lower() != ".fst":
        raise ValueError("Provide an absolute configured FL .fst preset path")
    bank = vst2_bank(path.read_bytes())
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        channels = client.call("channels.list", global_count=True)["channels"]
        before = next((c for c in channels if c["index"] == channel_index), None)
        if not before or before.get("target_fingerprint") != target_fingerprint:
            raise ValueError("Generator identity changed; inspect the intended instance before loading state")
        with ArrangementReader() as reader:
            project = reader.identity()
            channel = reader.channel_objects()[channel_index]
            instance = reader.value(reader.value(channel + 0x38) + 0x2C)
            result = {"status": "unknown", "project_saved": False, "automatic_retry": False,
                      "channel_index": channel_index, "preset_path": str(path),
                      "musical_setup_verified": False}
            with tempfile.NamedTemporaryFile(prefix="fruity-commander-state-", suffix=".fxb", delete=False) as staged:
                staged.write(bank)
            staged_path = Path(staged.name)
            result["staged_state_path"] = str(staged_path)
            try:
                result["native"] = dispatch(reader.window, reader.pid, 7, path=str(staged_path),
                    project=project["path"] or "", payload=struct.pack("<QQii", channel, instance, channel_index, 0),
                    timeout_ms=60000)
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, ValueError, RuntimeError) as error:
                result["message"] = str(error)
            try:
                observed = client.call("channels.list", global_count=True)["channels"]
                result["channel"] = next((c for c in observed if c["index"] == channel_index), None)
                same_instance = reader.value(reader.value(channel + 0x38) + 0x2C) == instance
                if (result.get("native", {}).get("native_callback_completed") and same_instance
                        and channels == observed and reader.identity() == project
                        and client.ping().get("session_fingerprint") == session):
                    result.update(status="loaded", verification="wrapper_accepted_file_and_instance_retained",
                                  message="Wrapper accepted the preset in the same instance. Verify sound and internal setup separately.")
                else:
                    result.setdefault("message", "Preset load not fully verified; inspect state before another request")
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                result["message"] = "State readback failed; inspect before another request: " + str(error)
            if result.get("native", {}).get("native_callback_completed"):
                try:
                    staged_path.unlink()
                    result.pop("staged_state_path")
                except OSError as error:
                    result["staging_cleanup_error"] = str(error)
            return result


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_load_generator_state(channel_index: int, target_fingerprint: str,
            preset_path: str, session_fingerprint: str | None = None) -> GeneratorStateToolResult:
        """Restore a configured .fst's VST2 bank in the existing Fruity Wrapper.

        Requires write mode. Use target_fingerprint from fl_add_generator or
        plugins_scan_loaded_plugins(include_channel_generators=true).
        Retains the current instance, channel identity and routing. Acceptance does
        not prove the internal instrument, mapping or audio: inspect and audition.
        Converts the qualified FL bank envelope to FXB without changing plugin
        bytes. VST3 and other state formats need separate qualification. Plugin
        assets remain referenced. Does not save; inspect unknown outcomes. A
        staging file is retained on unknown native completion, never retried.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: load_state(channel_index, target_fingerprint, preset_path, session_fingerprint)))
