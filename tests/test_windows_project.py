"""Native identity never uses unqualified offsets or an unstable string."""

import struct
import unittest
from unittest.mock import Mock

from scripts.windows_project import ProjectReader, PATH_POINTER_RVA, path_reference
from scripts.windows_score import selected_score_script, LAST_INDEX_RVA, SCRIPT_LIST_RVA


class WindowsProjectTest(unittest.TestCase):
    def test_selected_script_uses_host_index_and_rejects_inventory_change(self):
        reader = ProjectReader.__new__(ProjectReader)
        reader.base = 0
        encoded = "C:\\Scripts\\Owned.PYSCRIPT".encode("utf-16-le")
        memory = {LAST_INDEX_RVA: struct.pack("<i", 1),
                  SCRIPT_LIST_RVA: struct.pack("<Q", 1000),
                  1000 + 0x40: struct.pack("<i", 2),
                  1000 + 0x38: struct.pack("<Q", 2000),
                  2016: struct.pack("<Q", 3000),
                  2988: struct.pack("<HHiI", 1200, 2, 1, len(encoded) // 2),
                  3000: encoded + b"\0\0"}
        reader.read = Mock(side_effect=lambda address, size: memory[address])
        self.assertEqual(selected_score_script(reader), "C:\\Scripts\\Owned.PYSCRIPT")
        memory[LAST_INDEX_RVA] = struct.pack("<i", 2)
        with self.assertRaisesRegex(ValueError, "outside"):
            selected_score_script(reader)

    def test_unqualified_binary_is_rejected_before_resolving_memory(self):
        with self.assertRaisesRegex(ValueError, "not qualified"):
            path_reference(b"different FL engine")

    def test_unicode_path_and_changed_pointer(self):
        reader = ProjectReader.__new__(ProjectReader)
        reader.base, reader.pid = 0, 123
        pointer = 1000
        encoded = "C:\\Music\\Æøå.flp".encode("utf-16-le")
        memory = {PATH_POINTER_RVA: struct.pack("<Q", pointer),
                  pointer - 12: struct.pack("<HHiI", 1200, 2, 1, len(encoded) // 2),
                  pointer: encoded + b"\0\0"}
        reader.read = Mock(side_effect=lambda address, size: memory[address])
        self.assertEqual(reader.identity()["path"], "C:\\Music\\Æøå.flp")
        reader.read = Mock(side_effect=[memory[PATH_POINTER_RVA], memory[pointer - 12],
                                       memory[pointer], memory[pointer - 12],
                                       struct.pack("<Q", 2000)])
        with self.assertRaisesRegex(ValueError, "identity changed"):
            reader.identity()


if __name__ == "__main__":
    unittest.main()
