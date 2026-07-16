"""BrainService hosted on grpc.aio: Health plus the Converse conversation loop.

A thin service shell per AGENTS.md. Turn logic lives in cortex_core's TurnEngine
and the stream mechanics in `converse.py`; this module only binds them to the wire.
State never lives in this process beyond the in-flight turn (the one hard rule).
"""

import asyncio
import logging
import signal
from collections.abc import AsyncGenerator, AsyncIterator

import grpc
from grpc import aio

from cortex_core import (
    MemoryStoreError,
    ScheduleStore,
    ScheduleStoreError,
    SessionMemoryCascade,
    SessionStore,
    SessionStoreError,
)
from cortex_orchestrator.auth import SeamTokenInterceptor
from cortex_orchestrator.config import SeamServerConfig
from cortex_orchestrator.converse import (
    DEFAULT_CONFIRM_TIMEOUT_S,
    DEFAULT_MAX_BUFFERED_EVENTS,
    EngineFactory,
    converse,
)
from cortex_orchestrator.reminders import ack_reminder, list_due_reminders
from cortex_orchestrator.session_rpc import (
    DEFAULT_SESSION_LIST_LIMIT,
    MAX_SESSION_LIST_LIMIT,
    clamp_limit,
    delete_session,
    message_to_proto,
    rename_session,
    summary_to_proto,
)
from cortex_seam import (
    AckReminderReply,
    AckReminderRequest,
    BrainServiceServicer,
    ClientEvent,
    DeleteSessionReply,
    DeleteSessionRequest,
    GetSessionMessagesReply,
    GetSessionMessagesRequest,
    HealthReply,
    HealthRequest,
    ListDueRemindersReply,
    ListDueRemindersRequest,
    ListSessionsReply,
    ListSessionsRequest,
    RenameSessionReply,
    RenameSessionRequest,
    ServerEvent,
    add_BrainServiceServicer_to_server,
)

ORCHESTRATOR_VERSION = "0.0.0"
_SHUTDOWN_GRACE_SECONDS = 5.0
# SIGTERM is what `docker compose down` delivers (via init); SIGINT covers Ctrl-C runs.
# The brain only runs on dockerized Linux (AGENTS.md), so loop signal handlers always work.
_HANDLED_SIGNALS = (signal.SIGTERM, signal.SIGINT)
_logger = logging.getLogger(__name__)

# Re-exported for the composition root and its tests; the definitions and the mapping/clamp
# helpers moved to `session_rpc.py` to keep this shell thin (the two constants stay importable
# from here for the seam's existing consumers).
__all__ = [
    "DEFAULT_SESSION_LIST_LIMIT",
    "MAX_SESSION_LIST_LIMIT",
    "ORCHESTRATOR_VERSION",
    "BrainService",
    "create_server",
    "serve",
]


