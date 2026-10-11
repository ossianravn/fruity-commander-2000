"""Collect read-only macOS facts that decide Fruity Commander's remaining Mac routes.

Run on the Mac with FL Studio open. It changes no FL, MIDI or system setting,
clicks no menu and presses no key. Home-directory paths are written as ~.
The report includes FL window titles, which can contain the open project's name.
"""

import argparse
import json
import os
import platform
import plistlib
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from scripts import mac_host


HOME = str(Path.home())
SPLICE_CANDIDATES = ("~/Library/Application Support/com.splice.Splice",
                     "~/Library/Application Support/Splice",
                     "~/Library/Application Support/SpliceSettings")
SIGNING_FIELDS = ("Identifier", "Format", "CodeDirectory", "TeamIdentifier",
                  "Runtime Version", "Authority")

# Reads names and accessibility attributes only; nothing is clicked or typed.
_UI_FACTS = r'''
function run(argv) {
    var se = Application('System Events');
    var out = {ui_scripting: se.uiElementsEnabled()};
    var procs = se.applicationProcesses.whose({unixId: Number(argv[0])})();
    if (procs.length !== 1) { out.error = 'FL process is not visible to System Events'; return JSON.stringify(out); }
    var fl = procs[0];
    out.process_name = fl.name();
    try { out.menu_bar = fl.menuBars()[0].menuBarItems.name(); } catch (e) { out.menu_error = String(e); }
    try {  // Script entries here could let a later version select the score script itself.
        var tools = fl.menuBars()[0].menuBarItems().filter(function (m) { return /^tools$/i.test(m.name()); });
        out.tools_menu = tools.length ? tools[0].menus[0].menuItems().map(function (item) {
            var sub = /script/i.test(item.name() || '') && item.menus().length
                ? item.menus[0].menuItems.name() : undefined;
            return {name: item.name(), script_items: sub};
        }) : null;
    } catch (e) { out.tools_menu_error = String(e); }
    try {
        out.windows = fl.windows().map(function (w) {
            var row = {title: w.name()};
            try { row.document = w.attributes.byName('AXDocument').value(); }
            catch (e) { row.document_error = String(e); }
            return row;
        });
    } catch (e) { out.window_error = String(e); }
    return JSON.stringify(out);
}
'''


def redact(value):
    if isinstance(value, str):
        return value.replace(HOME, "~")
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    return value


def run(*command, timeout=30):
    try:
        done = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)}
    return {"returncode": done.returncode, "stdout": done.stdout,
            "stderr": done.stderr.decode("utf-8", "replace")[-4000:]}


def text(*command):
    result = run(*command)
    return result["stdout"].decode("utf-8", "replace").strip() if "stdout" in result else None


def guarded(collect):
    try:
        return collect()
    except Exception as error:  # A probe reports every failure and continues.
        return {"error": f"{type(error).__name__}: {error}"[:1024]}


def system_facts():
    return {"macos": text("sw_vers", "-productVersion"), "build": text("sw_vers", "-buildVersion"),
            "hardware": text("uname", "-m"), "rosetta": text("sysctl", "-n", "sysctl.proc_translated"),
            "python": sys.version.split()[0], "python_architecture": platform.machine(),
            "python_executable": sys.executable,
            "packages": {name: guarded(lambda name=name: metadata.version(name))
                         for name in ("postfader-fl-studio-mcp", "python-rtmidi", "mcp")}}


def entitlements(executable):
    for flag in ("--xml", None):
        command = ["codesign", "-d", "--entitlements", "-" if flag else ":-"]
        result = run(*command, *([flag] if flag else []), str(executable))
        data = result.get("stdout") or b""
        start = data.find(b"<?xml")
        if result.get("returncode") == 0 and start >= 0:
            return plistlib.loads(data[start:])
        if result.get("returncode") == 0 and not data.strip():
            return {}
    return {"error": result.get("stderr") or result.get("error")}


def signing(executable):
    lines = run("codesign", "-dv", "--verbose=2", str(executable)).get("stderr", "").splitlines()
    return [line for line in lines if line.startswith(SIGNING_FIELDS)]


