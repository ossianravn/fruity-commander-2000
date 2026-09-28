"""Import local WAVs through FL's native channel loader and inspect actual sources."""

import hashlib
from pathlib import Path
from typing import Literal

import anyio
import soundfile
from fl_studio_mcp import creative

from scripts.mcp_results import structured_result
from scripts.native_host import NativeExecutionError, dispatch
from scripts.project_save_as import same_path
from scripts.sample_results import SampleImportToolResult, SampleSourceToolResult
from scripts.windows_samples import SampleReader, inspect_sample


def audio_file(sample_path):
    path = Path(sample_path)
    if not path.is_absolute() or path.suffix.lower() != ".wav" or not path.is_file():
        raise ValueError("Provide an existing absolute WAV sample path")
    path = path.resolve()
    with soundfile.SoundFile(path) as audio:
        if audio.format not in ("WAV", "WAVEX", "RF64") or audio.frames <= 0:
            raise ValueError("The source must contain WAV audio")
        info = {"frames": audio.frames, "sample_rate": audio.samplerate,
                "channels": audio.channels, "duration_seconds": audio.frames / audio.samplerate}
        # Decode before mutating FL; metadata alone does not establish a valid file.
        for _ in audio.blocks(blocksize=65536):
            pass
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "sha256": digest, **info}


def import_sample(sample_path, session_fingerprint=None, kind="sampler"):
    if kind not in ("sampler", "audio_clip"):
        raise ValueError("Choose sampler or audio_clip")
    file = audio_file(sample_path)
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        client, _, session = creative._writable_preflight(session_fingerprint=session_fingerprint)
        before = client.call("channels.list", global_count=True)
        count = before["channel_count"]
        result = {"status": "unknown", "verification": "none", "file": file,
                  "session_fingerprint": session, "project_saved": False, "automatic_retry": False,
                  "external_assets_copied": False, "playback_verified": False}
        with SampleReader() as reader:
            identity = reader.identity()
            objects = reader.channel_objects()
            arrangement = reader.snapshot()
            payload = b""
            if kind == "audio_clip":
                preset = reader.engine.parent / "Data/Patches/Plugin database/Generators/Misc/Audio Clip.fst"
                if not preset.is_file():
                    raise ValueError(f"FL Audio Clip factory preset is unavailable: {preset}")
                payload = (str(preset) + "\0").encode("utf-16-le")
            try:
                result["native"] = dispatch(reader.window, reader.pid, 9 if kind == "sampler" else 11,
                    path=file["path"], payload=payload, project=identity["path"] or "",
                    expected_channels=count, timeout_ms=60000)
            except NativeExecutionError as error:
                result.update(native=error.evidence, message=str(error))
            except (OSError, ValueError, RuntimeError) as error:
                result["message"] = str(error)
            try:
                after = client.call("channels.list", global_count=True)
                result["observed_channel_count"] = after["channel_count"]
                if reader.identity() != identity or client.ping().get("session_fingerprint") != session:
                    raise ValueError("Project changed during sample import")
                if after["channel_count"] == count + 1:
                    result["source"] = reader.source(count)
                    result["channel"] = after["channels"][count]
                    unchanged = (reader.channel_objects()[:count] == objects
                                 and reader.snapshot() == arrangement)
                    source = result["source"]
                    if (unchanged and source["kind"] == kind and source["file_exists"]
                            and same_path(source["resolved_path"], file["path"])):
                        return {**result, "status": "imported",
                                "verification": "native_sample_path_and_channel_readback"}
                result["status"] = "partial" if result.get("native", {}).get("stage", 0) else "unknown"
                result.setdefault("message", "The requested source and preserved arrangement were not verified")
            except (OSError, ValueError, RuntimeError, KeyError) as error:
                result["message"] = str(error)
            result["next_action"] = "Inspect channels and sample source before another import; do not resend."
            return result


def register(server):
    @server.mcp.tool(annotations=server.MUTATING)
    async def fl_import_sample(sample_path: str,
                               session_fingerprint: str | None = None,
                               kind: Literal["sampler", "audio_clip"] = "sampler") -> SampleImportToolResult:
        """Import a local WAV as a new Sampler or Audio Clip channel.

        Requires write mode. Reads FL's actual sample path and new channel identity;
        never retries insertion. References the existing file, without copying it.
        For one-shots use sampler, sequence source.channel_index with piano_roll_create_pattern,
        then place its pattern. For timeline audio use audio_clip then fl_place_audio_clip.
        Does not prove playback, place a clip, adjust source tempo, or save the project.
        Inspect partial/unknown outcomes before continuing.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: import_sample(sample_path, session_fingerprint, kind)))

    @server.mcp.tool(annotations=server.READ_ONLY)
    async def fl_inspect_sample(channel_index: int) -> SampleSourceToolResult:
        """Read a Sampler/Audio Clip channel's actual source file, including after reopening.

        Identity and file existence do not establish decoded playback or audible quality.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: inspect_sample(channel_index)))
