"""Behavior tests for the abandoned-call line (ADR-0024 abandonment addendum).

Wire-level: a real loopback ``grpc.aio`` server whose ``ListSessions`` never returns, driven by a
real stub that announces a deadline and then walks away. That is the only place ``time_remaining``
is a real reading rather than a value this file arranged, and it is what proves the interceptor is
installed by ``create_server`` at all. Unit-level: the two handlers the wire cannot show being
passed through (the service's one stream, and a method the server does not serve).

Distrust-green proofs, each mutation applied to `abandon.py` alone with the orchestrator suite
re-run, then restored:
- deleting the ``except`` arm, so a cancelled handler prints nothing, reddens 4;
- swallowing the cancellation instead of re-raising it reddens 3, the three that assert the
  cancellation still arrives at whoever asked for it;
- watching every handler rather than only the unary-unary ones reddens the stream passthrough
  here and then **hangs** the wire ``Converse`` suite outright, a stream rebuilt as a unary
  handler having no behavior at all, which is the fence this module is built around;
- dropping the ``method`` field reddens 4, and dropping ``time_remaining`` reddens 4;
- and four that stand in for a grpc whose reading stopped meaning what it means, each replacing
  it with a constant: a negative (``-0.05``) reddens 4, the wire case on ``remaining >= 0``; a
  reading that has not run down (``0.15``) reddens 4, the wire case on the half-window bound; a
  positive sliver (``0.05``) reddens 3 and a float zero (``0.0``) reddens 3, both of them the
  three parameterized renderings, the wire case passing each **by design** since a real expiry
  reads as either of those under load.
"""

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
# Longer than any real answer and far shorter than the suite's patience: the client's deadline is
# what ends this call, so the number only has to be big enough that the store never wins the race.
_NEVER_S = 30.0
# What the client announces. Small enough to keep the suite quick, large enough to clear the
# loopback round trip that has to happen before the handler is even entered.
_ANNOUNCED_S = 0.2


class _NeverListingStore(InMemorySessionStore):
    """A session store whose ``list_sessions`` outlives any deadline a caller would announce."""

    async def list_sessions(self, *, limit: int) -> Sequence[SessionSummary]:
        del limit
        await asyncio.sleep(_NEVER_S)
        return ()


class _Latch(logging.Handler):
    """A handler that records the abandonment line and wakes whoever is waiting for it.

    The server cancels the handler after the client has already been told its deadline expired,
    so the assertion cannot follow the client's own failure: it has to wait for the line itself.
    """

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


@pytest.fixture
async def never_answering_server() -> AsyncIterator[str]:
    """A tokenless BrainService whose session listing never answers, on a loopback port."""
    config = SeamServerConfig(host="127.0.0.1", port=0)
    server, port = create_server(config, *_engine_and_store(_NeverListingStore()))
    await server.start()
    yield f"127.0.0.1:{port}"
    await server.stop(grace=None)


async def _abandon_a_listing(target: str) -> None:
    """Announce a deadline on ``ListSessions``, then let it expire without answering."""
    async with aio.insecure_channel(target) as channel:
        stub = BrainServiceStub(channel)
        listing = stub.ListSessions  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        with pytest.raises(aio.AioRpcError) as err:
            await cast(
                "Awaitable[ListSessionsReply]",
                listing(ListSessionsRequest(), timeout=_ANNOUNCED_S),
            )
        assert err.value.code() is grpc.StatusCode.DEADLINE_EXCEEDED


