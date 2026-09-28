"""Space transport observations without repeated bridge calls or client timers."""

from typing import Annotated

import anyio
from pydantic import Field

from fl_studio_mcp.contracts import TransportState


def register(server):
    server.mcp.remove_tool('fl_get_transport_state')

    @server.mcp.tool(name='fl_get_transport_state', annotations=server.READ_ONLY.model_copy(
        update={'title': 'Get transport state'}))
    async def fl_get_transport_state(
        wait_seconds: Annotated[float, Field(
            ge=0, allow_inf_nan=False,
            description='Seconds to wait before one fresh transport read; zero reads immediately. '
                        'Choose from the musical interval and client call timeout.',
        )] = 0,
    ) -> TransportState:
        """Read playback, recording, loop mode, position, and song length.

        loop_mode is 0 for Pattern and 1 for Song. Select either with
        fl_set_loop_mode(loop_mode='pattern' or 'song').
        Optional wait_seconds waits asynchronously before one fresh host read,
        avoiding tight polling when the client has no timer. It neither starts
        nor stops playback and does not sample the interval. Compare observed
        positions to the intended musical span; elapsed time alone is not proof
        of playback, control movement, or sound. Cancellation during the wait
        leaves transport unchanged. Default zero preserves immediate reads.
        """
        if wait_seconds:
            await anyio.sleep(wait_seconds)
        return await server._run('transport_state')
