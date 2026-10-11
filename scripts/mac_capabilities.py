"""Report owned operations truthfully on macOS, where the Windows helper cannot run."""

from fl_studio_mcp.contracts import CapabilityEvidence, CapabilityRecord


ASSISTED_SCORE = (
    "macOS: the user runs Postfader Apply from the Piano Roll script menu once per FL "
    "launch; later runs use Cmd+Opt+Y, which needs Accessibility permission for the "
    "app running this server. Running another Piano Roll script in between makes "
    "Cmd+Opt+Y run that script instead.")
NO_MAC_ROUTE = ("Windows native-helper operation; no macOS route is implemented yet. "
                "Report the gap instead of substituting another representation.")
OTHER_OS = "Fruity Commander implements host routes for Windows and macOS only."
MANUAL_SAVE = "Until then, ask the user to save in FL (Cmd+S or File > Save as)."
ADD_MENU = ("PostFader's named Add-menu route: Accessibility permission and English FL "
            "menus; verifies the new channel or slot. Preset (.fst) and instrument "
            "state loading remain Windows-only.")
EVIDENCE = CapabilityEvidence(kind="fixture_test",
    detail="macOS route selection is covered by fixture tests; no Fruity Commander run "
           "on a real Mac has been recorded yet.")

# capability: (access path, mutates, implemented on macOS, extra limitations)
REPLACED = {
    "playlist_clip_enumeration": ("fl_inspect_native_arrangement", False, False,
        ["fl_list_playlist_tracks still reads track names and mute/solo state."]),
    "automation_curve_inspection_and_crud": (
        "fl_inspect_native_arrangement / fl_create_automation_clip / fl_replace_automation_points",
        True, False, ["Do not substitute recorded events or streamed knob moves for a requested Automation Clip."]),
    "piano_roll_note_snapshot": ("piano_roll_inspect_score", True, True, [ASSISTED_SCORE]),
}
ADDED = {
    "editable_note_creation_and_range_revision": (
        "piano_roll_create_pattern / piano_roll_replace_range", True, True, [ASSISTED_SCORE]),
    "native_pattern_placement": ("fl_place_pattern_clip", True, False, []),
    "native_playlist_time_selection": ("fl_set_playlist_time_selection", True, False, []),
    "project_save": ("fl_get_project_file / fl_save_project", True, False, [MANUAL_SAVE]),
    "native_project_save_as": ("fl_save_project_as", True, False, [MANUAL_SAVE]),
    "native_generator_loading_and_setup": (
        "fl_list_installed_generators / fl_add_generator / fl_load_generator_state", True, False,
        ["Use macos_add_menu_plugin_loading for named instruments."]),
    "native_mixer_effect_loading": ("fl_list_installed_effects / fl_add_mixer_effect", True, False,
        ["Use macos_add_menu_plugin_loading for named mixer effects."]),
    "sample_import_and_placement": (
        "fl_import_sample / fl_inspect_sample / fl_place_audio_clip", True, False, []),
    "macos_add_menu_plugin_loading": (
        "plugins_list_available / plugins_load", True, True, [ADD_MENU]),
}


def record(name, spec, connected, macos=True):
    path, mutate, implemented, extra = spec
    implemented = implemented and macos
    if not macos:
        status, limits, extra = "unavailable", [OTHER_OS], []
    elif not implemented:
        status, limits = "unavailable", [NO_MAC_ROUTE]
    else:
        status = "unvalidated"
        limits = [] if connected else ["Connect FL through the IAC bus before using this route."]
    return CapabilityRecord(capability=name, status=status, access_path=path,
        mutates_project=mutate,
        limitations=[*limits, *extra, *(["Requires existing write mode for edits."]
                                        if mutate and implemented else [])],
        evidence=[EVIDENCE])


def macos_report(report, macos=True):
    """macos=False reports every owned route unavailable on an unsupported OS."""
    connected = report.connection.connected and report.connection.compatible
    rows = [record(row.capability, REPLACED[row.capability], connected, macos)
            if row.capability in REPLACED else row for row in report.capabilities]
    rows += [record(name, spec, connected, macos) for name, spec in ADDED.items()]
    return report.model_copy(update={"capabilities": rows})
