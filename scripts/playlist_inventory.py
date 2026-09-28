"""Select requested Playlist rows at the MCP result boundary."""

from typing import Annotated

from pydantic import Field
from fl_studio_mcp.track_b_contracts import PlaylistTrackList


def register(server):
    server.mcp.remove_tool('fl_list_playlist_tracks')

    @server.mcp.tool(name='fl_list_playlist_tracks', annotations=server.READ_ONLY.model_copy(
        update={'title': 'List Playlist tracks'}))
    async def fl_list_playlist_tracks(
        track_indices: Annotated[list[Annotated[int, Field(ge=1)]] | None, Field(
            description='One-based Playlist tracks to return. Omit or use null for all tracks; '
                        'an empty list selects none. Duplicates are returned once in host order.',
        )] = None,
    ) -> PlaylistTrackList:
        """Read names, mute/solo state and other controllable state of Playlist tracks.

        Pass track_indices for specific tracks instead of returning the full
        inventory. total_track_count always describes the entire host Playlist;
        tracks contains the selected rows in host order. Missing requested tracks
        are an error, not a partial match. Omitting the selection preserves the
        complete inventory. Clip placement, source links and automation points
        come from fl_inspect_native_arrangement, not this track-state listing.
        """
        observed = await server._performance_read('list_playlist_tracks')
        if track_indices is None:
            return observed
        requested = set(track_indices)
        missing = requested.difference(row.track_index for row in observed.tracks)
        if missing:
            raise ValueError('Playlist tracks not found: ' + ', '.join(map(str, sorted(missing))))
        return observed.model_copy(update={
            'tracks': [row for row in observed.tracks if row.track_index in requested],
        })
