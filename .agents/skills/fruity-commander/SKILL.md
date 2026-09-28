---
name: fruity-commander
description: Use Fruity Commander MCP to inspect FL Studio, choose owned Splice sounds, import WAVs, load generators, create or revise editable patterns, place audio and automation, control VSTs, and save projects.
---

# FL Studio workflow

Use the `fruity-commander` MCP connection. For connection/setup failures, read
[setup](references/setup.md). Discover current operation contracts through MCP;
use `fl_get_capabilities` when host support or readiness needs checking.
Fixture pitches, tempo, and lengths are examples; compose from
the user's request and current project. Required musical actions use MCP across
agent harnesses. Historical Computer Use proofs do not supply missing operations.

For samples, owned Splice sounds, drum kits or audio loops, read
[sample workflow](references/samples.md). It covers owned search/download, WAV import
as a Sampler or Audio Clip, sequencing/placement, and source persistence checks.

Use native lookup within Fruity Commander. First return matching paths only:
`search({query: "..."}).items.map(item => item.path)`.
Select an exact returned path before emitting its signature; other search hits
remain candidates, even when the query is an exact tool name. For that selected
tool, use its complete native contract directly when it supplies the arguments,
units and effects. Use the selective lookup below for large input/output graphs.
Search related terms when needed; a lexical miss does not establish absence.

In a fresh or resumed OpenCode turn, first await
`tools.opencode.list_mcp_resources({server:"fruity-commander"})` and return only
the resource count. Then search in a new execute call with a refreshed catalog;
the previous turn's names can precede this connection's readiness. This lists
metadata without reading FL. If the namespace remains absent, inspect setup and
report the connection failure instead of trying guessed tool calls.

For large or incomplete native contracts, `fl_get_tool_contract(tool_name, schema_section="input")`
returns its original purpose, effects annotations, input root and reference pointers
without expanding its entire input/output graph. Read the needed definitions through
those pointers; retain required fields, defaults, units, targeting, effects and
verification. Read selected output fields/definitions when their meaning is unclear;
an unambiguous receipt does not require retrieving its entire output schema.
Full native tool definitions remain available. Reuse metadata already in context
and batch independent lookups; print each shared definition once when identical.
Keep the input root, including required argument wrappers, alongside any child
definitions. Check each proposed call against both; a child request object is
not necessarily the complete tool argument object.

Discovery is complete when every proposed step has its operation, required argument
structure, verification and uncertainty handling. Keep unknown live values explicit.
Search for exact names identified in this workflow and call names confirmed by
the current catalog; broaden for missing operations. An empty startup catalog
calls for readiness handling, not more synonyms. Project large inventories to the
requested targets and needed fields while retaining identity and verification.
Reuse current observations that already answer the question, including their
evidence limits. An equivalent resource read is another host observation, not a
different source of missing fields. Report unresolved relationships explicitly.
For ordinary music/status requests, use current host evidence and report its
limits. Repository development history is not additional live evidence. Read it
when the user asks for development work or historical qualification results.

1. Distinguish ideas from requested edits. Inspect `fl_get_project_summary`,
   `fl_list_channels`, and the relevant pattern/plugin. Retain actual channel
   indices and pattern numbers. `fl_list_patterns` preserves sparse IDs and includes
   nondefault patterns plus current/picker selections. Its host count is metadata,
   not the highest ID or necessarily the returned row count. A stale controller
   needs the deployment/reload procedure in [setup](references/setup.md).
   Project summary already contains connection and transport state. Read again
   when freshness matters; use capabilities for an unresolved host-support question.
   For requested Playlist track names/mute/solo state, use
   `fl_list_playlist_tracks(track_indices=[...])`. Its total counts all host tracks;
   returned rows are the selection. Placements/curves/links come from the arrangement.
2. For an authorized edit, use the existing `fl_set_write_mode` when needed.
   Owned creation/range/inspection tools automatically select and start their score
   runtime through the native helper, including after a cold FL launch. The server
   requires signed execution proof. `piano_roll_start_session` exposes startup
   separately without musical write mode. If the helper is missing, follow the build
   instructions in [setup](references/setup.md). Legacy upstream score tools retain their older
   shortcut/bootstrap contracts; use the owned tools below. Score inspection uses upstream selection
   write mode and can add undo history/dirty state without changing the notes.
   `piano_roll_prepare_target` establishes selection, visibility and focus separately;
   successful preparation alone does not prove score execution. Unknown outcomes
   require inspection, never automatic mutation retries.
3. Compose explicit notes with host note numbers, quarter-note onsets and
   durations, and normalized velocity. FL displays host note 60 as C5.
   Read actual PPQ; keep phrase extent independent of the last note end.
4. For a new pattern, call `piano_roll_create_pattern(request, channel_index)`.
   The request contains `name`, `phrase_length_qn`, and `notes` with `pitch`,
   `start_qn`, `duration_qn`, `velocity`. Retain its actual pattern number.
   This route uses FL's new-note defaults and a native Length marker, including
   fractional quarter notes and trailing rests. It has no note-count or phrase
   cap. Owned creation and `fl_set_pattern_identity` preserve full names. Inspect
   the returned name and verification; host alteration is unverified, never silently
   accepted or retried. Use full observed names in expected-before preconditions.
   Independently read `piano_roll_inspect_score` after creation: its ticks,
   notes, markers, and `phrase_length_qn` come from FL. Null extent means there
   is no single explicit Length marker. FL quantizes velocity on script commit;
   the later read observes that persisted value. Verify Playlist placement too.
   Avoid the upstream `length_beats` setter: it uses sixteenth-note steps here.
   Place notes using `fl_place_pattern_clip(request)`: actual `pattern_number`,
   `expected_name`, `track` (1-based), `start_qn`, `length_qn`. The source begins
   at zero. Verify the returned clip and actual playback through its endpoint.
