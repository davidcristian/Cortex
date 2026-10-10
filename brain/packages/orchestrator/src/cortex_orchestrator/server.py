"""BrainService hosted on grpc.aio: Health plus the Converse conversation loop."""

import asyncio
import logging
import signal
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass

import grpc
from grpc import aio

from cortex_core import (
    MAX_TURN_MESSAGE_BYTES,
    PreferenceStore,
    ResidencyReporter,
    ScheduleStore,
    ScheduleStoreError,
    ServingWatch,
    SessionMemoryCascade,
    SessionStore,
)
from cortex_orchestrator.abandon import AbandonedCallInterceptor
from cortex_orchestrator.auth import RpcTokenInterceptor
from cortex_orchestrator.config import RpcServerConfig
from cortex_orchestrator.converse import (
    DEFAULT_CONFIRM_TIMEOUT_S,
    DEFAULT_MAX_BUFFERED_EVENTS,
    EngineFactory,
)
from cortex_orchestrator.converse_stream import ConverseStream
from cortex_orchestrator.preference_servicer import PreferenceRpcMixin
from cortex_orchestrator.reminders import ack_reminder, list_due_reminders
from cortex_orchestrator.session_rpc import DEFAULT_SESSION_LIST_LIMIT, MAX_SESSION_LIST_LIMIT
from cortex_orchestrator.session_servicer import SessionRpcMixin
from cortex_seam import (
    AckReminderReply,
    AckReminderRequest,
    BrainServiceServicer,
    ClientEvent,
    HealthNote,
    HealthReply,
    HealthRequest,
    ListDueRemindersReply,
    ListDueRemindersRequest,
    ServerEvent,
    add_BrainServiceServicer_to_server,
)

ORCHESTRATOR_VERSION = "0.0.0"
# A stopping brain lets turns finish for the drain, then ends the rest within the grace. The
# brain's compose `stop_grace_period` must cover the grace plus the teardown after it.
SHUTDOWN_DRAIN_SECONDS = 3.0
_SHUTDOWN_GRACE_SECONDS = 5.0
# SIGTERM is what `docker compose down` delivers; SIGINT covers a Ctrl-C run.
_HANDLED_SIGNALS = (signal.SIGTERM, signal.SIGINT)
_logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_SESSION_LIST_LIMIT",
    "MAX_SESSION_LIST_LIMIT",
    "ORCHESTRATOR_VERSION",
    "SHUTDOWN_DRAIN_SECONDS",
    "BrainService",
    "RpcPorts",
    "create_server",
    "serve",
]


@dataclass(frozen=True, slots=True)
class RpcPorts:
    """The optional ports the server offers beyond a turn, bundled as one dependency."""

    schedules: ScheduleStore | None = None
    memory_cascade: SessionMemoryCascade | None = None
    residency: ResidencyReporter | None = None
    preferences: PreferenceStore | None = None
    serving: ServingWatch | None = None


_NO_RPC_PORTS = RpcPorts()


