"""MCP note results, including incomplete receipts and uncertain target ownership.

The outer status governs the operation. A retained receipt describes what that
script reported; it cannot override a later target/session mismatch.
"""

from typing import Annotated, Literal, NotRequired, TypedDict

from pydantic import Field
from mcp.types import CallToolResult
from fl_studio_mcp.track_b_contracts import VerifiedPatternSelectionWrite

from scripts.pattern_identity import IdentityWrite


class SelectionReceipt(VerifiedPatternSelectionWrite):
    # The controller already serialized these strict models to JSON dictionaries.
    applied_at: str


class IdentityReceipt(IdentityWrite):
    applied_at: str


class ScoreNote(TypedDict):
    number: int
    time: Annotated[int, Field(description="Onset in native ticks relative to pattern start; divide by observed ppq for QN.")]
    length: Annotated[int, Field(description="Duration in native ticks.")]
    group: int
    pan: float
    velocity: float
    release: float
    color: int
    fcut: float
    fres: float
    pitchofs: int
    slide: bool
    porta: bool
    muted: bool
    selected: bool
    repeats: int


class ScoreMarker(TypedDict):
    time: int
    name: str
    mode: int
    tsnum: int
    tsden: int


class ScoreReceipt(TypedDict):
    """Authenticated script receipt; failures may have counts but no score snapshot."""

    request_id: str
    status: Literal["observed", "applied", "partial", "failed"]
    message: str
    next_action: NotRequired[str]
    ppq: NotRequired[int]
    notes: NotRequired[list[ScoreNote]]
    markers: NotRequired[list[ScoreMarker]]
    phrase_length_qn: NotRequired[Annotated[float | None,
        Field(description="Observed Length marker extent; null when no unique Length marker exists.")]]
    requested_phrase_length_qn: NotRequired[float]
    added_count: NotRequired[int]
    removed_count: NotRequired[int]
    untouched_notes_preserved: NotRequired[bool]
    markers_preserved: NotRequired[bool]


class NoteResult(TypedDict):
    channel_index: int
    pattern_number: int
    status: Annotated[Literal["observed", "applied", "partial", "failed", "unknown"],
        Field(description="Overall outcome. Unknown takes precedence over any retained script receipt; inspect before another write.")]
    project_saved: Literal[False]
    verification: Annotated[Literal["none", "host_receipt", "host_readback"],
        Field(description="host_receipt acknowledges execution without a complete score snapshot; host_readback includes notes, markers and PPQ for the confirmed target. Neither proves save/reopen.")]
    message: str
    next_action: NotRequired[str]


class ScoreOperationResult(NoteResult):
    request_id: str
    observed: NotRequired[ScoreReceipt]


class PatternCreationResult(NoteResult):
    request_id: NotRequired[str]
    observed: NotRequired[ScoreReceipt]
    selection: NotRequired[SelectionReceipt]
    identity: NotRequired[IdentityReceipt]
    score_status: NotRequired[Literal["failed", "pending"]]


ScoreToolResult = Annotated[CallToolResult, ScoreOperationResult]
PatternToolResult = Annotated[CallToolResult, PatternCreationResult]


class ScoreStartupResult(TypedDict):
    ready: Literal[True]
    verification: Literal["earlier_signed_receipt_this_process", "signed_host_bootstrap_receipt"]
    startup_route: NotRequired[Literal["native_helper", "macos_user_ran_script",
                                       "macos_rerun_last_script"]]
    script_path: NotRequired[str]
    channel_index: NotRequired[int]
    pattern_number: NotRequired[int]
    session_fingerprint: NotRequired[str]


ScoreStartupToolResult = Annotated[CallToolResult, ScoreStartupResult]
