"""Align all capability-report callers with owned operations and current host evidence."""

from fl_studio_mcp import readonly_inspector
from fl_studio_mcp.contracts import CapabilityEvidence, CapabilityRecord

from scripts.host_platform import family
from scripts.mac_capabilities import macos_report
from scripts.native_host import DLL_PATH
from scripts.windows_project import ProjectReader


def native_context():
    try:
        with ProjectReader() as reader:
            identity = reader.identity()
        return identity, None
    except (OSError, RuntimeError, ValueError) as error:
        return None, str(error)


def owned_report(report, identity, error, helper_present):
    connected = report.connection.connected and report.connection.compatible
    readable = connected and identity is not None
    writable = readable and helper_present
    limits = [] if readable else [error or report.connection.error or "Connect FL before using native operations."]
    host = ([CapabilityEvidence(kind="live_read_only_test",
             detail=f"Current project identity read on qualified engine {identity['engine_sha256']}.")]
            if identity else [])
    def record(name, path, mutate=False, partial=False, needs_helper=False, caveats=()):
        ready = writable if needs_helper else readable
        status = ("partial" if partial else "available") if ready else "unvalidated"
        helper_limits = (["Build the owned native helper with scripts/build_native.ps1."]
                         if needs_helper and not helper_present else [])
        return CapabilityRecord(capability=name, status=status, access_path=path,
            mutates_project=mutate,
            limitations=[*limits, *helper_limits, *caveats,
                         *(["Requires existing write mode for edits."] if mutate else [])],
            evidence=[*host, CapabilityEvidence(kind="fixture_test",
                detail="Owned route qualified on FL26.1.6.5639; current read does not execute or verify a new edit.")])

    replacements = {
        "playlist_clip_enumeration": record("playlist_clip_enumeration", "fl_inspect_native_arrangement"),
        "automation_curve_inspection_and_crud": record("automation_curve_inspection_and_crud",
            "fl_inspect_native_arrangement / fl_create_automation_clip / fl_replace_automation_points",
            mutate=True, partial=True, needs_helper=True,
            caveats=["Linear creation and same-extent source revision; all source copies share edits. Other shapes, extent edits and delete are not implemented."]),
        "piano_roll_note_snapshot": record("piano_roll_note_snapshot", "piano_roll_inspect_score",
            mutate=True, needs_helper=True,
            caveats=["Automatic owned script startup; editor preparation/inspection can add undo history and dirty state without changing notes."]),
    }
    additions = [
        record("editable_note_creation_and_range_revision", "piano_roll_create_pattern / piano_roll_replace_range",
               mutate=True, needs_helper=True),
        record("native_pattern_placement", "fl_place_pattern_clip", mutate=True, needs_helper=True),
        record("native_playlist_time_selection", "fl_set_playlist_time_selection", mutate=True, needs_helper=True),
        record("project_save", "fl_get_project_file / fl_save_project", mutate=True,
               caveats=["Save verifies completed FLP write, not reopening."]),
        record("native_project_save_as", "fl_save_project_as", mutate=True, needs_helper=True,
               caveats=["Explicit destination; native writer/path adoption independent of focus and first-save dialogs."]),
        record("native_generator_loading_and_setup", "fl_list_installed_generators / fl_add_generator / fl_load_generator_state",
               mutate=True, partial=True, needs_helper=True,
               caveats=["Configured VST2 bank route qualified; internal program selection, other state formats and external assets need separate handling. Verify sound separately."]),
        record("native_mixer_effect_loading", "fl_list_installed_effects / fl_add_mixer_effect",
               mutate=True, needs_helper=True,
               caveats=["Installed .fst into an explicit empty mixer slot; preserves existing effects and routing. Parameter setup, sends, playback and saving are separate operations."]),
        record("sample_import_and_placement", "fl_import_sample / fl_inspect_sample / fl_place_audio_clip",
               mutate=True, needs_helper=True,
               caveats=["WAV as Sampler or Audio Clip; external files stay referenced. Placement does not fit tempo. Verify playback and persistence separately."]),
    ]
    return report.model_copy(update={"capabilities": [replacements.get(row.capability, row)
        for row in report.capabilities] + additions})


def install():
    original = readonly_inspector.ReadOnlyInspector.capabilities
    if getattr(original, "_fruity_owned", False):
        return

    def capabilities(self):
        report = original(self)
        if family() != "windows":
            # Never open Win32 resources off Windows; report each route's actual status.
            return macos_report(report, macos=family() == "macos")
        identity, error = native_context()
        return owned_report(report, identity, error, DLL_PATH.is_file())

    capabilities._fruity_owned = True
    readonly_inspector.ReadOnlyInspector.capabilities = capabilities
