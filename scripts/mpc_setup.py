"""Enable MPC Beats MIDI mapping once, with FL and MPC closed, on Windows.

This configures a persisted preference; it does not inspect a live plugin or
create its project-specific CC assignments. All other file bytes are preserved.
"""

import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree


APPLICATIONS = {"fl.exe", "fl64.exe", "fl studio.exe", "mpc beats.exe", "mpc.exe", "ilbridge.exe"}
SETTING = re.compile(rb'<VALUE\s+name=(["\'])MidiLearnEnabled\1\s+val=(["\'])([01])\2\s*/>')


def enabled_settings(content):
    root = ElementTree.fromstring(content)
    entries = root.findall("./VALUE[@name='MidiLearnEnabled']")
    if root.tag != "PROPERTIES" or len(entries) != 1 or entries[0].get("val") not in {"0", "1"}:
        raise ValueError("MPC settings do not contain one recognized MidiLearnEnabled preference")
    if entries[0].get("val") == "1":
        return content
    matches = list(SETTING.finditer(content))
    if len(matches) != 1:
        raise ValueError("MPC preference layout differs from the qualified format; file unchanged")
    match = matches[0]
    result = content[:match.start(3)] + b"1" + content[match.end(3):]
    observed = ElementTree.fromstring(result).find("./VALUE[@name='MidiLearnEnabled']")
    if observed.get("val") != "1":
        raise ValueError("Could not update the intended MPC preference; file unchanged")
    return result


def running_applications():
    # Same Windows tasklist/CSV mechanism as pinned PostFader's setup wizard.
    result = subprocess.run(["tasklist.exe", "/FO", "CSV", "/NH"],
                            capture_output=True, text=True, check=True)
    return sorted({row[0] for row in csv.reader(result.stdout.splitlines())
                   if row and row[0].casefold() in APPLICATIONS})


def enable_mapping(settings_path):
    if sys.platform != "win32":
        raise OSError("This MPC preference setup is qualified on Windows only")
    running = running_applications()
    if running:
        raise RuntimeError("Close FL and MPC normally before setup: " + ", ".join(running)
                           + ". Their in-memory preferences can overwrite a file edit on exit.")
    path = Path(settings_path)
    before = path.read_bytes()
    after = enabled_settings(before)
    if after == before:
        return {"changed": False, "path": str(path), "persisted_midi_mapping_enabled": True}
    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as stream:
            staged = Path(stream.name)
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
        staged = None
    finally:
        if staged is not None:
            staged.unlink()
    if path.read_bytes() != after:
        raise RuntimeError("MPC preference changed during setup; inspect it before another attempt")
    return {"changed": True, "path": str(path), "persisted_midi_mapping_enabled": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, help="Existing MPC Beats.settings; defaults to this user's profile")
    options = parser.parse_args()
    path = options.settings
    if path is None:
        profile = os.environ.get("APPDATA")
        if not profile:
            parser.error("APPDATA is unavailable; supply the existing settings file with --settings")
        path = Path(profile) / "Akai/MPC Beats/MPC Beats.settings"
    if not path.is_file():
        parser.exit(1, f"MPC settings not found: {path}. Launch MPC Beats once, close it normally, then run setup.\n")
    try:
        result = enable_mapping(path)
    except (OSError, RuntimeError, ValueError, ElementTree.ParseError, subprocess.SubprocessError) as error:
        parser.exit(1, f"MPC setup failed: {error}\n")
    print(f"{'Enabled' if result['changed'] else 'Already enabled'}: MPC MIDI mapping for the next launch.")
    print("Project CC assignments and actual instrument response still need verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
