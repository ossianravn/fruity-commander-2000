"""Replace an existing automation source while preserving its links and placements."""

import struct

import anyio
from pydantic import BaseModel, ConfigDict, Field, model_validator
from fl_studio_mcp import creative

from scripts.automation_contract import AutomationPoint, encode_points
from scripts.native_host import NativeExecutionError, dispatch
from scripts.windows_arrangement import ArrangementReader
from scripts.arrangement_results import AutomationRevisionToolResult
from scripts.mcp_results import structured_result


class ObservedPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    time_qn: float = Field(ge=0)
    value: float
    tension: float
    curve: int = Field(ge=0, le=255)


class AutomationRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_event: int = Field(ge=0, le=0xffffffff)
    expected_points: list[ObservedPoint] = Field(min_length=1)
    points: list[AutomationPoint] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_curve(self):
        if self.points[0].time_qn != 0 or self.points[-1].time_qn != self.expected_points[-1].time_qn:
            raise ValueError("Replacement must start at zero and retain the observed source extent")
        if any(a.time_qn >= b.time_qn for a, b in zip(self.points, self.points[1:])):
            raise ValueError("Automation point times must be strictly increasing")
        return self


def revised_curve(before, after, source, points):
    expected = [{**curve, "points": points} if curve["source_event"] == source else curve
                for curve in before["automation"]]
    preserved = all(before[k] == after[k] for k in
                    ("project", "arrangement_index", "clips", "links", "time_selection"))
    if preserved and after["automation"] == expected:
        return next(curve for curve in expected if curve["source_event"] == source)
    return None


def replace_points(request, session_fingerprint=None):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        payload_points, expected = encode_points(request.points)
        if expected[-1]["time_qn"] != request.expected_points[-1].time_qn:
            raise ValueError("FL float deltas would change the source extent; choose representable point times")
        with ArrangementReader() as reader:
            before = reader.snapshot()
            curve = next((row for row in before["automation"] if row["source_event"] == request.source_event), None)
            if curve is None or curve["points"] != [point.model_dump() for point in request.expected_points]:
                raise ValueError("Automation points changed; inspect the existing source before revising")
            objects = reader.channel_objects()
            channel = objects[curve["channel_index"]]
            envelope = reader.value(reader.value(channel + 0x360) + 0x10)
            array = reader.value(envelope + 0x28)
            raw = reader.read(array, len(curve["points"]) * 32)
            if reader.curve(curve["channel_index"], channel) != curve or reader.read(array, len(raw)) != raw:
                raise ValueError("Automation changed during revision preparation")
            payload = struct.pack("<QQiIII", channel, envelope, curve["channel_index"], request.source_event,
                                  len(curve["points"]), len(request.points)) + raw + payload_points
            result = {"status": "unknown", "verification": "none", "project_saved": False,
                      "automatic_retry": False, "session_fingerprint": session,
                      "source_event": request.source_event}
            try:
                result["native"] = dispatch(reader.window, reader.pid, 8, payload=payload,
                    project=before["project"]["path"] or "", expected_channels=len(objects))
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (ValueError, OSError, RuntimeError) as error:
                result["message"] = str(error)
            try:
                after = reader.snapshot()
                result["observed"] = after
                if client.ping().get("session_fingerprint") != session:
                    raise ValueError("FL session changed during automation revision")
                revised = revised_curve(before, after, request.source_event, expected)
                if revised:
                    return {**result, "status": "revised", "automation": revised,
                            "verification": "native_points_links_and_placements_readback",
                            "message": "Revised the shared automation source; its links and Playlist copies are preserved."}
                result["status"] = "partial" if result.get("native", {}).get("stage", 0) else "unknown"
                result.setdefault("message", "The complete automation revision could not be verified")
            except (ValueError, OSError, RuntimeError, KeyError) as error:
                result["message"] = str(error)
            result["next_action"] = "Inspect the source points, links and Playlist before another edit; do not resend."
            return result


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_replace_automation_points(request: AutomationRevision,
                                            session_fingerprint: str | None = None) -> AutomationRevisionToolResult:
        """Replace an existing Automation Clip source with a linear curve of the same extent.

        Read source_event and the complete expected_points from fl_inspect_native_arrangement.
        New points contain quarter-note time_qn and normalized value, from zero to the
        observed endpoint. This edits the shared source: ALL its Playlist copies change.
        Preserves existing links, placements and other automation sources. Requires write
        mode, does not save, and reports actual float-quantized points. Inspect partial or
        unknown results before another edit; never automatically resend.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: replace_points(request, session_fingerprint)))
