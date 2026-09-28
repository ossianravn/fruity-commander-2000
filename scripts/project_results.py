"""Project identity and persistence evidence exposed at the MCP boundary.

Only status=saved confirms a completed write. An unknown result can retain an
acknowledgement or file observations without establishing persistence or reopening.
"""

from typing import Annotated, Literal, NotRequired, TypedDict

from mcp.types import CallToolResult
from pydantic import Field
from scripts.native_results import NativeReceipt


class ProjectIdentity(TypedDict):
    process_id: int
    path: str | None
    engine_sha256: str
    identity_basis: Literal["qualified_native_project_path_read"]


class CompletedFile(TypedDict):
    size_bytes: int
    modified_ns: Annotated[int, Field(description="File modification time as integer nanoseconds since the Unix epoch.")]
    sha256: str


class ProjectFileResult(ProjectIdentity):
    saved_file: CompletedFile | None
    verification: Literal["saved_file_snapshot_only"]
    message: str


class SaveAcknowledgement(TypedDict, total=False):
    """Retained host reply, including an incomplete or mismatched acknowledgement."""

    command: str
    dispatch_result: int
    dirty_before: int
    dirty_after: int
    session_fingerprint: str
    session_precondition_applied: bool
    expected_before_applied: bool


class SaveOutcome(TypedDict):
    session_fingerprint: str
    project_saved: bool
    automatic_retry: Literal[False]
    message: str
    next_action: NotRequired[str]


class ProjectSaveResult(ProjectIdentity, SaveOutcome):
    status: Literal["saved", "not_saved", "unknown"]
    verification: Literal["none", "host_save_and_completed_file_write"]
    before_file: NotRequired[CompletedFile]
    host: NotRequired[SaveAcknowledgement]
    after_file: NotRequired[CompletedFile]


class ProjectSaveAsResult(SaveOutcome):
    destination_path: str
    before_identity: ProjectIdentity
    before_file: CompletedFile | None
    status: Literal["saved", "unknown"]
    verification: Literal["none", "native_path_and_completed_file_write"]
    observed_identity: NotRequired[ProjectIdentity]
    after_file: NotRequired[CompletedFile]
    submitted: NotRequired[bool]
    dialog_cleanup_error: NotRequired[str]
    native: NotRequired[NativeReceipt]


ProjectFileToolResult = Annotated[CallToolResult, ProjectFileResult]
ProjectSaveToolResult = Annotated[CallToolResult, ProjectSaveResult]
ProjectSaveAsToolResult = Annotated[CallToolResult, ProjectSaveAsResult]
