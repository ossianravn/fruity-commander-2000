# Fruity Commander on macOS (preview)

Read this whenever `fl_get_capabilities` reports macOS routes, a tool error says
"no macOS route", or the user is on a Mac. The Mac preview has no recorded
real-Mac qualification yet; report what actually happened, including failures.

## What works through MCP

- Connection, project/channel/pattern/mixer/transport reads and control, plugin
  parameter scans and changes: PostFader tools over the IAC MIDI bus.
- Editable notes with the owned tools: `piano_roll_create_pattern`,
  `piano_roll_inspect_score`, `piano_roll_replace_range`, `piano_roll_start_session`.
- Named instruments and mixer effects from FL's Add menu: `plugins_list_available`,
  then `plugins_load` with the exact listed name (`kind="instrument"`, or
  `kind="effect"` with `track_index`). It verifies the new channel or effect slot.

## One user step per FL launch for notes

macOS has no qualified route to select an FL Piano Roll script programmatically,
so the user does it once each time FL starts. The first note tool call after FL
starts returns an error beginning "ONE-TIME STEP IN FL STUDIO". Stop and give the
user these steps in chat as a short numbered list, then wait for their reply:

1. In FL Studio, find the Piano Roll window Fruity Commander just opened.
2. Click the wrench (Tools) icon at the top of that Piano Roll (or Piano Roll
   menu › Tools).
3. Choose **Script…** › **Postfader** › **Postfader Apply** (may show as
   Postfader_Apply). It changes no notes.
4. Reply here when done.

Say they can use the computer meanwhile. After their reply, repeat the same call;
no pattern was created before the step. Later calls rerun the script with
Cmd+Opt+Y until FL restarts.

- If the step returns after the user ran it, FL's script runtime could not report
  back. Tell the user; do not loop.
- Cmd+Opt+Y needs Accessibility permission for the app running this server. A
  permission error names the System Settings change; relay it, then stop.
- If the user runs another Piano Roll script, Cmd+Opt+Y would run that script.
  Ask them to choose Postfader Apply again before the next note edit.

## Windows-only for now

These owned tools return "no macOS route is implemented yet":
`fl_create_automation_clip`, `fl_replace_automation_points`,
`fl_inspect_native_arrangement`, `fl_place_pattern_clip`,
`fl_set_playlist_time_selection`, `fl_import_sample`, `fl_inspect_sample`,
`fl_place_audio_clip`, `fl_list_installed_generators`, `fl_add_generator`,
`fl_load_generator_state`, `fl_list_installed_effects`, `fl_add_mixer_effect`,
`fl_get_project_file`, `fl_save_project`, `fl_save_project_as`.

- Tell the user plainly which requested step is not available on Mac yet.
- Never substitute recorded events or a streamed knob sweep for a requested
  Automation Clip, and never ask the user to do the agent's work by hand unless
  they choose to. Offer what is available: notes, instruments, mixing, playback.
- Saving: ask the user to save in FL (Cmd+S, or File › Save as for a new file).
  Do not claim the project was saved.
- Pattern placement in the Playlist and Song mode arrangement are not available
  yet; Pattern mode playback (`fl_set_loop_mode(loop_mode="pattern")`) auditions
  a pattern.
