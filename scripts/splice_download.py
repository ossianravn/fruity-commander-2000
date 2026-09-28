"""Selected owned downloads via Splice Desktop, adapted from mpc-sample's probe.

Runs in a short-lived process so generated protobuf descriptors from app updates
cannot conflict in the long-running MCP server. No purchase or account-token API.
"""

import argparse
import importlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time

from scripts.sample_import import audio_file
from scripts.splice_library import owned_sample, support_directory


def installed_archive(explicit=None):
    if explicit:
        path = Path(explicit).resolve()
    else:
        command = "Get-AppxPackage -Name Splice | Select-Object -ExpandProperty InstallLocation"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        roots = result.stdout.strip().splitlines()
        if len(roots) != 1:
            raise ValueError("Cannot identify one installed Splice package; provide app_asar")
        path = Path(roots[0]) / "resources/app.asar"
    if not path.is_file():
        raise ValueError(f"Splice app archive is unavailable: {path}")
    return path


def load_protocol(archive, output):
    from grpc_tools import protoc
    with archive.open("rb") as stream:
        _, header_size, _, json_size = struct.unpack("<4I", stream.read(16))
        header = json.loads(stream.read(json_size))
        entry = header["files"]["proto"]["files"]["app.proto"]
        stream.seek(8 + header_size + int(entry["offset"]))
        schema = stream.read(entry["size"])
    schema_path = output / "app.proto"
    schema_path.write_bytes(schema)
    if protoc.main(["grpc_tools.protoc", f"-I{output}", f"--python_out={output}", str(schema_path)]):
        raise RuntimeError("Splice protocol compilation failed")
    sys.path.insert(0, str(output))
    return importlib.import_module("app_pb2")


def rpc(channel, method, request, response_type):
    return channel.unary_unary(f"/proto.App/{method}",
        request_serializer=lambda value: value.SerializeToString(),
        response_deserializer=response_type.FromString)(request, timeout=10)


def download(file_hash, *, database_path=None, app_asar=None, timeout_seconds=30):
    owned = owned_sample(file_hash, database_path)
    if owned["local_path"] and Path(owned["local_path"]).is_file():
        audio = audio_file(owned["local_path"])
        if audio["sha256"] == file_hash:
            return {"status": "available", "method": "existing_owned_file", "file_hash": file_hash,
                    "owned_before_request": True, "file": audio, "hash_matches_catalog": True,
                    "credits_before": None, "credits_after": None, "credits_checked": False}
    import grpc
    support, archive = support_directory(), installed_archive(app_asar)
    address = (support / "port.conf").read_text(encoding="utf-8").strip()
    certificate = (support / ".certs/cert.pem").read_bytes()
    credentials = grpc.ssl_channel_credentials(root_certificates=certificate)
    with tempfile.TemporaryDirectory(prefix="fruity-splice-") as temp:
        pb = load_protocol(archive, Path(temp))
        with grpc.secure_channel(address, credentials) as channel:
            def credits():
                reply = rpc(channel, "ValidateLogin", pb.ValidateLoginRequest(), pb.ValidateLoginResponse)
                if not reply.HasField("User"):
                    raise RuntimeError("Sign in to Splice Desktop before downloading owned sounds")
                return reply.User.Credits

            before = credits()
            rpc(channel, "DownloadSample", pb.DownloadSampleRequest(FileHash=file_hash), pb.DownloadSampleResponse)
            deadline = time.monotonic() + timeout_seconds
            while True:
                reply = rpc(channel, "SampleInfo", pb.SampleInfoRequest(FileHash=file_hash), pb.SampleInfoResponse)
                if reply.HasField("Sample") and reply.Sample.LocalPath and Path(reply.Sample.LocalPath).is_file():
                    path = reply.Sample.LocalPath
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("Splice accepted the download but no file appeared; inspect before requesting again")
                time.sleep(0.5)
            after = credits()
    audio = audio_file(path)
    verified = audio["sha256"] == file_hash and before == after
    return {"status": "downloaded" if verified else "unverified", "method": "Splice Desktop DownloadSample",
            "file_hash": file_hash, "owned_before_request": True, "file": audio,
            "hash_matches_catalog": audio["sha256"] == file_hash,
            "credits_before": before, "credits_after": after, "credits_checked": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file_hash")
    parser.add_argument("--database-path")
    parser.add_argument("--app-asar")
    parser.add_argument("--timeout-seconds", type=float, default=30)
    options = vars(parser.parse_args())
    try:
        result = download(**options)
    except ImportError:
        raise SystemExit("Install optional requirements-splice.txt in the Fruity Commander runtime")
    except Exception as error:
        # Keep this process boundary's failure explicit; no retries or token output.
        raise SystemExit(f"Splice download failed ({type(error).__name__}): {error}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
