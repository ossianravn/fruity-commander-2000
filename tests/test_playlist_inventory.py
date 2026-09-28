"""Targeted Playlist reads preserve host identity, state and inventory metadata."""

from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch

from mcp.server.mcpserver.exceptions import ToolError
from fl_studio_mcp.track_b_contracts import PlaylistTrackList, PlaylistTrackSummary
from scripts.postfader_server import prepare_server


class PlaylistInventoryTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = prepare_server()

    def observation(self):
        return PlaylistTrackList(
            observed_at=datetime.now(timezone.utc), total_track_count=6,
            tracks=[PlaylistTrackSummary(track_index=i, name=f'Track {i}',
                muted=i == 5, soloed=i == 2, selected=i == 6, activity_level=0.25)
                for i in range(1, 7)], project_dirty_flag=1, warnings=['Fixture warning'],
        )

    async def test_selected_rows_keep_original_state_and_default_keeps_full_inventory(self):
        observed = self.observation()
        expected = observed.model_dump(mode='json')
        with patch.object(self.server, '_performance_read',
                          new=AsyncMock(return_value=observed)) as read:
            full = await self.server.mcp.call_tool('fl_list_playlist_tracks', {})
            self.assertEqual(full.structured_content, expected)
            selected = await self.server.mcp.call_tool('fl_list_playlist_tracks',
                                                     {'track_indices': [5, 2, 5]})
            expected['tracks'] = [expected['tracks'][1], expected['tracks'][4]]
            self.assertEqual(selected.structured_content, expected)
            self.assertEqual(len(observed.tracks), 6)  # The source snapshot is untouched.
            self.assertEqual(read.await_count, 2)
            read.assert_awaited_with('list_playlist_tracks')

    async def test_missing_requested_track_is_not_silently_returned_as_a_partial_match(self):
        with patch.object(self.server, '_performance_read',
                          new=AsyncMock(return_value=self.observation())):
            with self.assertRaisesRegex(ToolError, 'Playlist tracks not found: 7'):
                await self.server.mcp.call_tool('fl_list_playlist_tracks',
                                               {'track_indices': [2, 7]})


if __name__ == '__main__':
    unittest.main()
