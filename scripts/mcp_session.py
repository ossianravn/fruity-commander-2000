"""Keep one real PostFader MCP session alive for interactive host qualification.

Read one JSON request per stdin line: list, schema (name), call (name/arguments),
or quit. This diagnostic client preserves PostFader's process-local Piano Roll
bootstrap while UI setup takes place. It does not simulate host responses.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def emit(value, log):
    encoded = json.dumps(value, ensure_ascii=True)
    log.write(encoded + "\n")
    log.flush()
    print(encoded, flush=True)


async def run(options, log):
    environment = dict(os.environ)
    environment.update({
        "FL_STUDIO_USER_DATA_DIR": str(options.user_data.resolve()),
        "FL_BRIDGE_ENABLE_MIDI": "1",
        "FL_BRIDGE_MIDI_PORT": options.midi_port,
        "FL_BRIDGE_ENABLE_WRITES": "0",
        "PYTHONUNBUFFERED": "1",
    })
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("postfader_server.py").resolve())],
        env=environment,
    )
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            initialized = await session.initialize()
            catalog = await session.list_tools()
            tools = {tool.name: tool for tool in catalog.tools}
            emit({"ready": True,
                  "server": initialized.server_info.model_dump(mode="json"),
                  "tool_count": len(tools)}, log)
            while line := await asyncio.to_thread(sys.stdin.readline):
                try:
                    request = json.loads(line)
                    action = request["action"]
                    if action == "quit":
                        break
                    if action == "list":
                        emit({"tools": sorted(tools)}, log)
                    elif action == "schema":
                        emit(tools[request["name"]].model_dump(mode="json"), log)
                    elif action == "call":
                        result = await session.call_tool(
                            request["name"], request.get("arguments", {})
                        )
                        observed = result.structured_content
                        if observed is None:
                            observed = [item.model_dump(mode="json")
                                        for item in result.content]
                        emit({"tool": request["name"], "is_error": result.is_error,
                              "observed": observed}, log)
                    else:
                        emit({"error": f"Unknown diagnostic action: {action}"}, log)
                except (KeyError, TypeError, ValueError) as error:
                    emit({"input_error": str(error)}, log)
                except RuntimeError as error:
                    # A rejected response is an unknown outcome, never a retry.
                    emit({"tool_error": str(error), "automatic_retry": False}, log)


def main():
    # PowerShell pipes UTF-8 JSON; Windows' redirected Python stdin defaults to ANSI.
    sys.stdin.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--midi-port", required=True)
    parser.add_argument("--user-data", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    options = parser.parse_args()
    options.log.parent.mkdir(parents=True, exist_ok=True)
    with options.log.open("a", encoding="utf-8") as log:
        asyncio.run(run(options, log))


if __name__ == "__main__":
    main()
