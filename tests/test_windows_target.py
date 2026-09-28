"""Window resolution must not dispatch FL shortcuts into a browser."""

import unittest

from scripts.windows_shortcut import select_fl_window


class WindowTargetTest(unittest.TestCase):
    def test_title_collision_selects_the_fl_process(self):
        candidates = [
            (10, "How to install FL Studio - Google Chrome", r"C:\Chrome\chrome.exe"),
            (20, "Proof.flp - FL Studio 2026", r"C:\Image-Line\FL64.exe"),
            (21, "Plugin 001 - TubeSynth", r"C:\Image-Line\FL64.exe"),
        ]
        self.assertEqual(select_fl_window(candidates), 20)
        with self.assertRaisesRegex(ValueError, "found 0"):
            select_fl_window(candidates[:1])


if __name__ == "__main__":
    unittest.main()
