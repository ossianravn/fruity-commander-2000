"""Short-lived, thread-scoped Windows hook for owned native host operations."""

import ctypes
import mmap
import os
import secrets
from ctypes import wintypes as w
from pathlib import Path


DLL_PATH = Path(__file__).resolve().parents[1] / ".local/native/FruityCommanderHost.dll"
MESSAGE_NAME = "FruityCommander.Native.v3"


class Request(ctypes.Structure):
    _fields_ = [("version", w.DWORD), ("bytes", w.DWORD), ("process", w.DWORD),
                ("operation", w.DWORD), ("nonce", ctypes.c_uint64),
                ("status", w.LONG), ("thread", w.DWORD), ("exception", w.DWORD),
                ("expected_channels", ctypes.c_int32), ("created_channel", ctypes.c_int32),
                ("source_event", ctypes.c_int32), ("stage", w.DWORD),
                ("created_clip", ctypes.c_int32),
                ("path", w.WCHAR * 32768), ("project", w.WCHAR * 32768),
                ("error", w.WCHAR * 512)]


def native_api():
    if os.name != "nt":
        raise OSError("The native helper is currently qualified on Windows x64")
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = [
        (user.GetWindowThreadProcessId, [w.HWND, ctypes.POINTER(w.DWORD)], w.DWORD),
        (user.RegisterWindowMessageW, [w.LPCWSTR], w.UINT),
        (user.SetWindowsHookExW, [ctypes.c_int, ctypes.c_void_p, w.HMODULE, w.DWORD], w.HANDLE),
        (user.UnhookWindowsHookEx, [w.HANDLE], w.BOOL),
        (user.PostMessageW, [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
        (user.SendMessageTimeoutW, [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT,
                                   w.UINT, ctypes.POINTER(ctypes.c_size_t)], ctypes.c_ssize_t),
        (kernel.LoadLibraryW, [w.LPCWSTR], w.HMODULE),
        (kernel.GetProcAddress, [w.HMODULE, ctypes.c_char_p], ctypes.c_void_p),
        (kernel.FreeLibrary, [w.HMODULE], w.BOOL),
    ]
    for function, arguments, result in signatures:
        function.argtypes, function.restype = arguments, result
    return user, kernel


class NativeExecutionError(RuntimeError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def dispatch(window, process_id, operation, *, path="", project="",
             expected_channels=-1, timeout_ms=15000, payload=b""):
    """Return native execution evidence; never infer musical success from dispatch."""
    user, kernel = native_api()
    actual_pid = w.DWORD()
    thread = user.GetWindowThreadProcessId(window, ctypes.byref(actual_pid))
    if not thread or actual_pid.value != process_id:
        raise ValueError("Native dispatch target changed before loading")
    message = user.RegisterWindowMessageW(MESSAGE_NAME)
    if not message:
        raise ctypes.WinError(ctypes.get_last_error())
    nonce = secrets.randbits(63)
    size = ctypes.sizeof(Request) + len(payload)
    if size > 0xffffffff:
        raise ValueError("Native request exceeds the protocol's 32-bit byte representation")
    request = Request(version=3, bytes=size, process=process_id,
                      operation=operation, nonce=nonce, path=path, project=project,
                      expected_channels=expected_channels, created_channel=-1, source_event=-1,
                      created_clip=-1)
    name = f"Local\\FruityCommander.{process_id}.{nonce:016x}"
    with mmap.mmap(-1, size, tagname=name) as mapping:
        mapping.write(bytes(request))
        mapping.write(payload)
        module = kernel.LoadLibraryW(str(DLL_PATH))
        if not module:
            raise OSError(f"Cannot load {DLL_PATH}: {ctypes.WinError(ctypes.get_last_error())}")
        hook = None
        try:
            callback = kernel.GetProcAddress(module, b"HostHook")
            if not callback:
                raise ctypes.WinError(ctypes.get_last_error())
            hook = user.SetWindowsHookExW(4, callback, module, thread)  # WH_CALLWNDPROC
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            result = ctypes.c_size_t()
            delivered = user.SendMessageTimeoutW(window, message, 0, nonce,
                                                  0x22, timeout_ms, ctypes.byref(result))
            response = Request.from_buffer_copy(mapping[:])
            evidence = {"process_id": process_id, "thread_id": response.thread,
                        "operation": operation, "created_channel": response.created_channel,
                        "source_event": response.source_event, "stage": response.stage,
                        "created_clip": response.created_clip,
                        "native_callback_completed": bool(delivered and response.status == 2)}
            if not delivered:
                raise NativeExecutionError("Native dispatch did not complete; outcome unknown, no retry was sent", evidence)
            if response.status != 2 or response.thread != thread:
                detail = response.error or f"Unexpected native status {response.status}"
                raise NativeExecutionError(f"{detail} (exception 0x{response.exception:08x})", evidence)
            return evidence
        finally:
            try:
                if hook and not user.UnhookWindowsHookEx(hook):
                    raise ctypes.WinError(ctypes.get_last_error())
                # Let the target return through its message pump so Windows can
                # release its hook DLL reference. Never force a remote unload.
                if hook and not user.PostMessageW(window, 0, 0, 0):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                if not kernel.FreeLibrary(module):
                    raise ctypes.WinError(ctypes.get_last_error())


def run_owned_score_script():
    from fl_studio_mcp import creative
    from scripts.windows_project import ProjectReader

    script = creative.piano_roll_scripts_directory() / creative.PIANO_ROLL_SCRIPT_NAME
    if not script.is_file():
        raise ValueError(f"Owned score script has not been deployed: {script}")
    with ProjectReader() as reader:
        identity = reader.identity()
        evidence = dispatch(reader.window, reader.pid, 2, path=str(script),
                            project=identity["path"] or "")
    return {**evidence, "script_path": str(script)}
