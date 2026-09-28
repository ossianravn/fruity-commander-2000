"""Native dispatch evidence shared by owned mutation result contracts."""

from typing import Literal, NotRequired, TypedDict


class NativeReceipt(TypedDict):
    process_id: int
    thread_id: int
    operation: int
    created_channel: int
    source_event: int
    stage: int
    created_clip: int
    native_callback_completed: bool


class NativeMutationResult(TypedDict):
    """Dispatch can be absent or incomplete; each operation owns its final status."""

    project_saved: Literal[False]
    automatic_retry: Literal[False]
    native: NotRequired[NativeReceipt]
    message: NotRequired[str]
    next_action: NotRequired[str]