class BrainService(BrainServiceServicer):
    """The brain's side of the seam (proto/body.proto BrainService).

    Constructed with the engine factory and the session store by the composition root
    (`wiring.py` in production, tests otherwise). DI stays at the edge, the service holds
    no state. The factory (ADR-0022) lets each Converse stream wire its own confirmer into
    its own engine; engines are stateless functions over the store, so per-stream
    construction costs nothing. The store is injected explicitly (the same instance the
    engines use) so the read-only session RPCs (ADR-0021) read it directly, never through
    a turn engine.
    """

    def __init__(
        self,
        make_engine: EngineFactory,
        store: SessionStore,
        *,
        schedules: ScheduleStore | None = None,
        memory_cascade: SessionMemoryCascade | None = None,
        max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
        confirm_timeout_s: float = DEFAULT_CONFIRM_TIMEOUT_S,
    ) -> None:
        self._make_engine = make_engine
        self._store = store
        self._schedules = schedules
        self._memory_cascade = memory_cascade
        self._max_buffered_events = max_buffered_events
        self._confirm_timeout_s = confirm_timeout_s

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
            self._make_engine,
            request_iterator,
            max_buffered_events=self._max_buffered_events,
            confirm_timeout_s=self._confirm_timeout_s,
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
            summaries = await self._store.list_sessions(limit=clamp_limit(request.limit))
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))
        return ListSessionsReply(sessions=[summary_to_proto(s) for s in summaries])

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
        return GetSessionMessagesReply(messages=[message_to_proto(m) for m in messages])

    async def RenameSession(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: RenameSessionRequest,
        context: aio.ServicerContext[RenameSessionRequest, RenameSessionReply],
    ) -> RenameSessionReply:
        """Rename a chat (ADR-0021 management addendum): a gated, user-only catalog write.

        The gate is structural, not the mid-turn Confirmer: this RPC is reachable only from the
        overlay's user-driven list controls, never from a model, tool, or tainted turn (it is no
        tool and never runs through the turn engine, so no injected content can trigger it). It
        persists a display title via `SessionStore.set_title` (`session_rpc.rename_session`
        bounds the label); `request.title == ""` clears the override. A `SessionStoreError`
        aborts the RPC `UNAVAILABLE`, mirroring the read RPCs.
        """
        try:
            return await rename_session(self._store, request.session_id, request.title)
        except SessionStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))

    async def DeleteSession(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: DeleteSessionRequest,
        context: aio.ServicerContext[DeleteSessionRequest, DeleteSessionReply],
    ) -> DeleteSessionReply:
        """Delete a chat and cascade to its private memories (ADR-0021): a destructive user write.

        Structural user-only gate like RenameSession; ordering and the scope-aware cascade live in
        `session_rpc.delete_session`. A `SessionStoreError`/`MemoryStoreError` aborts `UNAVAILABLE`.
        """
        try:
            return await delete_session(self._store, self._memory_cascade, request.session_id)
        except (SessionStoreError, MemoryStoreError) as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))

    async def ListDueReminders(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: ListDueRemindersRequest,
        context: aio.ServicerContext[ListDueRemindersRequest, ListDueRemindersReply],
    ) -> ListDueRemindersReply:
        """Fired-but-undelivered reminders (ADR-0025; policy + mapping in `reminders.py`).

        Benignly empty with no ScheduleStore wired; a live store's `ScheduleStoreError`
        aborts `UNAVAILABLE` (the session-reads precedent).
        """
        del request
        try:
            return await list_due_reminders(self._schedules)
        except ScheduleStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))

    async def AckReminder(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: AckReminderRequest,
        context: aio.ServicerContext[AckReminderRequest, AckReminderReply],
    ) -> AckReminderReply:
        """Mark one reminder delivered (ADR-0025). Idempotent, `acked=false` when unknown."""
        try:
            return await ack_reminder(self._schedules, request.reminder_id)
        except ScheduleStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))


def create_server(
    config: SeamServerConfig,
    make_engine: EngineFactory,
    store: SessionStore,
    *,
    schedules: ScheduleStore | None = None,
    memory_cascade: SessionMemoryCascade | None = None,
) -> tuple[aio.Server, int]:
    """Build the aio server over `make_engine`/`store` and bind it (not started).

    `store` is the same session store the engines write, injected so the read-only session
    RPCs (ADR-0021) serve it directly; `schedules` (ADR-0025, None when scheduling is off)
    backs the reminder pull RPCs the same way. `memory_cascade` (None when memory is off) lets
    `DeleteSession` forget a deleted chat's private memories. With `config.token` set, a
    `SeamTokenInterceptor` fronts every RPC (ADR-0016), the shared-secret half of assumption 5's
    posture; empty disables it. Returns the server plus the actually-bound port (config.port 0).
    """
    interceptors = (SeamTokenInterceptor(config.token),) if config.token else ()
    server = aio.server(interceptors=interceptors)
    service = BrainService(
        make_engine,
        store,
        schedules=schedules,
        memory_cascade=memory_cascade,
        max_buffered_events=config.converse_buffer,
        confirm_timeout_s=config.confirm_timeout_s,
    )
    add_BrainServiceServicer_to_server(service, server)
    bound_port = server.add_insecure_port(config.bind_address)
    return server, bound_port


async def serve(
    config: SeamServerConfig,
    make_engine: EngineFactory,
    store: SessionStore,
    *,
    schedules: ScheduleStore | None = None,
    memory_cascade: SessionMemoryCascade | None = None,
) -> None:
    """Run the seam server until SIGTERM/SIGINT or cancellation; always stop gracefully.

    Signal handlers are installed on the running loop for the server's lifetime and
    removed on the way out; either signal (or cancelling this coroutine) drains in-flight
    RPCs for up to the shutdown grace period before the listener closes.
    """
    server, bound_port = create_server(
        config, make_engine, store, schedules=schedules, memory_cascade=memory_cascade
    )
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
