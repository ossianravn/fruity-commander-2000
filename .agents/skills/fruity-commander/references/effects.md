# Load and use mixer effects

1. Inspect the intended mixer track with `fl_inspect_mixer_track(track_index)`.
   Track indices are zero-based; track 0 is Master. Effect slots are zero-based
   0..9 in tools and displayed as 1..10 in FL. Retain occupied slots and routing.
2. Discover the installed effect with `fl_list_installed_effects(query)` and
   resolve an exact preset path/name. Use `fl_add_mixer_effect(track_index,
   slot_index, preset_path, expected_plugin_name)` for an empty slot on Windows.
   These owned tools supply Windows discovery/loading; the inherited
   `plugins_load`/`plugins_list_available` describe their Mac menu implementation.
3. Continue from a `loaded` result with actual effect identity and preserved mixer
   state. Retain the observed name, mixer track and slot for subsequent controls.
   Inspect partial/unknown results before deciding on another insertion.
4. Discover the loaded effect's controls with `plugins_scan_parameters` or
   `plugins_inspect_parameter_map`; set them through `fl_set_plugin_param` using
   `target={"kind":"mixer_effect", "track_index":..., "slot_index":...}`.
   Use `expected_before` when checking a value read just before writing. Use observed parameter names,
   normalized values and display strings; physical units need verified conversion.
5. For a send bus, use `fl_set_mixer_send` and `fl_set_mixer_send_level` with the
   intended source/destination. Inspect existing routes first and retain the dry
   path when the musical request calls for parallel processing. Verify route and
   parameter readback, then audition the relevant span and save the finished edit.

Insertion establishes plugin identity, not its musical settings, an audible effect,
or persistence. Meters establish signal; listening and save/reopen are separate checks.
