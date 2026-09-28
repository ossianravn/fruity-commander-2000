"""Installed-generator discovery, host identity and opaque preset evidence."""

from typing import Annotated, Literal, NotRequired, TypedDict

from mcp.types import CallToolResult

from scripts.native_results import NativeMutationResult


class GeneratorEntry(TypedDict):
    name: str
    preset_path: str
    expected_plugin_name: str | None
    vendor: str | None
    binary_path: str | None
    format: str | None
    evidence: Literal["FL_plugin_database_entry_not_loaded_instance"]


class GeneratorCatalog(TypedDict):
    generators: list[GeneratorEntry]
    searched_roots: list[str]


class ChannelReadback(TypedDict):
    """Pinned bridge's global channel observation, including unavailable getters."""

    index: int
    index_scope: Literal["global"]
    name: str
    volume: float | None
    pan: float | None
    pitch: float | None
    pitch_semitones: float | None
    pitch_range: float | None
    muted: bool | None
    solo: bool | None
    selected: bool | None
    type: int | None
    type_name: str
    mixer_track: int | None
    color: int | None
    plugin: str
    plugin_user_name: str
    reported_parameter_count: int | None
    target_fingerprint: str | None
    channel_fingerprint: str


class GeneratorLoadingResult(NativeMutationResult):
    status: Literal["loaded", "partial", "unknown"]
    verification: Literal["none", "host_plugin_identity_readback"]
    preset_path: str
    expected_plugin_name: str
    session_fingerprint: str
    observed_channel_count: NotRequired[int]
    new_channels: NotRequired[list[ChannelReadback]]
    channel_index: NotRequired[int]
    channel: NotRequired[ChannelReadback]


class GeneratorStateResult(NativeMutationResult):
    status: Literal["loaded", "unknown"]
    channel_index: int
    preset_path: str
    musical_setup_verified: Literal[False]
    channel: NotRequired[ChannelReadback | None]
    verification: NotRequired[Literal["wrapper_accepted_file_and_instance_retained"]]
    staged_state_path: NotRequired[str]
    staging_cleanup_error: NotRequired[str]


class GeneratorPresetResult(TypedDict):
    status: Literal["exported"]
    preset_path: str
    channel_index: int
    source_project: str
    source_sha256: str
    preset_sha256: str
    size_bytes: int
    state_basis: Literal["saved_project_file"]
    live_plugin_state_verified: Literal[False]
    external_assets_copied: Literal[False]
    message: str


GeneratorCatalogToolResult = Annotated[CallToolResult, GeneratorCatalog]
GeneratorLoadingToolResult = Annotated[CallToolResult, GeneratorLoadingResult]
GeneratorStateToolResult = Annotated[CallToolResult, GeneratorStateResult]
GeneratorPresetToolResult = Annotated[CallToolResult, GeneratorPresetResult]
