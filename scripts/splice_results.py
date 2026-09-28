"""Owned catalog and download receipts, independent of FL import/playback."""

from typing import Annotated, Literal, TypedDict
from mcp.types import CallToolResult
from scripts.sample_results import AudioFile


class OwnedSound(TypedDict):
    filename: str
    file_hash: str
    musical_key: str | None
    mode: str | None
    bpm: float | None
    sample_type: str | None
    duration_ms: float | None
    tags: list[str]
    pack: str | None
    local_path: str | None
    file_exists: bool


class OwnedInventory(TypedDict):
    owned_samples: int
    samples_with_local_path: int


class SpliceSearchResult(TypedDict):
    source: Literal["Splice Desktop owned catalog"]
    inventory: OwnedInventory
    total_matches: int
    returned: int
    results: list[OwnedSound]


class SpliceDownloadResult(TypedDict):
    status: Literal["available", "downloaded", "unverified"]
    method: Literal["existing_owned_file", "Splice Desktop DownloadSample"]
    file_hash: str
    owned_before_request: Literal[True]
    file: AudioFile
    hash_matches_catalog: bool
    credits_before: int | None
    credits_after: int | None
    credits_checked: bool


SpliceSearchToolResult = Annotated[CallToolResult, SpliceSearchResult]
SpliceDownloadToolResult = Annotated[CallToolResult, SpliceDownloadResult]