5. For a range revision, read the target immediately before calling
   `piano_roll_replace_range(request, channel_index, pattern_number)`.
   `request` contains `range_start_qn`, `range_end_qn`, and `notes` with
   `pitch`, `start_qn`, `duration_qn`, `velocity`. Onsets are pattern-relative;
   the range is start-inclusive and end-exclusive. An empty array clears that
   onset range. The operation keeps outside host note objects and their data.
   Re-read with `piano_roll_inspect_score`, compare surrounding notes and markers.
6. Resolve controls with `plugins_scan_loaded_plugins`,
   `plugins_inspect_parameter_map`, or `plugins_scan_parameters`. Set an
   identified normalized control with `fl_set_plugin_param`; inspect its
   readback and plugin display. Use a physical/display value only when the
   plugin exposes a verified conversion. MPC's CC74 wrapper parameter is a
   MIDI controller mapped to TubeSynth LPF Cutoff, not a directly exposed synth
   parameter. Retain both identities and report 7-bit CC quantization.
7. Discover installed generator variants with `fl_list_installed_generators(query)`.
   Choose an explicit preset path and call `fl_add_generator(preset_path,
   expected_plugin_name)`. Retain the returned channel and target fingerprint.
   Insertion verifies plugin identity; it can leave internal setup blank even
   when loading a configured preset. Extract state with `fl_extract_generator_preset`
   (saved FLP, global channel index, installed .fst template, new .fst destination).
   For an existing wrapped instance, `fl_load_generator_state` accepts its fresh
   target fingerprint and configured preset path. It restores the qualified
   embedded VST2 bank; VST3 and other formats need their own route. Acceptance
   alone does not prove internal setup. On this installation a second MPC instance
   remains uninitialized; the fresh-instrument proof uses one instance. External assets
   remain referenced. Check isolated instrument output and save/reopen. Never
   retry an uncertain insertion or state load automatically.
8. Inspect `fl_inspect_native_arrangement` before automation creation. Use
   `fl_create_automation_clip(request)` with `channel_index`, `parameter_index`,
   `target_fingerprint`, `track`, `start_qn`, `length_qn` and `points` containing
   `time_qn`/`value`. The points include zero and length endpoints, with normalized
   0..1 values and linear interpolation. Obtain a fresh target fingerprint from
   `plugins_scan_loaded_plugins(include_channel_generators=true)` when needed.
   Existing curves/links remain; resolve conflicting automation from the musical
   request. Verify returned actual points, target link and placement. Native point
   storage uses floats; MIDI CC targets add their own 7-bit quantization.
   For existing curves, call `fl_replace_automation_points(request)` using the
   observed `source_event`, complete `expected_points` (including tension/curve),
   and new `points` (`time_qn`/`value`). This replaces the shared source: every
   Playlist copy changes. It preserves the endpoint, links and placements; stale
   points require a fresh inspection. Actual undo/redo and save/reopen are qualified.
   Other interpolation shapes and extent changes remain gaps. Do not silently
   substitute a streamed sweep or agent desktop action.
9. Save when requested.
   For an existing named FLP, use `fl_get_project_file` to inspect its actual path
   and `fl_save_project` to save and verify a completed file rewrite. For an explicit
   new destination, use `fl_save_project_as(destination_path)` with an absolute `.flp`
   path in an existing directory. It changes the current path and replaces an existing
   FLP there; resolve the destination from the request before calling. It does not copy
   samples. Dirty=0 and an existing file alone do not prove current edits saved.
   Native path/startup access is qualified only on the tested Windows engine binary;
   report an adapter error without requiring the user to change FL versions.
10. Audition when requested, inspect control movement, then stop playback.
   Space transport observations using `fl_get_transport_state(wait_seconds=...)`.
   Choose seconds from the remaining quarter notes and observed tempo (QN×60/BPM),
   within the client's call timeout. Check actual positions after waiting and adapt
   if tempo, loop or playback state changed. A wait returns one fresh sample; it
   does not record the interval or stop playback. Stop explicitly after the intended
   span. Saving/readback and save/reopen with disconnected playback are distinct
   evidence. Report only checks actually performed.

For `pending`, distinguish an available MCP continuation from missing implementation.
For `unknown`, inspect the
score/target before deciding on another write; never resend to check success.
For `partial`, identify completed edits and the unfinished step. Product development
may continue on independent gaps; a missing operation is not a request to switch
products or narrow the user's musical goal.

For Song playback, `fl_get_transport_state.loop_mode` is 1 (Pattern is 0); use
`fl_set_loop_mode(loop_mode="song")` when needed. Inspect
`fl_inspect_native_arrangement.time_selection`. A
Playlist time selection may loop before later clips. Set the intended range with
`fl_set_playlist_time_selection(start_qn, end_qn)`, or omit both endpoints to clear
it. This targets the Playlist even when the Piano Roll is focused. Selection does
not start playback; current transport start was observed to begin at song zero.
