"""Read Sampler/Audio Clip sources from the qualified FL engine, not request memory."""

import os
import struct
from pathlib import Path

from scripts.windows_arrangement import ArrangementReader


class SampleReader(ArrangementReader):
    def source(self, index):
        identity, objects = self.identity(), self.channel_objects()
        if index < 0 or index >= len(objects):
            raise ValueError("Sample channel is outside the current inventory")
        channel = objects[index]
        kind = self.value(channel + 0x160, "<i")
        if kind not in (0, 4):
            raise ValueError("Channel is neither a Sampler nor an Audio Clip")
        # Load method BFEB80 -> BEE1F0 reads/writes channel.Sample (+330).Name (+AC).
        owner = self.value(channel + 0x330)
        pointer = self.value(owner + 0xAC)
        path = ""
        if pointer:
            header = self.read(pointer - 12, 12)
            codepage, width, _, count = struct.unpack("<HHiI", header)
            if (codepage, width) != (1200, 2) or count > 32767:
                raise ValueError("Unexpected native sample path representation")
            path = self.read(pointer, count * 2).decode("utf-16-le")
            if self.read(pointer - 12, 12) != header:
                raise ValueError("Sample path changed during readback")
        resolved = path.replace("%FLStudioFactoryData%", str(self.engine.parent))
        user_data = os.environ.get("FL_STUDIO_USER_DATA_DIR")
        if user_data:
            resolved = resolved.replace("%FLStudioUserData%", user_data)
        if (self.identity() != identity or self.channel_objects() != objects
                or self.value(channel + 0x330) != owner or self.value(owner + 0xAC) != pointer):
            raise ValueError("Sample identity changed during readback")
        return {"channel_index": index, "kind": "sampler" if kind == 0 else "audio_clip",
                "source_event": self.value(channel + 0x9C, "<I"), "source_path": path,
                "resolved_path": resolved, "file_exists": bool(resolved) and Path(resolved).is_file(),
                "verification": "native_sample_path_readback"}


def inspect_sample(index):
    with SampleReader() as reader:
        return reader.source(index)
