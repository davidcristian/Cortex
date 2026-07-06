"""BrainService hosted on grpc.aio: Health plus the Converse conversation loop.

A thin service shell per AGENTS.md. Turn logic lives in cortex_core's TurnEngine
and the stream mechanics in `converse.py`; this module only binds them to the wire.
State never lives in this process beyond the in-flight turn (the one hard rule).
"""

import asyncio
import logging
import signal
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import datetime

import grpc
from grpc import aio

from cortex_core import Message, SessionStore, SessionStoreError, SessionSummary, TurnEngine
from cortex_orchestrator.auth import SeamTokenInterceptor
from cortex_orchestrator.config import SeamServerConfig
from cortex_orchestrator.converse import DEFAULT_MAX_BUFFERED_EVENTS, converse
from cortex_seam import (
    BrainServiceServicer,
    ClientEvent,
    GetSessionMessagesReply,
    GetSessionMessagesRequest,
    HealthReply,
    HealthRequest,
    ListSessionsReply,
    ListSessionsRequest,
    ServerEvent,
    add_BrainServiceServicer_to_server,
)
from cortex_seam import SessionMessage as SessionMessagePb
from cortex_seam import SessionSummary as SessionSummaryPb

ORCHESTRATOR_VERSION = "0.0.0"
_SHUTDOWN_GRACE_SECONDS = 5.0
# Default and hard cap for a ListSessions request's `limit` (ADR-0021); a request's 0
# (or negative) means "server default", and no client can ask for an unbounded list.
DEFAULT_SESSION_LIST_LIMIT = 50
MAX_SESSION_LIST_LIMIT = 200
# SIGTERM is what `docker compose down` delivers (via init); SIGINT covers Ctrl-C runs.
# The brain only runs on dockerized Linux (AGENTS.md), so loop signal handlers always work.
_HANDLED_SIGNALS = (signal.SIGTERM, signal.SIGINT)
_logger = logging.getLogger(__name__)


def _unix_ms(moment: datetime) -> int:
    """A tz-aware instant as unix-milliseconds (the seam's timestamp form, ADR-0021)."""
    return int(moment.timestamp() * 1000)


def _summary_to_proto(summary: SessionSummary) -> SessionSummaryPb:
    """Map a core `SessionSummary` to the wire message (ADR-0021)."""
    return SessionSummaryPb(
        session_id=summary.session_id,
        title=summary.title,
        preview=summary.preview,
        last_activity_unix_ms=_unix_ms(summary.last_activity),
    )


def _message_to_proto(message: Message) -> SessionMessagePb:
    """Map a persisted `Message` to the wire `SessionMessage` (ADR-0021)."""
    return SessionMessagePb(
        role=message.role.value,
        text=message.text,
        turn_id=message.turn_id,
        at_unix_ms=_unix_ms(message.at),
    )


def _clamp_limit(limit: int) -> int:
    """A ListSessions `limit`: 0/negative → the default, and never above the hard cap."""
    if limit <= 0:
        return DEFAULT_SESSION_LIST_LIMIT
    return min(limit, MAX_SESSION_LIST_LIMIT)


class BrainService(BrainServiceServicer):
    """The brain's side of the seam (proto/body.proto BrainService).

    Constructed with the turn engine and the session store by the composition root
    (`wiring.py` in production, tests otherwise). DI stays at the edge, the service holds
    no state. The store is injected explicitly (the same instance the engine uses) so the
    read-only session RPCs (ADR-0021) read it directly, never through the turn engine.
    """

    def __init__(
        self,
        engine: TurnEngine,
        store: SessionStore,
        *,
        max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
    ) -> None:
        self._engine = engine
        self._store = store
        self._max_buffered_events = max_buffered_events

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
        events = converse(
            self._engine, request_iterator, max_buffered_events=self._max_buffered_events
        )
        try:
            async for event in events:
                yield event
        finally:
            # Runs on normal end, RPC cancel, and client disconnect alike: closing the
            # stream tears down its pump task and any in-flight turn deterministically.
            await events.aclose()

    async def ListSessions(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: ListSessionsRequest,
        context: aio.ServicerContext[ListSessionsRequest, ListSessionsReply],
    ) -> ListSessionsReply:
        """Return recent chats, most-recently-active first (ADR-0021, `list_sessions`).

        `request.limit` is clamped (0/negative → default, capped at the hard max). A
        `SessionStoreError` aborts the RPC `UNAVAILABLE` (abort raises, so nothing after runs).
        """
        try:
            summaries = await self._store.list_sessions(limit=_clamp_limit(request.limit))
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
        return ListSessionsReply(sessions=[_summary_to_proto(s) for s in summaries])

    async def GetSessionMessages(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: GetSessionMessagesRequest,
        context: aio.ServicerContext[GetSessionMessagesRequest, GetSessionMessagesReply],
    ) -> GetSessionMessagesReply:
        """Return one session's persisted history in append order (ADR-0021, `history`).

        Only USER/ASSISTANT messages persist, so the reply is the clean dialogue; an unknown
        session is an empty history. A `SessionStoreError` aborts the RPC `UNAVAILABLE`.
        """
        try:
            messages = await self._store.history(request.session_id)
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
        return GetSessionMessagesReply(messages=[_message_to_proto(m) for m in messages])


def create_server(
    config: SeamServerConfig, engine: TurnEngine, store: SessionStore
) -> tuple[aio.Server, int]:
    """Build the aio server, register BrainService over `engine`/`store`, and bind it (not started).

    `store` is the same session store the engine writes, injected so the read-only session
    RPCs (ADR-0021) serve it directly. With `config.token` set, a `SeamTokenInterceptor`
    fronts every RPC (ADR-0016). This is the shared-secret half of assumption 5's posture; empty
    disables it (loopback-only remains the outer boundary). Returns the server plus the
    actually-bound port (useful when config.port is 0).
    """
    interceptors = (SeamTokenInterceptor(config.token),) if config.token else ()
    server = aio.server(interceptors=interceptors)
    service = BrainService(engine, store, max_buffered_events=config.converse_buffer)
    add_BrainServiceServicer_to_server(service, server)
    bound_port = server.add_insecure_port(config.bind_address)
    return server, bound_port


async def serve(config: SeamServerConfig, engine: TurnEngine, store: SessionStore) -> None:
    """Run the seam server until SIGTERM/SIGINT or cancellation; always stop gracefully.

    Signal handlers are installed on the running loop for the server's lifetime and
    removed on the way out; either signal (or cancelling this coroutine) drains in-flight
    RPCs for up to the shutdown grace period before the listener closes.
    """
    server, bound_port = create_server(config, engine, store)
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
