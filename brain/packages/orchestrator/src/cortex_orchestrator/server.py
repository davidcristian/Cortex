"""BrainService hosted on grpc.aio: Health is live; Converse lands in Slice 3.

A thin service shell per AGENTS.md. Orchestration logic belongs in cortex_core
(this slice has none). State never lives in this process beyond a single RPC.
"""

import asyncio
import logging
import signal
from collections.abc import AsyncIterator

import grpc
from grpc import aio

from cortex_orchestrator.config import SeamServerConfig
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
    """The brain's side of the seam (proto/body.proto BrainService)."""

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
    ) -> None:
        """Abort UNIMPLEMENTED until the conversation loop arrives in Slice 3."""
        del request_iterator  # part of the generated servicer signature; unused here
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "Converse is not implemented yet; it arrives with Slice 3 (docs/ROADMAP.md).",
        )


def create_server(config: SeamServerConfig) -> tuple[aio.Server, int]:
    """Build the aio server, register BrainService, and bind it (not yet started).

    Returns the server plus the actually-bound port (useful when config.port is 0).
    """
    server = aio.server()
    add_BrainServiceServicer_to_server(BrainService(), server)
    bound_port = server.add_insecure_port(config.bind_address)
    return server, bound_port


async def serve(config: SeamServerConfig) -> None:
    """Run the seam server until SIGTERM/SIGINT or cancellation; always stop gracefully.

    Signal handlers are installed on the running loop for the server's lifetime and
    removed on the way out; either signal (or cancelling this coroutine) drains in-flight
    RPCs for up to the shutdown grace period before the listener closes.
    """
    server, bound_port = create_server(config)
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
