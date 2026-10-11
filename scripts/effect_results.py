"""Effect discovery and observed mixer-slot insertion results."""

from typing import Annotated, Literal, NotRequired, TypedDict

from mcp.types import CallToolResult

from scripts.native_results import NativeMutationResult
from scripts.plugin_results import GeneratorEntry


class EffectCatalog(TypedDict):
    effects: list[GeneratorEntry]
    searched_roots: list[str]


class EffectReadback(TypedDict):
    slot: int
    name: str
    user_name: str
    param_count: int
    mix_level: float | None
    use_global_index: Literal[False]
    target_fingerprint: str


class EffectLoadingResult(NativeMutationResult):
    status: Literal["loaded", "partial", "unknown"]
    verification: Literal["none", "host_plugin_identity_and_mixer_preservation_readback"]
    preset_path: str
    expected_plugin_name: str
    session_fingerprint: str
    track_index: int
    slot_index: int
    observed_effects: NotRequired[list[EffectReadback]]
    effect: NotRequired[EffectReadback]
    mixer_preserved: NotRequired[bool]


EffectCatalogToolResult = Annotated[CallToolResult, EffectCatalog]
EffectLoadingToolResult = Annotated[CallToolResult, EffectLoadingResult]
