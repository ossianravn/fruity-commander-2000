"""Create and inspect real linked Automation Clips through the owned native helper."""

import struct

import anyio
from fl_studio_mcp import creative

from scripts.automation_contract import AutomationCreation, observed_creation
from scripts.arrangement_results import ArrangementSnapshot, AutomationCreationToolResult
from scripts.mcp_results import structured_result
from scripts.native_host import NativeExecutionError, dispatch
from scripts.windows_arrangement import ArrangementReader


def inspect_arrangement():
    with creative._PIANO_ROLL_DISPATCH_LOCK, ArrangementReader() as reader:
        return reader.snapshot()


def create_automation(request, session_fingerprint=None):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        project = client.call("project.info")
        ppq = project["ppq"]
        if type(ppq) is not int or ppq <= 0:
            raise ValueError("FL did not report a valid project PPQ")
        start, length, points, expected = request.encoded(ppq)
        channels = client.call("channels.list", global_count=True)
        target = next((row for row in channels["channels"] if row["index"] == request.channel_index), None)
        if not target or target.get("target_fingerprint") != request.target_fingerprint:
            raise ValueError("Generator identity changed; inspect channels before creating automation")
        if not target.get("plugin") or request.parameter_index >= target["reported_parameter_count"]:
            raise ValueError("The requested generator parameter is unavailable")
        if request.parameter_index > 0x7fff:
            raise ValueError("Parameter exceeds the qualified channel event encoding")
        with ArrangementReader() as reader:
            before = reader.snapshot()
            objects = reader.channel_objects()
            if len(objects) != channels["channel_count"]:
                raise ValueError("Channel inventory changed before native automation preparation")
            address = objects[request.channel_index]
            source = reader.value(address + 0x9C, "<I")
            event = source + 0x8000 + request.parameter_index
            payload = struct.pack("<QiIiiiiiI", address, request.channel_index, event,
                                  before["arrangement_index"], len(before["clips"]), request.track,
                                  start, length, len(request.points)) + points
            result = {"status": "unknown", "project_saved": False, "automatic_retry": False,
                      "verification": "none", "session_fingerprint": session,
                      "target_event": event, "ppq": ppq}
            try:
                result["native"] = dispatch(reader.window, reader.pid, 4, payload=payload,
                                             project=before["project"]["path"] or "",
                                             expected_channels=len(objects))
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, RuntimeError, ValueError) as error:
                result["message"] = str(error)
            try:
                after = reader.snapshot()
                result["observed"] = after
                if after["project"] != before["project"] or client.ping().get("session_fingerprint") != session:
                    raise ValueError("Project changed during Automation Clip creation")
                actual_target = next((row for row in client.call("channels.list", global_count=True)["channels"]
                                      if row["index"] == request.channel_index), None)
                if not actual_target or actual_target.get("target_fingerprint") != request.target_fingerprint:
                    raise ValueError("Generator identity changed during Automation Clip creation")
                created = observed_creation(before, after, event, expected, request.track, start, length)
                if created and before["arrangement_index"] == after["arrangement_index"]:
                    return {**result, **created, "status": "created", "verification": "native_objects_and_link_readback",
                            "message": "The native Automation Clip, parameter link and Playlist placement were read back."}
                result["status"] = "partial" if result.get("native", {}).get("stage", 0) >= 1 else "unknown"
                result.setdefault("message", "The complete Automation Clip result could not be verified")
            except (OSError, RuntimeError, ValueError, KeyError) as error:
                result["message"] = str(error)
            result["next_action"] = "Inspect the returned native objects before another creation request; do not resend."
            return result


def register(server):
    @server.mcp.tool(annotations=server.READ_ONLY)
    async def fl_inspect_native_arrangement() -> ArrangementSnapshot:
        """Read the current Playlist, native Automation Clip points and actual parameter links.

        Includes stopped or unplaced automation channels. Clip indices may change
        after insertion; source_event identifies the automation source. This is
        host object evidence, not visual, audible or save/reopen verification.
        Includes actual Playlist time selection, which can constrain Song playback;
        use fl_set_playlist_time_selection to change it regardless of editor focus.
        """
        return await anyio.to_thread.run_sync(inspect_arrangement)

    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_create_automation_clip(request: AutomationCreation,
                                        session_fingerprint: str | None = None) -> AutomationCreationToolResult:
        """Create a native Automation Clip linked to a loaded generator parameter and place it.

        Use target_fingerprint from plugins_scan_loaded_plugins with generators
        included, or from fl_add_generator's result. Times are
        quarter notes; points run from zero to length_qn, with normalized 0..1 values
        and linear interpolation. Track is 1-based. Returns actual float-quantized
        points, link and placement. Existing clips/links remain in place, so inspect
        the target's existing automation and choose a non-conflicting placement.
        Requires write mode. Does not save. Never resend a partial/unknown creation.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: create_automation(request, session_fingerprint)))
