# Choose and use samples

Use these MCP tools in the installed `fruity-commander` connection. No separate
sample project, desktop automation, or user import handoff is needed.

1. For owned Splice sounds, call `splice_search_owned(request={...})`. Search
   `query` as literal text in filename/tags/pack; `tags` are exact and all must
   match. Filter `sample_type`, key/mode or BPM as useful. Use limit/offset for
   pagination. This searches owned metadata, including sounds not downloaded.
   `availability` describes recorded paths; `file_exists` checks the actual file.
2. Select using the musical request. `splice_download_owned(file_hash=...)`
   verifies an existing local WAV or downloads the selected owned file through
   signed-in Splice Desktop. No purchase operation is exposed. An actual download
   compares credits, hashes the file and decodes it. Use `file.path` from a result
   with status `available` or `downloaded`; inspect `unverified` before continuing.
   Existing-file reuse does not query credits. Download needs the optional Splice
   dependencies; read [setup](setup.md) for a specific connection/dependency failure.
3. For a one-shot or pitched sample, call `fl_import_sample(sample_path=...,
   kind="sampler")`. Use `source.channel_index` for `piano_roll_create_pattern`.
   A new Sampler's normal root note is FL C5/MIDI60; other pitches transpose it.
   Inspect notes, then place the pattern with `fl_place_pattern_clip`.
4. For timeline audio, import with `kind="audio_clip"`, then call
   `fl_place_audio_clip(request={channel_index, expected_source_path, track,
   start_qn, length_qn})`. Use the returned source's `resolved_path`. Track is
   one-based; timing uses quarter notes. Length controls the visible source window
   from zero. It does not automatically stretch a loop to the song tempo. Account
   for source BPM/duration when choosing placement; don't claim tempo fitting.
5. `fl_inspect_sample(channel_index=...)` independently reads FL's actual sample
   path and kind, including after reopening. Import success verifies source and
   channel identity. Play the intended span in Song mode and inspect meters for
   signal; neither a path nor meters establish listening-based musical quality.
6. Save with `fl_save_project` or an explicit `fl_save_project_as` destination.
   Files remain referenced at their existing locations. Saving an FLP does not
   collect/copy external samples. Keep those files available for later reopening.

Inspect partial/unknown imports and placements before further edits; do not repeat
a request merely because its acknowledgement is missing. The returned channel or
clip may already exist. Missing capabilities need a plugin/connection update or a
specific diagnosis, not approval for routine sample loading.

Current qualification: Windows FL26.1.6.5639 and Splice Desktop5.4.13. macOS support
is planned separately. Other audio formats, sample replacement, automatic tempo
fitting and collecting project assets are not implemented by these new operations.
