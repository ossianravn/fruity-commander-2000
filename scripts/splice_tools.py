"""MCP access to the owned library without an unrelated workspace or UI handoff."""

import json
import os
from pathlib import Path
import subprocess
import sys

import anyio
from pydantic import Field
from typing import Annotated

from scripts.mcp_results import structured_result
from scripts.splice_library import SpliceSearch, search_owned
from scripts.splice_results import SpliceSearchToolResult, SpliceDownloadToolResult


def download_owned(file_hash, database_path=None, app_asar=None, timeout_seconds=30):
    command = [sys.executable, "-X", "utf8", "-B", "-m", "scripts.splice_download", file_hash,
               "--timeout-seconds", str(timeout_seconds)]
    for flag, value in (("--database-path", database_path), ("--app-asar", app_asar)):
        if value:
            command.extend([flag, value])
    try:
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, encoding="utf-8", timeout=timeout_seconds + 60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("Splice download outcome unknown; inspect the catalog/file before another request") from error
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def register(server):
    @server.mcp.tool(annotations=server.READ_ONLY)
    async def splice_search_owned(request: SpliceSearch) -> SpliceSearchToolResult:
        """Search the user's owned Splice Desktop library, including sounds not yet downloaded.

        query is literal text in name/tags/pack; tags are exact and all must match.
        key uses Splice's stored spelling. local/cloud filter recorded paths; trust
        file_exists before using one. Pagination is limit/offset. No purchases,
        credits, network, or FL changes. Metadata freshness follows Desktop sync.
        """
        return structured_result(await anyio.to_thread.run_sync(lambda: search_owned(request)))

    @server.mcp.tool(annotations=server.MUTATING)
    async def splice_download_owned(file_hash: str, database_path: str | None = None,
                                     app_asar: str | None = None,
                                     timeout_seconds: Annotated[float, Field(gt=0)] = 30) -> SpliceDownloadToolResult:
        """Get one selected owned WAV via Splice Desktop; no purchase operation is used.

        Use file_hash from splice_search_owned. Reuses an existing hash-verified file;
        missing files need signed-in/running Splice Desktop and optional Splice dependencies.
        Verifies decoded audio/hash and compares credits for a download. unverified
        means inspect the returned evidence before continuing. Does not import into FL.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: download_owned(file_hash, database_path, app_asar, timeout_seconds)))
