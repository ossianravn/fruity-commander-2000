"""Place a named note pattern in the current Playlist using FL's native collection."""

import struct

import anyio
from pydantic import BaseModel, ConfigDict, Field
from fl_studio_mcp import creative

from scripts.native_host import NativeExecutionError, dispatch
from scripts.range_runtime import ticks
from scripts.windows_arrangement import ArrangementReader
from scripts.arrangement_results import PatternPlacementToolResult
from scripts.mcp_results import structured_result


class PatternPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    pattern_number: int = Field(ge=1)
    expected_name: str
    track: int = Field(ge=1, le=500)
    start_qn: float = Field(ge=0)
    length_qn: float = Field(gt=0)


def find_pattern(client, request):
    inventory = client.call("patterns.list")
    pattern = next((p for p in inventory["patterns"] if p["pattern"] == request.pattern_number), None)
    if not pattern or pattern["name"] != request.expected_name:
        raise ValueError("Pattern identity changed; inspect patterns before placing the clip")
    return pattern


def inserted_clip(before, after, expected):
    remaining = [{k: v for k, v in c.items() if k != "index"} for c in after["clips"]]
    for clip in before["clips"]:
        content = {k: v for k, v in clip.items() if k != "index"}
        if content not in remaining:
            return None
        remaining.remove(content)
    if len(remaining) != 1 or any(remaining[0].get(k) != v for k, v in expected.items()):
        return None
    return next(c for c in after["clips"] if {k: v for k, v in c.items() if k != "index"} == remaining[0])


def place_pattern(request, session_fingerprint=None):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        pattern = find_pattern(client, request)
        ppq = client.call("project.info")["ppq"]
        if type(ppq) is not int or ppq <= 0:
            raise ValueError("FL did not return a valid PPQ")
        start, end = ticks(request.start_qn, ppq), ticks(request.start_qn + request.length_qn, ppq)
        if not 0 <= start < end <= 0x7fffffff:
            raise ValueError("Placement is outside FL's signed tick representation")
        with ArrangementReader() as reader:
            before = reader.snapshot()
            pointer = reader.value(reader.base + 0x1543CE0 + request.pattern_number * 0xC0)
            payload = struct.pack("<Qiiiiii", pointer, request.pattern_number, before["arrangement_index"],
                                  len(before["clips"]), request.track, start, end - start)
            result = {"status": "unknown", "verification": "none", "project_saved": False,
                      "automatic_retry": False, "pattern": pattern, "ppq": ppq,
                      "session_fingerprint": session}
            try:
                result["native"] = dispatch(reader.window, reader.pid, 5,
                    project=before["project"]["path"] or "", payload=payload)
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (ValueError, OSError, RuntimeError) as error:
                result["message"] = str(error)
            try:
                after = reader.snapshot()
                result["observed"] = after
                if before["project"] != after["project"] or client.ping().get("session_fingerprint") != session:
                    raise ValueError("Project changed during pattern placement")
                find_pattern(client, request)
                expected = {"source_id": 0x50005000 + (request.pattern_number << 16),
                            "start_tick": start, "length_tick": end - start,
                            "track": request.track, "muted": False}
                clip = inserted_clip(before, after, expected)
                unchanged = all(before[k] == after[k] for k in ("arrangement_index", "automation", "links"))
                if clip and unchanged:
                    return {**result, "status": "placed", "verification": "native_playlist_readback", "clip": clip}
                result["status"] = "partial" if result.get("native", {}).get("stage", 0) else "unknown"
                result.setdefault("message", "The requested placement was not fully verified")
            except (ValueError, OSError, RuntimeError, KeyError) as error:
                result["message"] = str(error)
            result["next_action"] = "Inspect the Playlist before another placement request; do not resend."
            return result


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_place_pattern_clip(request: PatternPlacement,
                                    session_fingerprint: str | None = None) -> PatternPlacementToolResult:
        """Place an existing named pattern on a 1-based Playlist track at quarter-note timing.

        Retains the pattern's notes and other clips. Explicit length sets the source
        window beginning at zero; FL determines playback if it exceeds the source.
        Checks expected_name from fl_list_patterns and reads the resulting placement.
        Requires write mode. Does not save or select Song playback automatically.
        Inspect partial/unknown outcomes; never retry a placement automatically.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: place_pattern(request, session_fingerprint)))
