"""Control the Playlist time selection independently of the focused score editor."""

import struct
import anyio
from fl_studio_mcp import creative

from scripts.native_host import NativeExecutionError, dispatch
from scripts.range_runtime import ticks
from scripts.windows_arrangement import ArrangementReader
from scripts.arrangement_results import PlaylistSelectionToolResult
from scripts.mcp_results import structured_result


def select_time(start_qn=None, end_qn=None, session_fingerprint=None):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        ppq = client.call("project.info")["ppq"]
        if type(ppq) is not int or ppq <= 0:
            raise ValueError("FL did not return valid PPQ")
        if start_qn is None and end_qn is None:
            start, end = -1, -1
        elif start_qn is None or end_qn is None:
            raise ValueError("Provide both time endpoints, or omit both to clear the selection")
        else:
            start, end = ticks(start_qn, ppq), ticks(end_qn, ppq)
            if not 0 <= start < end <= 0x7fffffff:
                raise ValueError("Playlist selection requires ordered, representable nonnegative ticks")
        with ArrangementReader() as reader:
            before, project = reader.time_selection(), reader.identity()
            result = {"status": "unknown", "before": before, "ppq": ppq,
                      "project_saved": False, "automatic_retry": False}
            try:
                result["native"] = dispatch(reader.window, reader.pid, 6, project=project["path"] or "",
                    payload=struct.pack("<Qii", before["owner"], start, end))
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, ValueError, RuntimeError) as error:
                result["message"] = str(error)
            try:
                after = reader.time_selection()
                result["after"] = after
                matched = (after["start_tick"], after["end_tick"]) == (start, end)
                if (matched and after["owner"] == before["owner"] and reader.identity() == project
                        and client.ping().get("session_fingerprint") == session):
                    result.update(status="selected" if end != -1 else "cleared",
                                  verification="native_playlist_selection_readback")
                else:
                    result["message"] = "Playlist time selection did not match; inspect before another request"
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                result["message"] = "Selection readback failed; inspect before another request: " + str(error)
            return result


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_set_playlist_time_selection(start_qn: float | None = None,
            end_qn: float | None = None, session_fingerprint: str | None = None) -> PlaylistSelectionToolResult:
        """Select a Playlist time range in quarter notes, or omit both endpoints to clear it.

        A range can constrain Song playback even when clips extend beyond it.
        Targets the Playlist explicitly regardless of Piano Roll focus. Requires
        write mode; does not start playback, alter clips or save the project.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: select_time(start_qn, end_qn, session_fingerprint)))
