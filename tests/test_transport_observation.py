"""A delayed transport observation reads fresh state without keeping FL busy."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fl_studio_mcp.contracts import TransportState
from scripts.postfader_server import prepare_server


class TransportObservationTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = prepare_server()

    async def test_default_is_immediate_and_wait_reads_only_after_delay(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def wait(seconds):
            self.assertEqual(seconds, 2.5)
            entered.set()
            await release.wait()

        state = TransportState(playing=True, song_position_normalized=0.25)
        with patch.object(self.server, '_run', new=AsyncMock(return_value=state)) as read:
            immediate = await self.server.mcp.call_tool('fl_get_transport_state', {})
            self.assertFalse(immediate.is_error)
            self.assertEqual(immediate.structured_content['song_position_normalized'], 0.25)
            read.assert_awaited_once_with('transport_state')
            read.reset_mock()
            with patch('anyio.sleep', side_effect=wait):
                pending = asyncio.create_task(self.server.mcp.call_tool(
                    'fl_get_transport_state', {'wait_seconds': 2.5}))
                # Fail promptly if the old contract rejects the argument.
                await asyncio.sleep(0)
                if pending.done():
                    self.assertFalse((await pending).is_error)
                await asyncio.wait_for(entered.wait(), timeout=1)
                read.assert_not_called()
                state.song_position_normalized = 0.75
                release.set()
                observed = await pending
            self.assertFalse(observed.is_error)
            self.assertEqual(observed.structured_content['song_position_normalized'], 0.75)
            read.assert_awaited_once_with('transport_state')

    async def test_cancellation_during_wait_does_not_read_or_change_transport(self):
        entered = asyncio.Event()

        async def wait(seconds):
            entered.set()
            await asyncio.Event().wait()

        with patch.object(self.server, '_run', new=AsyncMock()) as read:
            with patch('anyio.sleep', side_effect=wait):
                pending = asyncio.create_task(self.server.mcp.call_tool(
                    'fl_get_transport_state', {'wait_seconds': 2.5}))
                await asyncio.wait_for(entered.wait(), timeout=1)
                pending.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await pending
            read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
