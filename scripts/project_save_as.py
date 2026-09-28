"""Save As owns native destination assignment and independent persistence evidence."""

import os
import time
from pathlib import Path

import anyio
from fl_studio_mcp import creative
from fl_studio_mcp.bridge_client import TIMEOUT

from scripts.project_save import file_snapshot
from scripts.windows_project import ProjectReader
from scripts.native_host import NativeExecutionError, dispatch
from scripts.project_results import ProjectSaveAsToolResult
from scripts.mcp_results import structured_result


def same_path(left, right):
    return bool(left and right and os.path.normcase(os.path.normpath(left))
                == os.path.normcase(os.path.normpath(right)))


def save_project_as(destination_path, session_fingerprint=None):
    destination = Path(destination_path)
    if not destination.is_absolute() or destination.suffix.lower() != ".flp":
        raise ValueError("Save As requires an absolute .flp destination path")
    destination = destination.resolve()
    if not destination.parent.is_dir():
        raise ValueError("The Save As destination directory does not exist")
    before_file = file_snapshot(destination) if destination.exists() else None
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        with ProjectReader() as reader:
            before_identity = reader.identity()
            result = {"destination_path": str(destination), "before_identity": before_identity,
                      "before_file": before_file, "session_fingerprint": session,
                      "project_saved": False, "status": "unknown", "verification": "none",
                      "automatic_retry": False}

            try:
                result["native"] = dispatch(reader.window, reader.pid, 10,
                    path=str(destination), project=before_identity["path"] or "", timeout_ms=60000)
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, ValueError, RuntimeError) as error:
                result["message"] = str(error)
            # A lost acknowledgement can still have saved. Inspect, never resend.
            try:
                deadline = time.monotonic() + TIMEOUT
                observation_error = "Save As did not produce the requested path and completed file write"
                while True:
                    identity = reader.identity()
                    result["observed_identity"] = identity
                    if same_path(identity["path"], str(destination)):
                        try:
                            after = file_snapshot(destination)
                        except (OSError, ValueError) as error:
                            observation_error = str(error)
                            after = before_file
                        if after != before_file:
                            ping = client.ping()
                            if ping.get("session_fingerprint") != session or reader.identity() != identity:
                                raise ValueError("FL project session changed during Save As verification")
                            return {**result, "project_saved": True, "status": "saved",
                                    "after_file": after, "verification": "native_path_and_completed_file_write",
                                    "message": "FL adopted the requested path and wrote a complete FLP. Reopening was not tested."}
                    elif identity != before_identity:
                        raise ValueError("FL adopted a different path during Save As")
                    if time.monotonic() >= deadline:
                        raise ValueError(observation_error)
                    time.sleep(0.1)
            except (OSError, ValueError, RuntimeError) as error:
                result.update(message=str(error),
                              next_action="Inspect FL's current path and destination file; do not automatically resend Save As.")
                return result


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_save_project_as(destination_path: str, session_fingerprint: str | None = None) -> ProjectSaveAsToolResult:
        """Save the current project to an explicit absolute .flp path and make it current.

        Requires write mode and an existing destination directory. Replaces an
        existing FLP at that explicitly requested path, using FL's native writer.
        Qualified on Windows FL 26.1.6.5639. Actual native path and completed file
        write must match; unknown outcomes are never retried. Does not copy samples
        or verify reopening. Uses FL's native save route, independent of editor focus.
        Use outer status/project_saved/verification. On unknown, the path or disk
        may already have changed; submitted/observed_identity record only available
        evidence. before_file refers to the destination, and is null if it was new.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: save_project_as(destination_path, session_fingerprint)))
