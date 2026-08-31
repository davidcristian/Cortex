import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import cast

import grpc
import pytest
from grpc import aio

from cortex_core import (
    EchoInferenceBackend,
    InMemorySessionStore,
    PlainFormatter,
    SessionSummary,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import (
    ABANDONED_MESSAGE,
    AbandonedCallInterceptor,
    EngineFactory,
    SeamServerConfig,
    create_server,
)
from cortex_seam import BrainServiceStub, ListSessionsReply, ListSessionsRequest

_ABANDON_LOGGER = "cortex_orchestrator.abandon"
# Longer than any real answer and far shorter than the suite's patience: the client's deadline
# is what ends these calls, so the store never wins the race.
_NEVER_S = 30.0
_ANNOUNCED_S = 0.2
# Fifty times the deadline above, so a reading taken as the handler starts cannot be mistaken
# for a window that ran out.
_WIDE_ANNOUNCED_S = 10.0


class _NeverListingStore(InMemorySessionStore):
    """A session store whose ``list_sessions`` outlives any deadline a caller would announce."""

    def __init__(self) -> None:
        super().__init__()
        self.entered = asyncio.Event()

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        del limit
        self.entered.set()
        await asyncio.sleep(_NEVER_S)
        return ()


class _Latch(logging.Handler):
    """A handler that records the abandonment line and wakes whoever is waiting for it."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.written = asyncio.Event()

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        self.written.set()


def _engine_and_store(store: InMemorySessionStore) -> tuple[EngineFactory, InMemorySessionStore]:
    engine = TurnEngine(store, EchoInferenceBackend(), SystemClock())
    return (lambda _confirmer, _progress: engine), store


@dataclass(frozen=True)
class _Wire:
    """A running loopback server, and the event its handler sets on the way in."""

    target: str
    entered: asyncio.Event


@pytest.fixture
async def never_answering_server() -> AsyncIterator[_Wire]:
    """A tokenless BrainService whose session listing never answers, on a loopback port."""
    config = SeamServerConfig(host="127.0.0.1", port=0)
    store = _NeverListingStore()
    server, port = create_server(config, *_engine_and_store(store))
    await server.start()
    yield _Wire(f"127.0.0.1:{port}", store.entered)
    await server.stop(grace=None)


def _listing(channel: aio.Channel) -> Callable[..., aio.UnaryUnaryCall[object, object]]:
    """Return the ``ListSessions`` callable off a real stub, typed past `grpc-stubs`' unknowns."""
    stub = BrainServiceStub(channel)
    return cast(
        "Callable[..., aio.UnaryUnaryCall[object, object]]",
        stub.ListSessions,  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    )


async def _abandon_a_listing(target: str) -> None:
    """Announce a deadline on ``ListSessions``, then let it expire without answering."""
    async with aio.insecure_channel(target) as channel:
        with pytest.raises(aio.AioRpcError) as err:
            await cast(
                "Awaitable[ListSessionsReply]",
                _listing(channel)(ListSessionsRequest(), timeout=_ANNOUNCED_S),
            )
        assert err.value.code() is grpc.StatusCode.DEADLINE_EXCEEDED


async def _cancel_a_listing(wire: _Wire, *, announced: float | None) -> None:
    """Start a listing, wait until the handler is really in it, then drop the call."""
    async with aio.insecure_channel(wire.target) as channel:
        call = _listing(channel)(ListSessionsRequest(), timeout=announced)
        await wire.entered.wait()
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cast("Awaitable[ListSessionsReply]", call)


async def _outlast_a_listing(target: str) -> None:
    """Announce the deadline in metadata alone, so only the brain's own clock can end the call."""
    async with aio.insecure_channel(target) as channel:
        announced = (("grpc-timeout", f"{int(_ANNOUNCED_S * 1000)}m"),)
        with pytest.raises(aio.AioRpcError) as err:
            await cast(
                "Awaitable[ListSessionsReply]",
                _listing(channel)(ListSessionsRequest(), metadata=announced),
            )
        assert err.value.code() is grpc.StatusCode.DEADLINE_EXCEEDED


async def _line_left_behind(driver: Awaitable[None]) -> logging.LogRecord:
    """Run ``driver`` against the wire and return the one abandonment line it leaves."""
    latch = _Latch()
    logger = logging.getLogger(_ABANDON_LOGGER)
    logger.addHandler(latch)
    try:
        await driver
        await asyncio.wait_for(latch.written.wait(), timeout=10)
    finally:
        logger.removeHandler(latch)
    (record,) = latch.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == ABANDONED_MESSAGE
    return record


def _reading_of(record: logging.LogRecord) -> object:
    """Assert the RPC's wire path and return the reading beside it, unjudged."""
    method = record.__dict__["method"]
    assert isinstance(method, str)
    # Matched by its tail, so the proto's package name is written in the proto and nowhere else.
    assert method.endswith(".BrainService/ListSessions")
    return record.__dict__["time_remaining"]


def _rendered(record: logging.LogRecord, printed: str) -> str:
    """Render the line the formatter writes, with the method and the reading filled in."""
    method = record.__dict__["method"]
    assert isinstance(method, str)
    return f"WARNING:{_ABANDON_LOGGER}:{ABANDONED_MESSAGE} method={method} {printed}"


async def test_an_abandoned_unary_call_says_so_and_prints_the_time_it_had_left(
    never_answering_server: _Wire,
) -> None:
    record = await _line_left_behind(_abandon_a_listing(never_answering_server.target))
    remaining = _reading_of(record)
    assert isinstance(remaining, float | int)
    # A bound rather than an exact 0: the cancellation can reach the handler with a sliver of the
    # announced window left (docs/readings/abandoned-call-remaining.md).
    assert remaining >= 0
    assert remaining < _ANNOUNCED_S / 2


async def test_a_caller_that_stopped_early_leaves_most_of_the_window_on_the_line(
    never_answering_server: _Wire,
) -> None:
    record = await _line_left_behind(
        _cancel_a_listing(never_answering_server, announced=_WIDE_ANNOUNCED_S)
    )
    remaining = _reading_of(record)
    # No upper bound: grpc-python rounds a timeout up before encoding it, so this client's 10 s
    # reaches the server as 10100ms and a reading can be above what was announced
    # (docs/readings/abandoned-call-remaining.md).
    assert isinstance(remaining, float)
    assert remaining > _WIDE_ANNOUNCED_S / 2


async def test_a_deadline_the_brain_outlasts_alone_reads_as_the_integer_floor(
    never_answering_server: _Wire,
) -> None:
    record = await _line_left_behind(_outlast_a_listing(never_answering_server.target))
    remaining = _reading_of(record)
    assert isinstance(remaining, int)
    assert remaining == 0
    assert PlainFormatter().format(record) == _rendered(record, "time_remaining=0")


async def test_a_caller_that_announced_no_deadline_reads_as_nothing_at_all(
    never_answering_server: _Wire,
) -> None:
    record = await _line_left_behind(_cancel_a_listing(never_answering_server, announced=None))
    assert _reading_of(record) is None
    assert PlainFormatter().format(record) == _rendered(record, "time_remaining=None")


@dataclass(frozen=True)
class _Details:
    """A minimal ``grpc.HandlerCallDetails`` stand-in for driving the wrap directly."""

    method: str
    invocation_metadata: tuple[tuple[str, str], ...] = ()


def _details(method: str = "/cortex/Method") -> grpc.HandlerCallDetails:
    return cast("grpc.HandlerCallDetails", _Details(method))


async def _intercepted(
    handler: "grpc.RpcMethodHandler[object, object] | None",
) -> "grpc.RpcMethodHandler[object, object] | None":
    """Run the interceptor over a continuation that resolves to ``handler``."""

    async def continuation(
        details: grpc.HandlerCallDetails,
    ) -> "grpc.RpcMethodHandler[object, object] | None":
        del details
        return handler

    return await AbandonedCallInterceptor().intercept_service(continuation, _details())


async def _watch(
    handler: "grpc.RpcMethodHandler[object, object]",
    context: aio.ServicerContext[object, object],
    request: object = "the request",
) -> object:
    """Drive the wrapped unary behavior the interceptor built around ``handler``."""
    wrapped = await _intercepted(handler)
    assert wrapped is not None
    watched = wrapped.unary_unary
    assert watched is not None
    behavior = cast(
        "Callable[[object, aio.ServicerContext[object, object]], Awaitable[object]]", watched
    )
    return await behavior(request, context)


async def test_a_streaming_method_is_handed_back_untouched() -> None:
    async def behavior(request: object, context: object) -> AsyncIterator[object]:
        del context
        yield request

    handler: grpc.RpcMethodHandler[object, object] = grpc.stream_stream_rpc_method_handler(behavior)
    assert await _intercepted(handler) is handler


async def test_an_unserviced_method_is_handed_back_untouched() -> None:
    assert await _intercepted(None) is None


async def test_a_unary_call_that_answers_is_not_reported_as_abandoned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def behavior(request: object, context: object) -> object:
        del context
        return request

    handler: grpc.RpcMethodHandler[object, object] = grpc.unary_unary_rpc_method_handler(behavior)
    with caplog.at_level(logging.WARNING, logger=_ABANDON_LOGGER):
        answer = await _watch(handler, _context(4.5))
    assert answer == "the request"
    assert caplog.records == []


class _Context:
    """A servicer context that answers only what the wrap reads off it."""

    def __init__(self, remaining: float | None) -> None:
        self._remaining = remaining

    def time_remaining(self) -> float | None:
        return self._remaining


def _context(remaining: float | None) -> aio.ServicerContext[object, object]:
    return cast("aio.ServicerContext[object, object]", _Context(remaining))


@pytest.mark.parametrize(
    ("remaining", "printed"),
    [
        (0, "time_remaining=0"),
        (0.83, "time_remaining=0.83"),
        (None, "time_remaining=None"),
    ],
    ids=["deadline-expired", "caller-stopped-early", "no-deadline-announced"],
)
async def test_the_line_prints_the_reading_without_judging_it(
    remaining: float | None,
    printed: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def behavior(request: object, context: object) -> object:
        del request, context
        raise asyncio.CancelledError

    handler: grpc.RpcMethodHandler[object, object] = grpc.unary_unary_rpc_method_handler(behavior)
    with (
        caplog.at_level(logging.WARNING, logger=_ABANDON_LOGGER),
        pytest.raises(asyncio.CancelledError),
    ):
        await _watch(handler, _context(remaining))
    (record,) = caplog.records
    assert PlainFormatter().format(record) == (
        f"WARNING:{_ABANDON_LOGGER}:{ABANDONED_MESSAGE} method=/cortex/Method {printed}"
    )
