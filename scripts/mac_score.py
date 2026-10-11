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
    """Relay-ready steps; the path follows FL's manual (Piano roll menu > Tools > Script...)."""
    message = (
        "ONE-TIME STEP IN FL STUDIO (needed once each time FL Studio starts). "
        "Ask the user to: 1) look at the Piano Roll window Fruity Commander just opened "
        "in FL Studio; 2) click the wrench (Tools) icon at the top of that Piano Roll, "
        "or open the Piano Roll menu > Tools; 3) choose Script..., then Postfader, then "
        "Postfader Apply (it may show as Postfader_Apply); 4) reply that it is done. "
        "This changes no notes. Then repeat the same request; no pattern was created yet. "
        f"Later edits run it automatically with {mac_host.RUN_LAST_SCRIPT} until FL restarts. "
        "If this message returns after the user ran it, FL's script runtime could not "
        "report back: tell the user and stop instead of retrying.")
    return f"{message} (Automatic rerun was not confirmed: {reason})" if reason else message


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
