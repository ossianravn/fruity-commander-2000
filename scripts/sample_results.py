"""File acquisition, native source identity, and playback are separate evidence."""

from typing import Annotated, Literal, NotRequired, TypedDict
from mcp.types import CallToolResult
from scripts.native_results import NativeMutationResult
from scripts.plugin_results import ChannelReadback
from scripts.arrangement_results import ArrangementMutationResult, PlaylistClip


class AudioFile(TypedDict):
    path: str
    sha256: str
    frames: int
    sample_rate: int
    channels: int
    duration_seconds: float


class SampleSource(TypedDict):
    channel_index: int
    kind: Literal["sampler", "audio_clip"]
    source_event: int
    source_path: str
    resolved_path: str
    file_exists: bool
    verification: Literal["native_sample_path_readback"]


class SampleImportResult(NativeMutationResult):
    status: Literal["imported", "partial", "unknown"]
    verification: Literal["none", "native_sample_path_and_channel_readback"]
    file: AudioFile
    session_fingerprint: str
    external_assets_copied: Literal[False]
    playback_verified: Literal[False]
    observed_channel_count: NotRequired[int]
    source: NotRequired[SampleSource]
    channel: NotRequired[ChannelReadback]


SampleSourceToolResult = Annotated[CallToolResult, SampleSource]
SampleImportToolResult = Annotated[CallToolResult, SampleImportResult]


class AudioPlacementResult(ArrangementMutationResult):
    status: Literal["placed", "partial", "unknown"]
    verification: Literal["none", "native_playlist_and_sample_readback"]
    source: SampleSource
    ppq: int
    clip: NotRequired[PlaylistClip]


AudioPlacementToolResult = Annotated[CallToolResult, AudioPlacementResult]
