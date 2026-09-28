"""Independent native curve, link and Playlist reads on the qualified engine.

FruityLink's inspected MIT SDK supplied the layout research leads. Every RVA and
the 88-byte clip stride below were separately inspected on our exact engine.
Reads detect observed changes; they are not an atomic host-thread snapshot.
"""

import math
import struct

from scripts.windows_project import ProjectReader


class ArrangementReader(ProjectReader):
    def value(self, address, fmt="<Q"):
        return struct.unpack(fmt, self.read(address, struct.calcsize(fmt)))[0]

    def channel_objects(self):
        owner = self.value(self.value(self.base + 0x11E6280))
        header = self.read(owner + 8, 16)
        data, count, capacity = struct.unpack("<Qii", header)
        if count < 0 or capacity < count:
            raise ValueError("Unexpected native channel list representation")
        objects = list(struct.unpack(f"<{count}Q", self.read(data, count * 8))) if count else []
        if self.read(owner + 8, 16) != header:
            raise ValueError("Channel inventory changed during inspection")
        return objects

    def curve(self, index, channel):
        if self.value(channel + 0x160, "<i") != 5:
            raise ValueError("Requested channel is not a native Automation Clip")
        envelope = self.value(self.value(channel + 0x360) + 0x10)
        if self.value(envelope) != self.base + 0x797558 or self.value(envelope + 0x58, "<i") != 4:
            raise ValueError("Unexpected Automation Clip envelope representation")
        array = self.value(envelope + 0x28)
        count = self.value(array - 8, "<q") if array else 0
        if count < 0:
            raise ValueError("Negative native automation point count")
        raw = self.read(array, count * 32) if count else b""
        points, time = [], 0.0
        for offset in range(0, len(raw), 32):
            delta, value, tension, curve = struct.unpack_from("<fffB", raw, offset)
            if not all(math.isfinite(v) for v in (delta, value, tension)) or delta < 0:
                raise ValueError("Unexpected native automation point data")
            time += delta
            points.append({"time_qn": time, "value": value, "tension": tension, "curve": curve})
        if self.value(envelope + 0x28) != array or (array and self.value(array - 8, "<q") != count):
            raise ValueError("Automation points changed during inspection")
        if raw and self.read(array, len(raw)) != raw:
            raise ValueError("Automation values changed during inspection")
        return {"channel_index": index, "source_event": self.value(channel + 0x9C, "<I"), "points": points}

    def playlist(self):
        index = self.value(self.base + 0x11DA658, "<i")
        if index < 0:
            raise ValueError("No current arrangement")
        arrangement = self.value(self.value(self.base + 0x1572B60) + index * 8)
        collection = self.value(arrangement + 0x14)
        header = self.read(collection + 8, 16)
        data, stride, count = struct.unpack("<Qii", header)
        if stride != 88 or count < 0:
            raise ValueError("Unexpected Playlist collection layout")
        raw = self.read(data, count * stride) if count else b""
        clips = []
        for i in range(count):
            at = i * stride
            start, source, length, track = struct.unpack_from("<iIih", raw, at)
            clips.append({"index": i, "start_tick": start, "source_id": source,
                          "length_tick": length, "track": 500 - track,
                          "muted": bool(raw[at + 0x13] & 0x20),
                          "source_range_bytes": raw[at + 0x18:at + 0x20].hex()})
        if self.read(collection + 8, 16) != header or self.value(self.base + 0x11DA658, "<i") != index:
            raise ValueError("Playlist changed during inspection")
        if raw and self.read(data, len(raw)) != raw:
            raise ValueError("Playlist records changed during inspection")
        return {"arrangement_index": index, "clips": clips}

    def links(self):
        owner = self.value(self.value(self.base + 0x11E4A68) + 8)
        header = self.read(owner + 8, 16)
        data, count, capacity = struct.unpack("<Qii", header)
        if count < 0 or capacity < count:
            raise ValueError("Unexpected automation link registry")
        links = []
        for i in range(count):
            entry = self.value(data + i * 8)
            links.append({"source_event": self.value(entry + 8, "<I"),
                          "target_event": self.value(entry + 0x10, "<I")})
        if self.read(owner + 8, 16) != header:
            raise ValueError("Automation link registry changed during inspection")
        return links

    def snapshot(self):
        identity = self.identity()
        objects = self.channel_objects()
        curves = [self.curve(i, channel) for i, channel in enumerate(objects)
                  if self.value(channel + 0x160, "<i") == 5]
        result = {**self.playlist(), "automation": curves, "links": self.links()}
        if self.identity() != identity or self.channel_objects() != objects:
            raise ValueError("Project or channel inventory changed during arrangement inspection")
        selection = {k: v for k, v in self.time_selection().items() if k != "owner"}
        return {**result, "time_selection": selection, "project": identity,
                "verification": "native_object_readback"}

    def time_selection(self):
        owner = self.value(self.value(self.base + 0x11E7630))
        start, end = struct.unpack("<ii", self.read(owner + 0xD74, 8))
        return {"owner": owner, "start_tick": start, "end_tick": end,
                "active": end > start >= 0}
