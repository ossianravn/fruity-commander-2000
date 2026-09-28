"""Translate the qualified FL VST2 bank envelope into standard FXB framing.

FL's -9 state envelope and -2/qword length were inspected in the installed
wrapper serializer. PyFLP identifies wrapper records; JUCE documents FXB layout.
Plugin chunk bytes and external file references remain opaque and unchanged.
"""

import struct

from scripts.generator_presets import parse


def vst2_bank(preset):
    _, events = parse(preset)
    records = dict(events)
    if records.get(201, b"").decode("utf-16-le").rstrip("\0") != "Fruity Wrapper":
        raise ValueError("State loading requires a configured Fruity Wrapper preset")
    wrapper = records.get(213, b"")
    if len(wrapper) < 4 or struct.unpack_from("<I", wrapper)[0] != 12:
        raise ValueError("This FL wrapper state representation is not qualified")
    fields, offset = {}, 4
    while offset < len(wrapper):
        if offset + 12 > len(wrapper):
            raise ValueError("Truncated wrapper record header")
        tag, size = struct.unpack_from("<IQ", wrapper, offset)
        offset += 12
        if tag in fields or size > len(wrapper) - offset:
            raise ValueError("Duplicate or truncated wrapper state record")
        fields[tag] = wrapper[offset:offset + size]
        offset += size
    if len(fields.get(51, b"")) != 4 or 52 in fields:
        raise ValueError("This route requires VST2 bank state; VST3 needs its own state route")
    state = fields.get(53, b"")
    if len(state) < 21:
        raise ValueError("Missing VST2 state envelope")
    version, flags, marker, size, program = struct.unpack_from("<iBiqi", state)
    if version != -9 or not flags & 8 or marker != -2 or size <= 0 or size != len(state) - 21:
        raise ValueError("This preset does not contain the qualified opaque VST2 bank format")
    version_bytes = fields.get(57, b"\0" * 4)
    if len(version_bytes) != 4 or program < 0:
        raise ValueError("Invalid VST2 version or current program")
    # Bank version 2 carries the selected program in the first four future bytes.
    future = struct.pack(">I", program) + bytes(124)
    body = struct.pack(">4sIIII128sI", b"FBCh", 2,
                       int.from_bytes(fields[51], "little"),
                       int.from_bytes(version_bytes, "little"), 1, future, size) + state[21:]
    return b"CcnK" + struct.pack(">I", len(body)) + body
