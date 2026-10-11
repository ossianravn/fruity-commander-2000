"""Resume the owned score script automatically, with actual execution evidence."""

import anyio
import secrets
from fl_studio_mcp import creative
from fl_studio_mcp.bridge_client import get_client

from scripts import mac_score
from scripts.host_platform import is_macos
from scripts.native_host import run_owned_score_script
from scripts.score_results import ScoreStartupToolResult
from scripts.mcp_results import structured_result


def prepare_locked(registry):
    """Stage the upstream bootstrap while our caller already owns dispatch."""
    with registry._lock:
        path = creative.piano_roll_scripts_directory() / creative.PIANO_ROLL_SCRIPT_NAME
        request_id, secret = secrets.token_hex(16), secrets.token_hex(32)
        receipt = creative._piano_roll_receipt_path(path, request_id, phase="arm")
        script = creative._bootstrap_script(request_id=request_id, receipt_path=receipt,
                                             receipt_secret=secret)
        creative._atomic_text(path, script)
        registry._prepared, registry._armed = True, False
        registry._arm_request_id = request_id
        registry._arm_receipt_secret = secret
        registry._arm_receipt_path = receipt


def run_score_script():
    """Run the staged owned script on the focused editor through this OS's route."""
    if is_macos():
        return mac_score.run_owned_score_script()
    return run_owned_score_script()


def start_runtime(registry):
    """Stage and run the bootstrap; Windows selects it natively, macOS needs one user run."""
    if is_macos():
        return mac_score.arm(registry, prepare_locked)
    prepare_locked(registry)
    execution = run_owned_score_script()
    verified, error = creative._await_arm_receipt(
        registry._arm_receipt_path, receipt_secret=registry._arm_receipt_secret,
        request_id=registry._arm_request_id)
    if not verified:
        raise ValueError(error or "FL did not return signed score startup proof")
    return {"script_path": execution["script_path"], "startup_route": "native_helper"}


def ensure_locked_score_session(channel_index, pattern_number):
    """Caller owns the dependency's non-reentrant dispatch lock."""
    registry = creative.PIANO_ROLL
    with registry._lock:
        if registry.status().armed_this_session:
            return {"ready": True, "verification": "earlier_signed_receipt_this_process"}
        target = creative._target_piano_roll(channel_index, pattern_number, navigation_only=True)
        if not target.selected_target_verified or not target.piano_roll_visibility_verified:
            raise ValueError("FL did not establish the score target for automatic startup")
        execution = start_runtime(registry)
        after = get_client().call("creative.piano_roll_target")
        if (after["channel_indices"] != [channel_index]
                or after["pattern_number"] != pattern_number
                or after["session_fingerprint"] != target.session_fingerprint):
            raise ValueError("FL target changed during automatic score startup")
        registry._armed = True
        return {"ready": True, "verification": "signed_host_bootstrap_receipt",
                "startup_route": execution["startup_route"],
                "script_path": execution["script_path"], "channel_index": channel_index,
                "pattern_number": pattern_number,
                "session_fingerprint": target.session_fingerprint}


def ensure_score_session(channel_index, pattern_number):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        return ensure_locked_score_session(channel_index, pattern_number)


def register(server):
    @server.mcp.tool(annotations=server.WORKFLOW_STATE)
    async def piano_roll_start_session(channel_index: int, pattern_number: int) -> ScoreStartupToolResult:
        """Start this MCP process's score runtime with a signed host receipt.

        Windows selects the owned script by its actual inventory path on the
        qualified build through the native helper; no prior selection is needed.
        macOS needs the user to run Postfader Apply from the Piano Roll script
        menu once per FL launch; the error explains it, later runs are automatic.
        Retargets the editor, then runs a no-note-change bootstrap through FL's
        own script runtime.
        FL can add undo history and mark the project dirty when running scripts.
        Owned note tools call this automatically when the process is unarmed.
        An earlier receipt establishes runtime readiness for this process, not
        a fresh observation of the requested editor target or score contents.
        """
        return structured_result(await anyio.to_thread.run_sync(
            lambda: ensure_score_session(channel_index, pattern_number)))
