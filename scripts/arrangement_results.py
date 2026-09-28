"""MCP result contract for the existing native arrangement reader.

These types describe readback; they impose no new musical input limits. Keep
native ticks and clip-relative quarter notes distinct at the client boundary.
"""

from typing import Annotated, Literal, NotRequired, TypedDict

from mcp.types import CallToolResult
from pydantic import Field

from scripts.native_results import NativeMutationResult
from scripts.project_results import ProjectIdentity


class AutomationReadbackPoint(TypedDict):
    time_qn: Annotated[float, Field(description="Quarter notes relative to automation source start.")]
    value: Annotated[float, Field(description="Stored normalized curve value. Live target value, quantization and musical direction depend on the linked control and mapping; they are not measured here.")]
    tension: float
    curve: int


class AutomationSource(TypedDict):
    """Stored automation curve, not a live plug-in/CC reading or evidence of audible response."""

    channel_index: int
    source_event: Annotated[int, Field(description="Shared automation source ID; use with complete points for revision.")]
    points: list[AutomationReadbackPoint]


class PlaylistClip(TypedDict):
    index: Annotated[int, Field(description="Current collection index; may change after insertion.")]
    start_tick: int
    source_id: Annotated[int, Field(description="Audio and automation placements use their source_event + 0x5000.")]
    length_tick: int
    track: Annotated[int, Field(description="One-based Playlist track.")]
    muted: bool
    source_range_bytes: str


class ParameterLink(TypedDict):
    source_event: int
    target_event: int


class PlaylistTimeSelection(TypedDict):
    start_tick: int
    end_tick: int
    active: bool


class ArrangementSnapshot(TypedDict):
    arrangement_index: int
    clips: Annotated[list[PlaylistClip], Field(description="Placements in native ticks; use current project PPQ to convert.")]
    automation: list[AutomationSource]
    links: list[ParameterLink]
    time_selection: PlaylistTimeSelection
    project: ProjectIdentity
    verification: Literal["native_object_readback"]


class ArrangementMutationResult(NativeMutationResult):
    session_fingerprint: str
    observed: NotRequired[ArrangementSnapshot]


class AutomationCreationResult(ArrangementMutationResult):
    status: Literal["created", "partial", "unknown"]
    verification: Literal["none", "native_objects_and_link_readback"]
    target_event: int
    ppq: int
    automation: NotRequired[AutomationSource]
    clip: NotRequired[PlaylistClip]


class AutomationRevisionResult(ArrangementMutationResult):
    status: Literal["revised", "partial", "unknown"]
    verification: Literal["none", "native_points_links_and_placements_readback"]
    source_event: int
    automation: NotRequired[AutomationSource]


class PatternReference(TypedDict):
    pattern: int
    name: str
    color: int | None
    length: Annotated[int | None, Field(description="Legacy FL pattern length in sixteenth-note steps, not quarter notes.")]
    current: bool
    selected: bool
    default: bool


class PatternPlacementResult(ArrangementMutationResult):
    status: Literal["placed", "partial", "unknown"]
    verification: Literal["none", "native_playlist_readback"]
    pattern: PatternReference
    ppq: int
    clip: NotRequired[PlaylistClip]


class OwnedTimeSelection(PlaylistTimeSelection):
    owner: int


class PlaylistSelectionResult(NativeMutationResult):
    status: Literal["selected", "cleared", "unknown"]
    before: OwnedTimeSelection
    ppq: int
    after: NotRequired[OwnedTimeSelection]
    verification: NotRequired[Literal["native_playlist_selection_readback"]]


AutomationCreationToolResult = Annotated[CallToolResult, AutomationCreationResult]
AutomationRevisionToolResult = Annotated[CallToolResult, AutomationRevisionResult]
PatternPlacementToolResult = Annotated[CallToolResult, PatternPlacementResult]
PlaylistSelectionToolResult = Annotated[CallToolResult, PlaylistSelectionResult]