def plugin_databases(bundle):
    found = []
    for directory, children, _ in os.walk(bundle / "Contents"):
        depth = len(Path(directory).relative_to(bundle).parts)
        if Path(directory).name == "Plugin database":
            found.append(str(Path(directory).relative_to(bundle)))
            children.clear()
        elif depth >= 7:
            children.clear()
    return found


def installation(bundle):
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    executable = bundle / "Contents/MacOS" / info.get("CFBundleExecutable", "")
    return {"bundle": str(bundle), "identifier": info.get("CFBundleIdentifier"),
            "version": info.get("CFBundleShortVersionString"), "build": info.get("CFBundleVersion"),
            "executable_architectures": text("lipo", "-archs", str(executable)),
            "signing": guarded(lambda: signing(executable)),
            "entitlements": guarded(lambda: entitlements(executable)),
            "plugin_databases": guarded(lambda: plugin_databases(bundle))}


def installations():
    roots = [Path("/Applications"), Path.home() / "Applications"]
    bundles = sorted(path for root in roots if root.is_dir() for path in root.glob("FL Studio*.app"))
    return [guarded(lambda bundle=bundle: installation(bundle)) for bundle in bundles]


def running():
    rows = mac_host.fl_processes()
    ui = (guarded(lambda: mac_host.osascript(_UI_FACTS, rows[0]["pid"]))
          if len(rows) == 1 else None)
    return {"processes": rows, "ui": ui}


def user_data():
    from fl_studio_mcp import bridge_install, creative
    from fl_studio_mcp.host_config import fl_studio_user_data_dir
    from scripts.controller_deployment import configure, expected_deployment
    from scripts.mac_score import marker_path

    root = fl_studio_user_data_dir()
    configure()
    controller = bridge_install.target_path(str(root))
    scripts = creative.piano_roll_scripts_directory()
    return {"path": str(root), "exists": root.is_dir(),
            "hardware": (root / "Settings/Hardware").is_dir(),
            "controller_deployed": controller.is_file(),
            "controller_current": controller.is_file()
                                  and controller.read_bytes() == expected_deployment()[0],
            "score_scripts": sorted(path.name for path in scripts.glob("*.pyscript"))
                             if scripts.is_dir() else None,
            "score_arm_marker": marker_path().is_file()}


def midi_ports():
    import rtmidi

    inputs, outputs = rtmidi.MidiIn(), rtmidi.MidiOut()
    try:
        return {"inputs": inputs.get_ports(), "outputs": outputs.get_ports()}
    finally:
        inputs.delete()
        outputs.delete()


def splice():
    rows = {}
    app = Path("/Applications/Splice.app/Contents/Info.plist")
    if app.is_file():
        rows["app_version"] = plistlib.loads(app.read_bytes()).get("CFBundleShortVersionString")
    for candidate in SPLICE_CANDIDATES:
        root = Path(candidate).expanduser()
        if root.is_dir():
            rows[candidate] = {"children": sorted(path.name for path in root.iterdir())[:40],
                               "catalogs": sorted(str(path.relative_to(root))
                                                  for path in root.glob("**/sounds.db"))[:10]}
    return rows


def collect():
    return redact({"probe_version": 1, "system": guarded(system_facts),
                   "fl_installations": guarded(installations), "fl_running": guarded(running),
                   "permission_issues": guarded(mac_host.permission_issues),
                   "user_data": guarded(user_data),
                   "midi": guarded(midi_ports), "splice": guarded(splice)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-data-dir", help="FL user-data folder; otherwise configured/default")
    parser.add_argument("--output", type=Path, default=Path("fruity-commander-mac-probe.json"))
    options = parser.parse_args()
    if sys.platform != "darwin":
        parser.exit(2, "Run this probe on the Mac that runs FL Studio.\n")
    if options.user_data_dir:
        # Every resolver (controller, score scripts) reads the same configured folder.
        os.environ["FL_STUDIO_USER_DATA_DIR"] = str(Path(options.user_data_dir).expanduser().resolve())
    report = collect()
    options.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {options.output.resolve()}. Review it, then send it to the developer.")
    print("Nothing in FL Studio or macOS settings was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