async def test_an_abandoned_unary_call_says_so_and_prints_the_time_it_had_left(
    never_answering_server: str,
) -> None:
    """The whole point, end to end: the handler the caller dropped leaves a line behind.

    Before this, a call the body gave up on unwound in silence and read exactly like one that was
    never made. The remaining time is the reading the brain was handed and never took: here the
    deadline the caller announced is what ended the call, so the window has run down and what is
    left of it is nothing an operator would spend.
    """
    latch = _Latch()
    logger = logging.getLogger(_ABANDON_LOGGER)
    logger.addHandler(latch)
    try:
        await _abandon_a_listing(never_answering_server)
        await asyncio.wait_for(latch.written.wait(), timeout=10)
    finally:
        logger.removeHandler(latch)
    (record,) = latch.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == ABANDONED_MESSAGE
    # The wire path of the RPC that was dropped, which is the whole of what the interceptor knows
    # about a call it is deliberately generic over. Matched by its tail so the proto's package
    # name is spelled in the proto and nowhere else.
    method = record.__dict__["method"]
    assert isinstance(method, str)
    assert method.endswith(".BrainService/ListSessions")
    remaining = record.__dict__["time_remaining"]
    assert isinstance(remaining, float | int)
    # Two claims about one real reading, each asserted rather than described. It is never
    # negative, because grpc floors what it answers here and documents the answer as a nonnegative
    # float, so an expiry can never read as a caller who walked away with time to spare.
    assert remaining >= 0
    # And the announced window really has run down, rather than reading small because something
    # else ended the call. A bound and not the floor itself, because the floor is not what an
    # expiry always reads: `max(deadline - now, 0)` answers with its own second argument only when
    # the cancellation reaches this handler after the deadline passed, and a loaded machine can
    # deliver it while a sliver of the window is still unspent. Measured rather than reasoned.
    # Idle, 20 replays of this scenario read an integer `0` every time; with 48 busy loops on 24
    # cores and a second full run of this suite beside them, 32 of 200 read a positive float
    # instead, the largest of them 0.0073 s, under 4% of the announced window and a thirteenth of
    # this bound. The rendering of an expiry is pinned below, on the `0` this file hands the wrap,
    # because that is where it is the same reading twice rather than whatever the clock said.
    assert remaining < _ANNOUNCED_S / 2


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
    """Drive the wrapped unary behavior the interceptor built around ``handler``.

    The cast is the one `grpc-stubs` forces: it types a handler's behavior with the synchronous
    server's signature, where every behavior on this service is an ``async def``.
    """
    wrapped = await _intercepted(handler)
    assert wrapped is not None
    watched = wrapped.unary_unary
    assert watched is not None
    behavior = cast(
        "Callable[[object, aio.ServicerContext[object, object]], Awaitable[object]]", watched
    )
    return await behavior(request, context)


async def test_a_streaming_method_is_handed_back_untouched() -> None:
    """`Converse` announces no deadline and must stay unwatched: the fence, as a shape check.

    A stream-stream handler carries no unary-unary behavior, so the passthrough is decided by
    what the method *is* rather than by a name this interceptor would have to keep current.
    """

    async def behavior(request: object, context: object) -> AsyncIterator[object]:
        del context
        yield request

    handler: grpc.RpcMethodHandler[object, object] = grpc.stream_stream_rpc_method_handler(behavior)
    assert await _intercepted(handler) is handler


async def test_an_unserviced_method_is_handed_back_untouched() -> None:
    """The continuation may resolve to ``None`` (no such method); there is nothing to watch."""
    assert await _intercepted(None) is None


async def test_a_unary_call_that_answers_is_not_reported_as_abandoned(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ordinary path: the wrap returns the reply and writes nothing.

    Asserted through the wrapped behavior rather than over the wire, because the assertion that
    matters is the negative one, and a silent line is only evidence if the same call would have
    printed had it been dropped.
    """

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
    """Three different facts, one line, no branch: the operator reads the number.

    An expired deadline reads as no time left worth spending, grpc flooring the reading at zero
    rather than letting it run negative; that floor and the bound around it are asserted over the
    wire above, on the reading a real clock produced. These three are values this file hands the
    wrap, so what they pin is the rendering, and the `0` among them is the rendering an expiry
    prints whenever the cancellation lands after the deadline passed. A
    caller that stopped early is the shipped body on every call, since it enforces a bound
    strictly shorter than the one it announces; ``None`` is a caller that announced nothing and
    simply disconnected. The wrap tells the three apart by printing the reading, never by
    deciding what it means.
    """

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
