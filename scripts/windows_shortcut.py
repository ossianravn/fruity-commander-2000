"""Resolve PostFader's Windows shortcut target by process, not browser title."""

import ctypes
import os
import time
from ctypes import wintypes
from pathlib import PureWindowsPath


def select_fl_window(candidates):
    matches = [handle for handle, title, executable in candidates
               if "FL Studio" in title
               and PureWindowsPath(executable).name.lower() in ("fl64.exe", "fl.exe")]
    if len(matches) != 1:
        raise ValueError(f"Expected one visible FL main window; found {len(matches)}")
    return matches[0]


def _windows_api():
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    signatures = [
        (user.EnumWindows, [callback_type, wintypes.LPARAM], wintypes.BOOL),
        (user.IsWindowVisible, [wintypes.HWND], wintypes.BOOL),
        (user.GetWindowTextLengthW, [wintypes.HWND], ctypes.c_int),
        (user.GetWindowTextW, [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
        (user.GetWindowThreadProcessId, [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)], wintypes.DWORD),
        (user.ShowWindow, [wintypes.HWND, ctypes.c_int], wintypes.BOOL),
        (user.SetForegroundWindow, [wintypes.HWND], wintypes.BOOL),
        (user.GetForegroundWindow, [], wintypes.HWND),
        (user.keybd_event, [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t], None),
        (kernel.OpenProcess, [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        (kernel.QueryFullProcessImageNameW, [wintypes.HANDLE, wintypes.DWORD,
                                           wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        (kernel.CloseHandle, [wintypes.HANDLE], wintypes.BOOL),
    ]
    for function, arguments, result in signatures:
        function.argtypes = arguments
        function.restype = result
    return user, kernel, callback_type


def _find_window(user, kernel, callback_type):
    candidates = []

    def inspect(handle, unused):
        if not user.IsWindowVisible(handle):
            return True
        title = ctypes.create_unicode_buffer(user.GetWindowTextLengthW(handle) + 1)
        user.GetWindowTextW(handle, title, len(title))
        if "FL Studio" not in title.value:
            return True
        process_id = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        process = kernel.OpenProcess(0x1000, False, process_id.value)
        if not process:
            return True  # Cannot identify this process; it is not a target.
        try:
            path = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(path))
            if kernel.QueryFullProcessImageNameW(process, 0, path, ctypes.byref(length)):
                candidates.append((handle, title.value, path.value))
        finally:
            kernel.CloseHandle(process)
        return True

    if not user.EnumWindows(callback_type(inspect), 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return select_fl_window(candidates)


def _focus_window(user, window):
    user.ShowWindow(window, 9)
    user.keybd_event(0x12, 0, 0, 0)
    try:
        user.SetForegroundWindow(window)
    finally:
        user.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.3)
    if user.GetForegroundWindow() != window:
        raise RuntimeError("Windows did not grant FL Studio foreground focus")


def focus_fl_window():
    if os.environ.get("FL_BRIDGE_SANDBOXED") == "1":
        raise RuntimeError("Desktop focus is disabled in the offline environment")
    user, kernel, callback_type = _windows_api()
    _focus_window(user, _find_window(user, kernel, callback_type))


def trigger_fl_shortcut(keys, shortcut, validate_target=None):
    from fl_studio_mcp.creative import HotkeyDispatch

    found = focused = False
    try:
        if os.environ.get("FL_BRIDGE_SANDBOXED") == "1":
            raise RuntimeError("Desktop shortcuts are disabled in the offline environment")
        user, kernel, callback_type = _windows_api()
        window = _find_window(user, kernel, callback_type)
        found = True
        _focus_window(user, window)
        focused = True
        if validate_target is not None:
            validate_target()
        pressed = []
        try:
            for key in keys:
                user.keybd_event(key, 0, 0, 0)
                pressed.append(key)
        finally:
            for key in reversed(pressed):
                user.keybd_event(key, 0, 2, 0)
    except (OSError, ValueError, RuntimeError) as error:
        return HotkeyDispatch(platform="windows", shortcut=shortcut,
                              fl_window_found=found, fl_window_focused=focused,
                              hotkey_dispatched=False, error=str(error))
    return HotkeyDispatch(platform="windows", shortcut=shortcut,
                          fl_window_found=True, fl_window_focused=True,
                          hotkey_dispatched=True)


def trigger_piano_roll_shortcut(validate_target=None):
    return trigger_fl_shortcut((0x11, 0x12, 0x59), "Ctrl+Alt+Y", validate_target)
