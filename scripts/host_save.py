# Appended to the pinned controller. Save acknowledgement is not disk evidence.


def fc_save_project(a):
    if set(a) - {"session_fingerprint"}:
        raise ValueError("project.save accepts only session_fingerprint")
    _check_session_precondition(a)
    session = SESSION_FINGERPRINT
    before = general.getChangedFlag()
    dispatched = transport.globalTransport(midi.FPT_Save, 1)
    if dispatched == midi.GT_Cannot:
        raise ValueError("FL did not handle the save command")
    yield
    if session != SESSION_FINGERPRINT:
        raise ValueError("FL project changed while saving; inspect the project before continuing")
    return {"command": "project.save", "dispatch_result": dispatched,
            "dirty_before": before, "dirty_after": general.getChangedFlag(),
            **_precondition_report(a)}


HANDLERS["project.save"] = fc_save_project
LEAN_WRITE_COMMANDS = LEAN_WRITE_COMMANDS | {"project.save"}
