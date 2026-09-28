"""Extract saved generator state into an FL preset using an existing preset envelope.

Event framing follows the inspected FruityLink SDK's FlpPluginStateReader
(MIT, c0a76bc5779728084a4165b08314a8575d5e781e), including FL26's tagged event172.
Plugin state remains opaque; external assets/references are not copied or rewritten.
"""

import hashlib
import struct
from pathlib import Path

import anyio

from scripts.plugin_results import GeneratorPresetToolResult
from scripts.mcp_results import structured_result


def read_events(image, tagged=True):
    if len(image) < 14 or image[:4] != b"FLhd":
        raise ValueError("Missing FL header")
    chunk = 8 + struct.unpack_from("<I", image, 4)[0]
    if image[chunk:chunk + 4] != b"FLdt" or chunk + 8 > len(image):
        raise ValueError("Missing FL event chunk")
    pos = chunk + 8
    end = pos + struct.unpack_from("<I", image, chunk + 4)[0]
    if end != len(image):
        raise ValueError("FL event chunk does not match file length")
    events = []
    while pos < end:
        event = image[pos]
        pos += 1
        if event < 192:
            size = 1 if event < 64 else 2 if event < 128 else 4
            if event == 172 and tagged:
                if pos == end:
                    raise ValueError("Truncated tagged FL event")
                size = 3 if image[pos] == 1 else 5
        else:
            size, shift = 0, 0
            while True:
                if pos == end or shift >= 35:
                    raise ValueError("Invalid FL event length")
                value = image[pos]
                pos += 1
                size |= (value & 127) << shift
                if value < 128:
                    break
                shift += 7
        if pos + size > end:
            raise ValueError("Truncated FL event payload")
        events.append((event, image[pos:pos + size]))
        pos += size
    return image[:chunk], events


def parse(image):
    try:
        return read_events(image)
    except ValueError as tagged_error:
        try:
            return read_events(image, tagged=False)
        except ValueError:
            raise tagged_error


def encode_event(event, payload):
    result = bytearray([event])
    if event >= 192:
        size = len(payload)
        while size >= 128:
            result.append((size & 127) | 128)
            size >>= 7
        result.append(size)
    return bytes(result) + payload


def preset_image(project, channel_index, template):
    _, source = parse(project)
    header, envelope = parse(template)
    required = (201, 212, 203, 213)
    selected, channel = {}, None
    for event, payload in source:
        if event == 199 and event not in selected:
            selected[event] = payload
        elif event == 64:
            channel = int.from_bytes(payload, "little")
        elif event == 236:
            channel = None
        elif channel == channel_index and event in required:
            if event in selected:
                raise ValueError("Ambiguous generator state in the saved project")
            selected[event] = payload
    if set(selected) != set(required) | {199}:
        raise ValueError("The saved channel does not contain a complete generator preset state")
    if [event for event, _ in envelope] != [199, 28, 201, 212, 203, 213]:
        raise ValueError("Use a generator database preset with the qualified six-event envelope")
    data = b"".join(encode_event(event, selected.get(event, payload)) for event, payload in envelope)
    return header + b"FLdt" + struct.pack("<I", len(data)) + data


def extract_preset(project_path, channel_index, template_path, destination_path):
    project, template, destination = map(Path, (project_path, template_path, destination_path))
    if any(not path.is_absolute() for path in (project, template, destination)):
        raise ValueError("Project, preset template and destination paths must be absolute")
    if channel_index < 0 or destination.suffix.lower() != ".fst":
        raise ValueError("Provide a global channel index and .fst destination")
    source = project.read_bytes()
    image = preset_image(source, channel_index, template.read_bytes())
    # Export is a new artifact; exclusive creation avoids destroying its source.
    with destination.open("xb") as stream:
        stream.write(image)
    actual = destination.read_bytes()
    if actual != image:
        raise OSError("The exported preset did not read back exactly")
    return {"status": "exported", "preset_path": str(destination), "channel_index": channel_index,
            "source_project": str(project), "source_sha256": hashlib.sha256(source).hexdigest(),
            "preset_sha256": hashlib.sha256(actual).hexdigest(), "size_bytes": len(actual),
            "state_basis": "saved_project_file", "live_plugin_state_verified": False,
            "external_assets_copied": False,
            "message": "Saved generator state exported. External plugin files remain referenced; load and inspect to verify setup."}


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_extract_generator_preset(project_path: str, channel_index: int,
                                          template_path: str, destination_path: str) -> GeneratorPresetToolResult:
        """Export a saved project's generator setup as a new .fst file, without changing FL.

        Uses the channel's global index in that saved file. Unsaved changes are not
        included. template_path is an installed generator database .fst providing
        FL's preset envelope. Destination must be new; existing files are preserved.
        Plugin state stays opaque: external samples/plugin project files remain
        referenced at their original paths. This is not a portable asset package.
        Insert with fl_add_generator, then restore a configured VST2 bank with
        fl_load_generator_state; insertion alone does not prove state restoration.
        Verify musical behavior afterward.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: extract_preset(project_path, channel_index, template_path, destination_path)))