class BrainService(SessionRpcMixin, PreferenceRpcMixin, BrainServiceServicer):
    """The brain's side of the gRPC interface (proto/body.proto BrainService)."""

    def __init__(
        self,
        make_engine: EngineFactory,
        store: SessionStore,
        *,
        ports: RpcPorts = _NO_RPC_PORTS,
        max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
        confirm_timeout_s: float = DEFAULT_CONFIRM_TIMEOUT_S,
    ) -> None:
        self._make_engine = make_engine
        self._store = store
        self._schedules = ports.schedules
        self._memory_cascade = ports.memory_cascade
        self._residency = ports.residency
        self._preferences = ports.preferences
        self._serving = ports.serving
        self._max_buffered_events = max_buffered_events
        self._confirm_timeout_s = confirm_timeout_s
        self._streams: set[ConverseStream] = set()

    async def end_turns(self) -> None:
        """End every open `Converse` stream as a stopping brain does."""
        await asyncio.gather(*(stream.shut_down() for stream in tuple(self._streams)))

    async def Health(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: HealthRequest,
        context: aio.ServicerContext[HealthRequest, HealthReply],
    ) -> HealthReply:
        """Report readiness so the overlay can display connection state."""
        del request, context
        report = None if self._residency is None else self._residency.residency()
        if report is not None and not report.serving:
            return HealthReply(ready=False, detail=report.detail)
        fault = None if self._serving is None else self._serving.fault()
        if fault is not None:
            return HealthReply(ready=False, detail=fault)
        notes = (*(() if report is None else report.notes), *self._serving_notes())
        if notes:
            replies = [HealthNote(text=note) for note in notes]
            return HealthReply(ready=True, detail="; ".join(notes), notes=replies)
        return HealthReply(ready=True, detail=f"cortex-orchestrator {ORCHESTRATOR_VERSION}")

    def _serving_notes(self) -> tuple[str, ...]:
        return () if self._serving is None else self._serving.notes()

    async def Converse(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request_iterator: AsyncIterator[ClientEvent],
        context: aio.ServicerContext[ClientEvent, ServerEvent],
    ) -> AsyncGenerator[ServerEvent, None]:
        """Stream the conversation loop; contract and cancel semantics: `converse.py`."""
        del context  # RPC cancellation and disconnect arrive as a generator close, not here
        stream = ConverseStream(
            self._make_engine,
            max_buffered_events=self._max_buffered_events,
            confirm_timeout_s=self._confirm_timeout_s,
        )
        self._streams.add(stream)
        events = stream.events(request_iterator)
        try:
            async for event in events:
                yield event
        finally:
            self._streams.discard(stream)
            await events.aclose()

    async def ListDueReminders(  # noqa: N802 - method name is fixed by the gRPC codegen interface
        self,
        request: ListDueRemindersRequest,
        context: aio.ServicerContext[ListDueRemindersRequest, ListDueRemindersReply],
    ) -> ListDueRemindersReply:
        """Fired-but-undelivered reminders (policy + mapping in `reminders.py`)."""
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
        """Mark one fire delivered."""
        try:
            return await ack_reminder(
                self._schedules, request.reminder_id, request.fired_at_unix_ms
            )
        except ScheduleStoreError as err:
            await context.abort(grpc.StatusCode.UNAVAILABLE, str(err))


def create_server(
    config: RpcServerConfig,
    make_engine: EngineFactory,
    store: SessionStore,
    ports: RpcPorts = _NO_RPC_PORTS,
) -> tuple[aio.Server, int]:
    """Build the aio server over `make_engine`/`store` and bind it (not started)."""
    server, bound_port, _ = _build(config, make_engine, store, ports)
    return server, bound_port


def _build(
    config: RpcServerConfig,
    make_engine: EngineFactory,
    store: SessionStore,
    ports: RpcPorts,
) -> tuple[aio.Server, int, BrainService]:
    """The bound server, its port and the service it hosts."""
    guards: list[aio.ServerInterceptor] = []
    if config.token:
        guards.append(RpcTokenInterceptor(config.token))
    guards.append(AbandonedCallInterceptor())
    # gRPC's 4 MiB default would refuse a turn with one full-size attached image at the transport.
    server = aio.server(
        interceptors=guards,
        options=[("grpc.max_receive_message_length", MAX_TURN_MESSAGE_BYTES)],
    )
    service = BrainService(
        make_engine,
        store,
        ports=ports,
        max_buffered_events=config.converse_buffer,
        confirm_timeout_s=config.confirm_timeout_s,
    )
    add_BrainServiceServicer_to_server(service, server)
    bound_port = server.add_insecure_port(config.bind_address)
    return server, bound_port, service


async def serve(
    config: RpcServerConfig,
    make_engine: EngineFactory,
    store: SessionStore,
    ports: RpcPorts = _NO_RPC_PORTS,
    *,
    drain_s: float = SHUTDOWN_DRAIN_SECONDS,
) -> None:
    """Run the server until SIGTERM/SIGINT or cancellation; always stop gracefully."""
    server, bound_port, service = _build(config, make_engine, store, ports)
    await server.start()
    _logger.info("gRPC server listening", extra={"host": config.host, "port": bound_port})
    loop = asyncio.get_running_loop()
    stop_requested = asyncio.Event()
    for signum in _HANDLED_SIGNALS:
        loop.add_signal_handler(signum, stop_requested.set)
    try:
        await stop_requested.wait()
    finally:
        for signum in _HANDLED_SIGNALS:
            loop.remove_signal_handler(signum)
        await _stop(server, service, drain_s)


async def _stop(server: aio.Server, service: BrainService, drain_s: float) -> None:
    """Refuse new calls, let the turns in flight finish within `drain_s`, then end the rest."""
    stopping = asyncio.create_task(server.stop(grace=_SHUTDOWN_GRACE_SECONDS))
    done, _ = await asyncio.wait([stopping], timeout=drain_s)
    if not done:
        await service.end_turns()
    await stopping
