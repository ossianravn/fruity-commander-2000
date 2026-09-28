"""Save the current named project through FL and independently observe its file."""

import ctypes
import hashlib
import os
import struct
import time
from pathlib import Path

import anyio
from fl_studio_mcp import creative
from fl_studio_mcp.bridge_client import TIMEOUT

from scripts.windows_project import ProjectReader
from scripts.project_results import ProjectFileToolResult, ProjectSaveToolResult
from scripts.mcp_results import structured_result


def open_completed_file(path):
    """On Windows, read only while no writer or replacement holds the file."""
    if os.name != "nt":
        return path.open("rb")
    import msvcrt
    from ctypes import wintypes as w

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p,
                                  w.DWORD, w.DWORD, w.HANDLE]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    return os.fdopen(descriptor, "rb")


def file_snapshot(path):
    with open_completed_file(Path(path)) as stream:
        before = os.fstat(stream.fileno())
        header = stream.read(22)
        if (len(header) != 22 or header[:4] != b"FLhd"
                or struct.unpack_from("<I", header, 4)[0] != 6
                or header[14:18] != b"FLdt"
                or struct.unpack_from("<I", header, 18)[0] + 22 != before.st_size):
            raise ValueError("Project file is not a complete FLP container")
        digest = hashlib.sha256(header)
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Project file changed during disk inspection")
        return {"size_bytes": after.st_size, "modified_ns": after.st_mtime_ns,
                "sha256": digest.hexdigest()}


def inspect_project_file():
    with ProjectReader() as reader:
        identity = reader.identity()
        try:
            observed = file_snapshot(identity["path"]) if identity["path"] else None
        except FileNotFoundError:
            observed = None
        if reader.identity() != identity:
            raise ValueError("FL project changed during file inspection")
        return {**identity, "saved_file": observed,
                "verification": "saved_file_snapshot_only",
                "message": "This inspects disk; it does not prove unsaved host edits are persisted."}


def save_project(session_fingerprint=None):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(
            session_fingerprint=session_fingerprint)
        with ProjectReader() as reader:
            identity = reader.identity()
            path = identity["path"]
            result = {**identity, "session_fingerprint": session,
                      "project_saved": False, "status": "not_saved",
                      "verification": "none", "automatic_retry": False}
            if not path or not Path(path).is_file():
                return {**result, "message": "This project needs Save As; use fl_save_project_as with an explicit destination."}
            before = file_snapshot(path)
            result["before_file"] = before
            if reader.identity() != identity:
                raise ValueError("FL project changed before save dispatch")
            try:
                reply = client.call("project.save", session_fingerprint=session)
                result["host"] = reply
                if reply.get("command") != "project.save" or reply.get("session_fingerprint") != session:
                    raise ValueError("Save acknowledgement did not match the project session")
            except (OSError, RuntimeError, ValueError) as error:
                return {**result, "status": "unknown", "message": str(error),
                        "next_action": "Inspect the current project and file; do not automatically resend save."}
            deadline = time.monotonic() + TIMEOUT
            observation_error = "No completed file write was observed after save dispatch"
            while True:
                try:
                    if reader.identity() != identity or client.ping().get("session_fingerprint") != session:
                        return {**result, "status": "unknown",
                                "message": "Project identity changed during save verification."}
                    after = file_snapshot(path)
                    result["after_file"] = after
                    if after != before:
                        if reader.identity() != identity or client.ping().get("session_fingerprint") != session:
                            return {**result, "status": "unknown",
                                    "message": "Project identity changed during disk readback."}
                        return {**result, "project_saved": True, "status": "saved",
                                "verification": "host_save_and_completed_file_write",
                                "message": "FL acknowledged save and the current project's complete FLP file was rewritten. Reopening was not tested."}
                except (OSError, RuntimeError, ValueError) as error:
                    observation_error = str(error)
                if time.monotonic() >= deadline:
                    return {**result, "status": "unknown", "message": observation_error,
                            "next_action": "Inspect the current project and file; do not automatically resend save."}
                time.sleep(0.1)


def register(server):
    @server.mcp.tool(annotations=server.READ_ONLY)
    async def fl_get_project_file() -> ProjectFileToolResult:
        """Read the current project's full path and a completed saved-file snapshot.

        Windows engine access is qualified for FL 26.1.6.5639. File existence
        does not prove current host edits are saved. Does not save or change FL.
        path is null for an unnamed project; saved_file is null when no file exists.
        A file snapshot does not establish save/reopen verification.
        """
        return structured_result(await anyio.to_thread.run_sync(inspect_project_file))

    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_save_project(session_fingerprint: str | None = None) -> ProjectSaveToolResult:
        """Save the current named FLP and verify its file write at its actual path.

        Requires write mode. Use fl_save_project_as to assign an explicit new path.
        Unknown results are not retried. File-write evidence is distinct from
        save/reopen qualification. FL's dirty flag is not persistence proof.
        Use outer status/project_saved/verification, not a retained host reply or
        file snapshot alone. unknown means unconfirmed, even if FL actually saved;
        not_saved means this call needs Save As. Absent evidence stays absent.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: save_project(session_fingerprint)))
