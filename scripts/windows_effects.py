"""Read the exact-engine mixer target before a single host-thread insertion."""

import struct


def effect_target(reader, track_index, slot_index):
    def read(address, format="Q"):
        return struct.unpack("<" + format, reader.read(address, struct.calcsize("<" + format)))[0]

    count = read(read(reader.base + 0x11E6200), "i")
    if not 0 <= track_index <= count - 2 or not 0 <= slot_index < 10:
        raise ValueError("Mixer track/slot is outside FL's current addressable range")
    array = read(reader.base + 0x11E4708)
    if not array:
        raise ValueError("FL's mixer inventory is unavailable")
    slot = read(array + track_index * 0x1478 + 0x134C + slot_index * 8)
    if not slot or read(slot + 0x64, "i") != -1:
        raise ValueError("The requested effect slot is not empty; existing effects are preserved")
    if (read(slot + 0x130, "i"), read(slot + 0x134, "i")) != (track_index, slot_index):
        raise ValueError("FL's mixer slot identity differs from the requested target")
    if read(read(slot) + 0xF0) != reader.base + 0xEC43D0:
        raise ValueError("The mixer slot load method differs from the inspected implementation")
    return struct.pack("<iiQQ", track_index, slot_index, array, slot)
