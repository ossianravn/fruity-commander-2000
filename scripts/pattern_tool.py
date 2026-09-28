"""Prepare an empty FL pattern and create its native score and phrase extent."""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from fl_studio_mcp import creative

from scripts.range_runtime import note_timing, ticks
from scripts.range_tool import NewNote, dispatch_locked_score
from scripts.score_startup import ensure_locked_score_session
from scripts.score_results import PatternToolResult
from scripts.mcp_results import structured_result


class PatternCreation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1)
    phrase_length_qn: float = Field(gt=0)
    notes: list[NewNote]

    @model_validator(mode="after")
    def validate_phrase(self):
        if any(n.start_qn >= self.phrase_length_qn for n in self.notes):
            raise ValueError("New note onsets must be inside the requested phrase")
        return self


def create_pattern(request, channel_index):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, ping, session = creative._writable_preflight()
        project = client.call("project.info")
        ppq = project["ppq"]
        if type(ppq) is not int or ppq <= 0:
            raise ValueError("FL did not report a valid PPQ")
        # project.info counts the visible Channel Rack filter on this host.
        channels = client.call("channels.list", global_count=True)
        if not 0 <= channel_index < channels["channel_count"]:
            raise ValueError("The requested instrument channel does not exist")
        data = request.model_dump(mode="json")
        if ticks(request.phrase_length_qn, ppq) <= 0:
            raise ValueError("The phrase becomes zero ticks at the project PPQ")
        for note in data["notes"]:
            note_timing(note, ppq, 0, request.phrase_length_qn)
        current = client.call("patterns.list")["current_pattern"]
        ensure_locked_score_session(channel_index, current)
        pinned = creative._PinnedClient(client, ping)
        inspector = creative.TrackBInspector(creative.TrackBReadGateway(pinned))
        found = inspector.find_empty_pattern(start_pattern_number=1)
        pattern = found.empty_pattern_number
        if pattern is None:
            raise ValueError("FL reported no default empty pattern available")
        controller = creative.TrackBController(creative.TrackBMutationGateway(pinned))
        result = {"pattern_number": pattern, "channel_index": channel_index,
                  "status": "unknown", "project_saved": False, "verification": "none"}
        named = False
        try:
            selection = controller.select_pattern(pattern_number=pattern, session_fingerprint=session)
            result["selection"] = selection.model_dump(mode="json")
            if not selection.verified:
                return {**result, "message": "FL did not verify the empty-pattern selection."}
            identity = controller.set_pattern_identity(
                pattern_number=pattern, name=request.name, session_fingerprint=session)
            result["identity"] = identity.model_dump(mode="json")
            if not identity.verified:
                return {**result, "message": "FL did not verify the prepared pattern's name."}
            named = True
            score = dispatch_locked_score("create_score", {**data, "expected_ppq": ppq},
                                          channel_index, pattern, session=session)
            result.update(score)
            if score["status"] in {"failed", "pending"}:
                result.update(status="partial", score_status=score["status"],
                              message="The pattern was named; " + score["message"])
            return result
        except (OSError, RuntimeError, ValueError, KeyError) as error:
            return {**result, "status": "partial" if named else "unknown",
                    "message": f"{type(error).__name__}: {error}",
                    "next_action": "Inspect the returned pattern before making another creation request."}


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    def piano_roll_create_pattern(request: PatternCreation, channel_index: int) -> PatternToolResult:
        """Create an editable pattern with explicit quarter-note notes and phrase length.

        Uses a host-confirmed default empty pattern and FL's normal new-note
        expression defaults. A native Length marker preserves trailing rests.
        Note times are relative to pattern start; velocities are normalized 0..1.
        Readback shows FL's timing/value quantization.
        Returns the actual pattern reference, notes, and extent. Requires write mode;
        automatically starts the owned runtime through the native helper, including
        first named-script selection. Does not place clips or save.
        Inspect partial/unknown results before another creation; never auto-retry.
        Use the outer status/verification; selection/identity can be available even
        when the observed score receipt is absent or incomplete. host_receipt only
        acknowledges execution; it does not establish complete score readback.
        """
        return structured_result(create_pattern(request, channel_index))
