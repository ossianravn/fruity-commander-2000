"""Inspect FL's actual run-last-script target on the qualified engine binary.

Derived from the live EEPRLastScriptMenu callback and its disassembly on
26.1.6.5639: last index, TStringList instance, Count at +0x40 and data at +0x38.
This module only reads host memory. It never changes the selected script.
"""

import os
import struct

from scripts.windows_project import ProjectReader
from scripts.windows_shortcut import trigger_piano_roll_shortcut


LAST_INDEX_RVA = 0x11313CC
SCRIPT_LIST_RVA = 0x12BE9F8


def selected_score_script(reader):
    def pointer(address):
        return struct.unpack("<Q", reader.read(address, 8))[0]

    index_bytes = reader.read(reader.base + LAST_INDEX_RVA, 4)
    index = struct.unpack("<i", index_bytes)[0]
    listing = pointer(reader.base + SCRIPT_LIST_RVA)
    if index < 0 or not listing:
        return None
    count = struct.unpack("<i", reader.read(listing + 0x40, 4))[0]
    if index >= count:
        raise ValueError("FL's selected score script is outside its script inventory")
    array = pointer(listing + 0x38)
    address = array + index * 16
    text = pointer(address)
    header = reader.read(text - 12, 12)
    codepage, unit, _, length = struct.unpack("<HHiI", header)
    if codepage != 1200 or unit != 2 or length > 32767:
        raise ValueError("FL's selected script path has an unexpected representation")
    data = reader.read(text, (length + 1) * 2)
    unchanged = (reader.read(reader.base + LAST_INDEX_RVA, 4) == index_bytes
                 and pointer(reader.base + SCRIPT_LIST_RVA) == listing
                 and pointer(listing + 0x38) == array and pointer(address) == text
                 and reader.read(text - 12, 12) == header)
    if not unchanged or data[-2:] != b"\0\0":
        raise ValueError("FL's selected score script changed during inspection")
    return data[:-2].decode("utf-16-le")


def require_owned_script():
    from fl_studio_mcp import creative

    expected = creative.piano_roll_scripts_directory() / creative.PIANO_ROLL_SCRIPT_NAME
    with ProjectReader() as reader:
        selected = selected_score_script(reader)
    if not selected or os.path.normcase(selected) != os.path.normcase(str(expected)):
        raise ValueError("Automatic score startup cannot select the intended script yet. "
                         f"FL's last script is {selected!r}; required script is {str(expected)!r}. "
                         "No shortcut was sent.")
    return selected


def trigger_owned_score_script():
    return trigger_piano_roll_shortcut(validate_target=require_owned_script)
