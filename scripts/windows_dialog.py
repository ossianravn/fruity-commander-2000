"""Process-scoped Windows dialog controls for FL-owned file operations.

Uses standard HWND control identity and messages, never screen coordinates.
Command dispatch is distinct from the operation owner's host/file verification.
"""

import ctypes
import json
import os
import subprocess
from ctypes import wintypes as w
from pathlib import Path

from fl_studio_mcp.bridge_client import TIMEOUT
from scripts.windows_shortcut import _windows_api


class DialogControls:
    def __init__(self, process_id):
        self.pid = process_id
        self.user, _, self.callback_type = _windows_api()
        signatures = [
            ("GetClassNameW", [w.HWND, w.LPWSTR, ctypes.c_int], ctypes.c_int),
            ("GetDlgCtrlID", [w.HWND], ctypes.c_int),
            ("GetParent", [w.HWND], w.HWND),
            ("IsWindowEnabled", [w.HWND], w.BOOL),
            ("IsWindow", [w.HWND], w.BOOL),
            ("EnumChildWindows", [w.HWND, self.callback_type, w.LPARAM], w.BOOL),
            ("PostMessageW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL),
            ("SendMessageTimeoutW", [w.HWND, w.UINT, w.WPARAM, w.LPARAM,
                                      w.UINT, w.UINT, ctypes.POINTER(ctypes.c_size_t)],
             ctypes.c_ssize_t),
        ]
        for name, arguments, result in signatures:
            function = getattr(self.user, name)
            function.argtypes, function.restype = arguments, result

    def owns(self, handle):
        pid = w.DWORD()
        self.user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        return pid.value == self.pid and bool(self.user.IsWindow(handle))

    def message(self, handle, message, wparam=0, lparam=0):
        if not self.owns(handle):
            raise ValueError("FL dialog control no longer belongs to the target process")
        result = ctypes.c_size_t()
        if not self.user.SendMessageTimeoutW(handle, message, wparam, lparam,
                                              0x22, int(TIMEOUT * 1000), ctypes.byref(result)):
            raise OSError("FL dialog did not acknowledge its control message")
        return result.value

    def text(self, handle):
        length = self.message(handle, 0x000E)  # WM_GETTEXTLENGTH
        buffer = ctypes.create_unicode_buffer(length + 1)
        self.message(handle, 0x000D, len(buffer), ctypes.addressof(buffer))
        return buffer.value

    def describe(self, handle):
        name = ctypes.create_unicode_buffer(256)
        if not self.user.GetClassNameW(handle, name, len(name)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"handle": handle, "class": name.value,
                "id": self.user.GetDlgCtrlID(handle),
                "parent": self.user.GetParent(handle),
                "enabled": bool(self.user.IsWindowEnabled(handle)),
                "text": self.text(handle)}

    def windows(self, parent=None):
        handles = []

        def collect(handle, unused):
            if self.owns(handle) and self.user.IsWindowVisible(handle):
                handles.append(handle)
            return True

        callback = self.callback_type(collect)
        if parent is None:
            if not self.user.EnumWindows(callback, 0):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            self.user.EnumChildWindows(parent, callback, 0)
        return [self.describe(handle) for handle in handles]

    def set_text(self, handle, value):
        # EM_REPLACESEL emits the edit notifications used by the Common Item
        # Dialog. WM_SETTEXT changed visible text but left its destination stale.
        buffer = ctypes.create_unicode_buffer(value)
        self.message(handle, 0x00B1, 0, -1)  # EM_SETSEL: select all
        self.message(handle, 0x00C2, 1, ctypes.addressof(buffer))  # EM_REPLACESEL
        if self.text(handle) != value:
            raise ValueError("FL file dialog path readback differs from the request")

    def accessibility(self, handle, action, **data):
        if not self.owns(handle):
            raise ValueError("FL dialog control changed before accessibility access")
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        try:
            result = subprocess.run(
                [str(powershell), "-NoProfile", "-NonInteractive", "-File",
                 str(Path(__file__).with_name("dialog_access.ps1"))],
                input=json.dumps({"process_id": self.pid, "handle": handle,
                                  "action": action, **data}),
                capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT,
                creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as error:
            raise OSError("FL dialog accessibility did not finish") from error
        if result.returncode:
            raise ValueError("FL dialog accessibility: " + result.stderr.strip())
        return json.loads(result.stdout)

    def click(self, handle):
        if not self.owns(handle) or not self.user.IsWindowEnabled(handle):
            raise ValueError("FL dialog button is unavailable")
        # Asynchronous: the button can open a modal confirmation dialog.
        if not self.user.PostMessageW(handle, 0x00F5, 0, 0):  # BM_CLICK
            raise ctypes.WinError(ctypes.get_last_error())
