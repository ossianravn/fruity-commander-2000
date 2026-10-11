"""Target the running macOS FL process through osascript; never screen coordinates.

Process identity uses NSRunningApplication, which needs no privacy permission.
Bringing FL forward and sending its run-last-script shortcut use System Events:
the application that launched this MCP server needs Accessibility permission
(and macOS asks once to let it control System Events). The bundle identifier
was observed by pinned PostFader on FL 26.1.3 for macOS; qualify it per build.
"""

import json
import os
import subprocess

from fl_studio_mcp.creative import HotkeyDispatch


FL_BUNDLE_ID = "com.image-line.flstudio"
RUN_LAST_SCRIPT = "Cmd+Opt+Y"
ARCHITECTURES = {0x0100000C: "arm64", 0x01000007: "x86_64"}
# Apple Events not authorized, assistive access disabled, keystrokes not allowed.
PERMISSION_ERRORS = ("-1743", "-1719", "-25211", "(1002)")
PERMISSION_HINT = ("In System Settings > Privacy & Security, allow the app running this MCP "
                   "server (Claude, Codex or Terminal) under Accessibility and let it control "
                   "System Events under Automation, then restart that app.")

# Arguments travel through argv as JSON or numbers, never interpolated into source.
_PROCESSES = r'''
ObjC.import('AppKit');
function run(argv) {
    var apps = $.NSRunningApplication.runningApplicationsWithBundleIdentifier(argv[0]);
    var rows = [];
    for (var i = 0; i < apps.count; i++) {
        var app = apps.objectAtIndex(i);
        var date = app.launchDate;
        rows.push({pid: app.processIdentifier, name: ObjC.unwrap(app.localizedName),
                   launched: date.isNil() ? null : date.timeIntervalSince1970,
                   bundle_path: ObjC.unwrap(app.bundleURL.path),
                   architecture: app.executableArchitecture});
    }
    return JSON.stringify(rows);
}
'''

_FRONT_AND_KEY = r'''
function run(argv) {
    var pid = Number(argv[0]);
    var press = argv[1] === 'press';
    var se = Application('System Events');
    var matches = se.applicationProcesses.whose({unixId: pid})();
    if (matches.length !== 1) throw Error('FL Studio process ' + pid + ' is not visible to System Events');
    var fl = matches[0];
    fl.frontmost = true;
    delay(0.4);
    if (!fl.frontmost()) throw Error('macOS did not bring FL Studio to the front');
    if (press) se.keystroke('y', {using: ['command down', 'option down']});
    return JSON.stringify({frontmost: true, pressed: press});
}
'''

_UI_SCRIPTING = r'''
function run() {
    return JSON.stringify({enabled: Application('System Events').uiElementsEnabled()});
}
'''


def osascript(source, *arguments, timeout=15):
    if os.environ.get("FL_BRIDGE_SANDBOXED") == "1":
        raise RuntimeError("Desktop automation is disabled in the offline environment")
    try:
        completed = subprocess.run(["osascript", "-l", "JavaScript", "-e", source,
                                    *map(str, arguments)],
                                   capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        # A timed-out script may still have acted; callers never resend on their own.
        raise RuntimeError(f"osascript did not finish within {timeout} s") from error
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "osascript failed").strip()
        if any(code in detail for code in PERMISSION_ERRORS):
            detail += " " + PERMISSION_HINT
        raise RuntimeError(detail[:1024])
    return json.loads(completed.stdout)


def fl_processes():
    rows = osascript(_PROCESSES, FL_BUNDLE_ID)
    return [{**row, "architecture": ARCHITECTURES.get(row.get("architecture"),
                                                      row.get("architecture"))}
            for row in rows]


def running_fl():
    """Return the one running FL process; its launch time identifies this FL session."""
    rows = fl_processes()
    if len(rows) != 1:
        raise RuntimeError(f"Expected one running FL Studio; found {len(rows)}")
    return rows[0]


def focus_fl(process=None):
    process = process or running_fl()
    osascript(_FRONT_AND_KEY, process["pid"], "focus")
    return process


def trigger_run_last_script(process=None):
    """Press FL's run-last-script shortcut only while FL is verified frontmost."""
    found = False
    try:
        process = process or running_fl()
        found = True
        osascript(_FRONT_AND_KEY, process["pid"], "press")
    except (OSError, RuntimeError, ValueError) as error:
        return HotkeyDispatch(platform="macos", shortcut=RUN_LAST_SCRIPT,
                              fl_window_found=found, fl_window_focused=False,
                              hotkey_dispatched=False, error=str(error)[:512])
    return HotkeyDispatch(platform="macos", shortcut=RUN_LAST_SCRIPT,
                          fl_window_found=True, fl_window_focused=True,
                          hotkey_dispatched=True)


def permission_issues():
    """Check UI scripting for the app running this process; other apps need their own grant."""
    try:
        enabled = osascript(_UI_SCRIPTING)["enabled"]
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        return [f"Could not confirm macOS automation permission: {error}"[:1024]]
    return [] if enabled is True else ["Accessibility is off for the app running this check. "
                                       + PERMISSION_HINT]
