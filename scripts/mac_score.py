"""Start the owned score runtime on macOS with signed receipts and one user step.

No qualified macOS route selects an FL Piano Roll script programmatically. Once
per FL launch the user runs Postfader Apply from the Piano Roll script menu; the
staged bootstrap changes no notes and returns a signed receipt. A marker then
records that FL launch, so later MCP processes rerun the same script with FL's
run-last-script shortcut. FL exposes no macOS readback of its last-run script:
running another Piano Roll script in between makes that shortcut run it instead.
"""

import json

from fl_studio_mcp import creative

from scripts import mac_host


MARKER_NAME = ".fruity-commander-macos-arm.json"
MENU_PATH = "Scripts > Postfader > Postfader Apply"


class ScoreRuntimeNeedsUser(ValueError):
    """FL needs a one-time user action before the owned score runtime can start."""


def marker_path():
    return creative.piano_roll_scripts_directory() / MARKER_NAME


def launch_identity(process):
    return {"process_id": process["pid"], "launched": process["launched"]}


def read_marker():
    try:
        value = json.loads(marker_path().read_text(encoding="ascii"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def staged_receipt_verified(registry):
    """Accept only the receipt of this process's latest staged bootstrap."""
    path = registry._arm_receipt_path
    if registry._armed or not registry._prepared or path is None or not path.is_file():
        return False
    verified, _ = creative._await_arm_receipt(
        path, receipt_secret=registry._arm_receipt_secret, request_id=registry._arm_request_id)
    return verified


def instruction(reason=None):
    message = ("macOS needs one action in FL Studio before Fruity Commander can read or "
               "edit notes (once per FL launch): in the open Piano Roll, choose "
               f"{MENU_PATH}. It changes no notes. Then repeat the request; later "
               f"edits rerun it automatically with {mac_host.RUN_LAST_SCRIPT}. "
               "If this repeats after running it, FL's script runtime could not "
               "return its receipt; report that rather than retrying edits.")
    return f"{message} Automatic rerun was not confirmed: {reason}" if reason else message


def arm(registry, prepare):
    """Caller holds the dispatch and registry locks and has opened the target editor."""
    process = mac_host.running_fl()
    identity = launch_identity(process)
    if staged_receipt_verified(registry):
        return armed(identity, "macos_user_ran_script")
    prepare(registry)
    if read_marker() != identity:
        raise ScoreRuntimeNeedsUser(instruction())
    dispatch = mac_host.trigger_run_last_script(process)
    if not dispatch.hotkey_dispatched:
        raise ScoreRuntimeNeedsUser(instruction(dispatch.error))
    verified, error = creative._await_arm_receipt(
        registry._arm_receipt_path, receipt_secret=registry._arm_receipt_secret,
        request_id=registry._arm_request_id)
    if not verified:
        raise ScoreRuntimeNeedsUser(instruction(error or "no signed receipt"))
    return armed(identity, "macos_rerun_last_script")


def script_path():
    return creative.piano_roll_scripts_directory() / creative.PIANO_ROLL_SCRIPT_NAME


def armed(identity, route):
    """Record the FL launch whose last-run script is ours; the caller arms the registry."""
    creative._atomic_text(marker_path(), json.dumps(identity, sort_keys=True))
    return {"script_path": str(script_path()), "startup_route": route}


def run_owned_score_script():
    """Rerun the armed script on the focused editor; the receipt is the evidence."""
    dispatch = mac_host.trigger_run_last_script()
    if not dispatch.hotkey_dispatched:
        raise RuntimeError(dispatch.error or "FL's run-last-script shortcut was not sent")
    return {"script_path": str(script_path()), "dispatch": dispatch.model_dump(mode="json")}
