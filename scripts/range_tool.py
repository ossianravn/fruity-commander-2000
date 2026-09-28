"""Add onset-range replacement to PostFader's existing script dispatch path."""

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fl_studio_mcp import creative
from fl_studio_mcp.bridge_client import get_client

from scripts.score_startup import ensure_locked_score_session
from scripts.native_host import run_owned_score_script
from scripts.score_results import ScoreToolResult
from scripts.mcp_results import structured_result


class NewNote(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    pitch: int = Field(ge=0, le=131)
    start_qn: float = Field(ge=0)
    duration_qn: float = Field(gt=0)
    velocity: float = Field(ge=0, le=1)


class RangeReplacement(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    range_start_qn: float = Field(ge=0)
    range_end_qn: float = Field(gt=0)
    notes: list[NewNote]

    @model_validator(mode="after")
    def validate_scope(self):
        if self.range_end_qn <= self.range_start_qn:
            raise ValueError("Range end must be after start")
        if any(not self.range_start_qn <= n.start_qn < self.range_end_qn for n in self.notes):
            raise ValueError("Replacement onsets must be inside [range_start_qn, range_end_qn)")
        return self


def read_receipt(path, request_id, secret):
    envelope = json.loads(path.read_text(encoding="ascii"))
    payload = envelope["payload"]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False).encode("ascii")
    signature = hmac.new(bytes.fromhex(secret), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, envelope["hmac_sha256"]):
        raise ValueError("Range receipt signature does not match this dispatch")
    if payload["request_id"] != request_id:
        raise ValueError("Range receipt belongs to a different request")
    return payload


def dispatch_score(operation, request, channel_index, pattern_number):
    with creative._PIANO_ROLL_DISPATCH_LOCK:
        return dispatch_locked_score(operation, request, channel_index, pattern_number)


def dispatch_locked_score(operation, request, channel_index, pattern_number, session=None):
    """Dispatch while the caller holds PostFader's score-operation lock."""
    ensure_locked_score_session(channel_index, pattern_number)
    if session is not None:
        creative._writable_preflight(session_fingerprint=session)
    target = creative._target_piano_roll(channel_index, pattern_number)
    if session is not None and target.session_fingerprint != session:
        raise ValueError("Project changed after pattern preparation")
    if not target.selected_target_verified or not target.piano_roll_visibility_verified:
        raise ValueError("FL could not establish the requested Piano Roll target")
    request_id, secret = secrets.token_hex(16), secrets.token_hex(32)
    script = creative.piano_roll_scripts_directory() / creative.PIANO_ROLL_SCRIPT_NAME
    receipt = creative._piano_roll_receipt_path(script, request_id, phase="apply")
    fields = {"OPERATION": operation, "REQUEST": request, "REQUEST_ID": request_id,
              "SECRET": secret, "RECEIPT_PATH": str(receipt)}
    runtime = Path(__file__).with_name("range_runtime.py").read_text(encoding="utf-8")
    source = Path(__file__).with_name("range_entry.pyscript").read_text(encoding="utf-8")
    # Only validated data and local paths precede the maintained script body.
    prefix = "\n".join(f"{key} = {ascii(value)}" for key, value in fields.items())
    creative._atomic_text(script, prefix + "\n" + runtime + "\n" + source)
    result = {"request_id": request_id, "channel_index": channel_index,
              "pattern_number": pattern_number, "project_saved": False,
              "verification": "none", "status": "pending"}
    try:
        run_owned_score_script()
    except (OSError, RuntimeError, ValueError) as error:
        return {**result, "status": "unknown", "message": str(error),
                "next_action": "Inspect the score and native execution error before another edit; do not resend."}
    deadline = time.monotonic() + creative.PIANO_ROLL_RECEIPT_WAIT_SECONDS
    while True:
        try:
            observed = read_receipt(receipt, request_id, secret)
            break
        except (OSError, ValueError, KeyError, TypeError) as error:
            if time.monotonic() >= deadline:
                return {**result, "status": "unknown", "message": str(error),
                        "next_action": "Call piano_roll_inspect_score; do not resend the mutation."}
            time.sleep(0.05)
    verification = ("host_readback" if all(key in observed for key in ("ppq", "notes", "markers"))
                    else "host_receipt")
    result.update(observed=observed, status=observed["status"],
                  message=observed["message"], verification=verification)
    try:
        after = get_client().call("creative.piano_roll_target")
        unchanged = (after["channel_indices"] == [channel_index]
                     and after["pattern_number"] == pattern_number
                     and after["session_fingerprint"] == target.session_fingerprint)
        if not unchanged:
            raise ValueError("The editor target changed during score operation")
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        result.update(status="unknown", verification="none", message=str(error),
                      next_action="Inspect both the target and score before any further edit.")
    return result


def replace_range(request, channel_index, pattern_number):
    return dispatch_score("replace_range", request.model_dump(mode="json"),
                          channel_index, pattern_number)


def register(server):
    @server.mcp.tool(annotations=server.WORKFLOW_STATE)
    def piano_roll_inspect_score(channel_index: int, pattern_number: int) -> ScoreToolResult:
        """Inspect all target notes and raw timeline markers through FL's score runtime.

        Selects the target editor; does not change musical data or save the project.
        Requires the upstream editor-selection write mode. Automatically starts
        the owned script through the native helper, including first selection.
        FL can add undo history and mark the project dirty when running scripts.
        Use the outer status/verification; observed is a possibly incomplete script
        receipt. host_receipt does not establish a complete score readback.
        """
        return structured_result(dispatch_score("inspect_score", {}, channel_index, pattern_number))

    @server.mcp.tool(annotations=server.MUTATING)
    def piano_roll_replace_range(
        request: RangeReplacement, channel_index: int, pattern_number: int,
    ) -> ScoreToolResult:
        """Replace only note onsets in [start,end), measured in quarter notes.

        Read the score first. Notes outside the interval retain their original
        host objects and expression. Note times are relative to pattern start;
        velocities are normalized 0..1. Readback shows FL's timing/value quantization.
        Requires write mode; automatically starts
        the owned script through the native helper, including first selection.
        Does not alter pattern extent, automation, or save FLP.
        Use the outer status/verification; an unknown outcome overrides any retained
        observed receipt. host_receipt does not establish a complete score readback.
        """
        return structured_result(replace_range(request, channel_index, pattern_number))
