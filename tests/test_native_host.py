"""Real cross-process hook test; no FL engine or musical mutation in this fixture."""

import ctypes
import os
import subprocess
import time
import unittest
from ctypes import wintypes as w

from scripts.native_host import DLL_PATH, dispatch, native_api


@unittest.skipUnless(os.name == "nt" and DLL_PATH.exists(), "Build the Windows native fixture first")
class NativeHostTest(unittest.TestCase):
    def assert_unloaded(self, user, window):
        deadline = time.monotonic() + 2
        value = ctypes.c_size_t()
        while True:
            self.assertTrue(user.SendMessageTimeoutW(window, 0x8001, 0, 0, 0x22, 1000,
                                                    ctypes.byref(value)))
            if not value.value:
                return
            self.assertLess(time.monotonic(), deadline, "Hook DLL remained loaded")
            time.sleep(0.01)

    def test_target_thread_dispatch_failure_and_hook_removal(self):
        host = subprocess.Popen([str(DLL_PATH.with_name("NativeTestHost.exe"))],
                                stdout=subprocess.PIPE, text=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        user, _ = native_api()
        window, pid, thread = map(int, host.stdout.readline().split())
        try:
            result = dispatch(window, pid, 1, payload=bytes(100000))
            self.assertEqual(result["thread_id"], thread)
            with self.assertRaisesRegex(RuntimeError, "unqualified"):
                dispatch(window, pid, 2)
            # Repeated independent load/unhook cycles still reach the same thread.
            self.assertTrue(dispatch(window, pid, 1)["native_callback_completed"])
            with self.assertRaisesRegex(ValueError, "target changed"):
                dispatch(window, pid + 1, 1)
            self.assert_unloaded(user, window)
            user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            user.PostMessageW(window, 0x8002, 0, 0)
            self.assertEqual(host.stdout.readline().strip(), "busy")
            with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
                dispatch(window, pid, 1, timeout_ms=10)
            self.assert_unloaded(user, window)
        finally:
            user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            user.PostMessageW(window, 0x10, 0, 0)
            host.wait(timeout=5)
            host.stdout.close()
        self.assertEqual(host.returncode, 0)
