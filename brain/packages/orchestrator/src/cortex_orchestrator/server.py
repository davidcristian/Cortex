"""BrainService hosted on grpc.aio: Health plus the Converse conversation loop.

A thin service shell per AGENTS.md. Turn logic lives in cortex_core's TurnEngine
and the stream mechanics in `converse.py`; this module only binds them to the wire.
State never lives in this process beyond the in-flight turn (the one hard rule).
"""

import asyncio
import logging
import signal
from collections.abc import AsyncGenerator, AsyncIterator

from grpc import aio

from cortex_core import TurnEngine
from cortex_orchestrator.config import SeamServerConfig
from cortex_orchestrator.converse import converse
from cortex_seam import (
    BrainServiceServicer,
    ClientEvent,
    HealthReply,
    HealthRequest,
    ServerEvent,
    add_BrainServiceServicer_to_server,
)

ORCHESTRATOR_VERSION = "0.0.0"
_SHUTDOWN_GRACE_SECONDS = 5.0
# SIGTERM is what `docker compose down` delivers (via init); SIGINT covers Ctrl-C runs.
# The brain only runs on dockerized Linux (AGENTS.md), so loop signal handlers always work.
_HANDLED_SIGNALS = (signal.SIGTERM, signal.SIGINT)
_logger = logging.getLogger(__name__)


class BrainService(BrainServiceServicer):
    """The brain's side of the seam (proto/body.proto BrainService).

    Constructed with the turn engine by the composition root (`wiring.py` in
    production, tests otherwise). DI stays at the edge, the service holds no state.
    """

    def __init__(self, engine: TurnEngine) -> None:
        self._engine = engine

    async def Health(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: HealthRequest,
        context: aio.ServicerContext[HealthRequest, HealthReply],
    ) -> HealthReply:
        """Report readiness so the overlay can display connection state."""
        del request, context  # part of the generated servicer signature; unused here
        return HealthReply(ready=True, detail=f"cortex-orchestrator {ORCHESTRATOR_VERSION}")

    async def Converse(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request_iterator: AsyncIterator[ClientEvent],
        context: aio.ServicerContext[ClientEvent, ServerEvent],
    ) -> AsyncGenerator[ServerEvent, None]:
        """Stream the conversation loop; contract and cancel semantics: `converse.py`.

        `UserTurn.images` are ignored in this slice (multimodal arrives with vision,
        Slice 10). Failures surface as a terminal SeamError event, never as an RPC error.
        """
        del context  # RPC cancellation/disconnect arrive as generator close, not via context
        events = converse(self._engine, request_iterator)
        try:
            async for event in events:
                yield event
        finally:
            # Runs on normal end, RPC cancel, and client disconnect alike: closing the
            # stream tears down its pump task and any in-flight turn deterministically.
            await events.aclose()


def create_server(config: SeamServerConfig, engine: TurnEngine) -> tuple[aio.Server, int]:
    """Build the aio server, register BrainService over `engine`, and bind it (not started).

    Returns the server plus the actually-bound port (useful when config.port is 0).
    """
    server = aio.server()
    add_BrainServiceServicer_to_server(BrainService(engine), server)
    bound_port = server.add_insecure_port(config.bind_address)
    return server, bound_port


async def serve(config: SeamServerConfig, engine: TurnEngine) -> None:
    """Run the seam server until SIGTERM/SIGINT or cancellation; always stop gracefully.

    Signal handlers are installed on the running loop for the server's lifetime and
    removed on the way out; either signal (or cancelling this coroutine) drains in-flight
    RPCs for up to the shutdown grace period before the listener closes.
    """
    server, bound_port = create_server(config, engine)
    await server.start()
    _logger.info("seam server listening", extra={"host": config.host, "port": bound_port})
    loop = asyncio.get_running_loop()
    stop_requested = asyncio.Event()
    for signum in _HANDLED_SIGNALS:
        loop.add_signal_handler(signum, stop_requested.set)
    try:
        await stop_requested.wait()
    finally:
        for signum in _HANDLED_SIGNALS:
            loop.remove_signal_handler(signum)
        await server.stop(grace=_SHUTDOWN_GRACE_SECONDS)
