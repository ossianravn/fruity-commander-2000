"""Qualify registered MCP/skill discovery and a read through Codex app-server.

Uses a temporary in-memory session for MCP context; never starts a model turn
or persists a chat. Uses the installed Codex CLI's versioned JSON-RPC API.
"""

import argparse
import json
import queue
import subprocess
import threading
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-js", type=Path, required=True)
    parser.add_argument("--config", action="append", default=[],
                        help="Process-local Codex config override; repeat for multiple settings")
    parser.add_argument("--plugin-marketplace", type=Path,
                        help="Verify installed Fruity Commander plugin and its sole active server")
    parser.add_argument("--cwd", type=Path,
                        help="Client workspace; defaults to this repository")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--commands", type=Path, help="Optional JSONL tool/arguments calls, executed in order")
    mode.add_argument("--catalog-only", action="store_true",
                      help="Record tool definitions without calling FL tools or starting a model turn")
    parser.add_argument("--evidence", type=Path, help="Output JSON path")
    options = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    workspace = (options.cwd or root).resolve()
    evidence = options.evidence or root / ".local/proof/codex-connection.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    messages = queue.Queue()
    stderr = evidence.with_suffix(".stderr.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        ["node", str(options.codex_js),
         *[arg for value in options.config for arg in ("-c", value)],
         "app-server", "--stdio"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
        text=True, encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW,
    )

    def read():
        for line in process.stdout:
            messages.put(json.loads(line))
        messages.put(None)

    threading.Thread(target=read, daemon=True).start()

    def send(method, params, request_id=None):
        data = {"method": method, "params": params}
        if request_id is not None:
            data["id"] = request_id
        process.stdin.write(json.dumps(data) + "\n")
        process.stdin.flush()
        if request_id is None:
            return None
        while True:
            result = messages.get(timeout=90)
            if result is None:
                raise RuntimeError("Codex app-server exited before replying")
            if result.get("id") == request_id:
                if "error" in result:
                    raise RuntimeError(result["error"])
                return result["result"]

    results = {}
    try:
        results["client"] = send("initialize", {
            "clientInfo": {"name": "fruity_connection_probe", "version": "0.1"},
            "capabilities": {"experimentalApi": True},
        }, 1)
        send("initialized", {})
        if options.plugin_marketplace:
            results["plugin"] = send("plugin/read", {
                "marketplacePath": str(options.plugin_marketplace.resolve()),
                "pluginName": "fruity-commander-2000",
            }, 20)["plugin"]
            summary = results["plugin"]["summary"]
            if not summary["installed"] or not summary["enabled"]:
                raise RuntimeError("Fruity Commander plugin is not installed and enabled")
        skills = send("skills/list", {"cwds": [str(workspace)], "forceReload": True}, 2)
        results["skill"] = [s for entry in skills["data"] for s in entry["skills"]
                            if s["name"].split(":")[-1] == "fruity-commander"]
        print(json.dumps({"skill_discovered": bool(results["skill"])}), flush=True)
        if options.plugin_marketplace and not any(
            s.get("pluginId") == "fruity-commander-2000@" + results["plugin"]["marketplaceName"]
            and s["enabled"]
            for s in results["skill"]
        ):
            raise RuntimeError("Installed plugin workflow skill was not discovered")
        context = send("thread/start", {"cwd": str(workspace), "ephemeral": True}, 3)
        thread_id = context["thread"]["id"]
        inventory = send("mcpServerStatus/list", {
            "threadId": thread_id, "limit": 100,
            "detail": "toolsAndAuthOnly",
        }, 4)
        results["servers"] = [{"name": s["name"], "tool_count": len(s["tools"])}
                              for s in inventory["data"]]
        if options.plugin_marketplace:
            candidates = [s for s in inventory["data"]
                          if "fruity" in s["name"] and s["tools"]]
            if len(candidates) != 1:
                raise RuntimeError(f"Expected one active Fruity Commander server, found {len(candidates)}")
            server = candidates[0]
        else:
            server = next(s for s in inventory["data"] if s["name"] == "fruity-commander")
        results["server"] = server["name"]
        results["tools"] = sorted(server["tools"])
        print(json.dumps({"tool_count": len(results["tools"])}), flush=True)
        if options.catalog_only:
            results["catalog"] = server["tools"]
            results["provider_capabilities"] = send("modelProvider/capabilities/read", {}, 5)
            return
        results["read"] = send("mcpServer/tool/call", {
            "threadId": thread_id, "server": server["name"],
            "tool": "fl_get_project_summary", "arguments": {},
        }, 5)
        print(json.dumps({"read_is_error": results["read"].get("isError", False)}), flush=True)
        if results["read"].get("isError"):
            raise RuntimeError("Project read failed; inspect the evidence file")
        results["calls"] = []
        if options.commands:
            requests = [json.loads(line) for line in options.commands.read_text(encoding="utf-8").splitlines() if line.strip()]
            for index, request in enumerate(requests, 6):
                result = send("mcpServer/tool/call", {"threadId": thread_id,
                    "server": server["name"], "tool": request["tool"],
                    "arguments": request.get("arguments", {})}, index)
                results["calls"].append({"tool": request["tool"], "result": result})
                evidence.write_text(json.dumps(results, indent=2), encoding="utf-8")
                print(json.dumps({"tool": request["tool"], "is_error": result.get("isError", False)}), flush=True)
                if result.get("isError"):
                    raise RuntimeError("Tool returned an error; stopped without retry. Inspect evidence.")
    finally:
        evidence.write_text(json.dumps(results, indent=2), encoding="utf-8")
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
        stderr.close()


if __name__ == "__main__":
    main()
