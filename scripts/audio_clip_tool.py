"""Place an imported Audio Clip source using the existing native Playlist boundary."""

import struct
import anyio
from pydantic import BaseModel, ConfigDict, Field
from fl_studio_mcp import creative

from scripts.mcp_results import structured_result
from scripts.native_host import NativeExecutionError, dispatch
from scripts.playlist_tool import inserted_clip
from scripts.project_save_as import same_path
from scripts.range_runtime import ticks
from scripts.sample_results import AudioPlacementToolResult
from scripts.windows_samples import SampleReader


class AudioPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    channel_index: int = Field(ge=0)
    expected_source_path: str
    track: int = Field(ge=1, le=500)
    start_qn: float = Field(ge=0)
    length_qn: float = Field(gt=0)


def place_audio(request, session_fingerprint=None):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        ppq = client.call("project.info")["ppq"]
        if type(ppq) is not int or ppq <= 0:
            raise ValueError("FL did not return a valid PPQ")
        start, end = ticks(request.start_qn, ppq), ticks(request.start_qn + request.length_qn, ppq)
        if not 0 <= start < end <= 0x7fffffff:
            raise ValueError("Placement is outside FL's signed tick representation")
        with SampleReader() as reader:
            before, source = reader.snapshot(), reader.source(request.channel_index)
            if source["kind"] != "audio_clip" or not same_path(source["resolved_path"], request.expected_source_path):
                raise ValueError("Inspect the intended Audio Clip channel and its source path before placement")
            pointer = reader.channel_objects()[request.channel_index]
            payload = struct.pack("<QIIiiiii4x", pointer, request.channel_index, source["source_event"],
                before["arrangement_index"], len(before["clips"]), request.track, start, end - start)
            result = {"status": "unknown", "verification": "none", "source": source, "ppq": ppq,
                      "session_fingerprint": session, "project_saved": False, "automatic_retry": False}
            try:
                result["native"] = dispatch(reader.window, reader.pid, 12,
                    project=before["project"]["path"] or "", payload=payload)
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, ValueError, RuntimeError) as error:
                result["message"] = str(error)
            try:
                after = reader.snapshot()
                result["observed"] = after
                if (before["project"] != after["project"] or reader.source(request.channel_index) != source
                        or client.ping().get("session_fingerprint") != session):
                    raise ValueError("Project or Audio Clip source changed during placement")
                expected = {"source_id": source["source_event"] + 0x5000, "track": request.track,
                            "start_tick": start, "length_tick": end - start, "muted": False}
                clip = inserted_clip(before, after, expected)
                if clip and all(before[k] == after[k] for k in ("automation", "links", "arrangement_index")):
                    return {**result, "status": "placed", "verification": "native_playlist_and_sample_readback",
                            "clip": clip}
                result["status"] = "partial" if result.get("native", {}).get("stage", 0) else "unknown"
                result.setdefault("message", "The requested placement was not fully verified")
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                result["message"] = str(error)
            result["next_action"] = "Inspect the Playlist and sample source before another placement; do not resend."
            return result


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_place_audio_clip(request: AudioPlacement,
                                  session_fingerprint: str | None = None) -> AudioPlacementToolResult:
        """Place an imported Audio Clip on a 1-based Playlist track at quarter-note timing.

        Use fl_import_sample(kind='audio_clip') first. expected_source_path comes from
        fl_inspect_sample.resolved_path. The source window starts at zero; length_qn
        controls its visible duration, not tempo fitting or source time stretching.
        Requires write mode. Verifies source and placement; does not audition or save.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: place_audio(request, session_fingerprint)))
