"""Behavior tests for the abandoned-call line (ADR-0024 abandonment addendum).

Wire-level: a real loopback ``grpc.aio`` server whose ``ListSessions`` never returns, driven by a
real stub. Four cases run over that wire, and between them every reading the line distinguishes is
one grpc produced rather than one this file arranged, each in the shape that produces it in
production:

- the caller stops waiting early, which is the shipped body on every call, since it enforces a
  bound strictly shorter than the one it announces (ADR-0024's grace margin);
- the brain's own clock ends the call, which is what happens when the body is killed or the
  connection half-opens and the cancellation the body would have sent never arrives;
- both clocks are armed on the same announcement and race, which is the fixture's older case;
- the caller announces no deadline at all and disconnects.

The wire is also what proves the interceptor is installed by ``create_server``, which no unit test
of the wrap can say. Unit-level: the two handlers the wire cannot show being passed through (the
service's one stream, and a method the server does not serve), and the rendering of all three
readings side by side.

**Nothing here sleeps to order two events.** A cancellation that arrives before the handler is
entered produces no line at all, so the cases that cancel wait on ``_Wire.entered``, which the
never-answering store sets from inside the handler, and every case then waits on ``_Latch``, which
the line itself sets. The one case that wants the deadline to have passed does not wait for it
either: it announces the deadline in ``grpc-timeout`` metadata and arms no client timer, so the
only clock that can end the call is the brain's own and the subtraction behind the reading has
always already gone negative.

Distrust-green proofs, each mutation applied to `abandon.py` alone with the whole orchestrator
suite (`packages/orchestrator/tests`, 448 selected and 19 deselected as integration) re-run, then
restored:
- deleting the ``except`` arm, so a cancelled handler prints nothing, reddens 7, every case here
  that expects a line;
- swallowing the cancellation instead of re-raising it reddens 3, the three renderings, which are
  the only cases that watch the cancellation reach whoever asked for it; the wire cases do not,
  because a client that has already been told its deadline expired, or that cancelled the call
  itself, is told the same thing either way;
- watching every handler rather than only the unary-unary ones reddens the stream passthrough
  here and then **hangs** ``test_converse_grpc.py`` outright, a stream rebuilt as a unary handler
  having no behavior at all, which is the fence this module is built around;
- dropping the ``method`` field reddens 7, and dropping ``time_remaining`` reddens 7;
- and four that stand in for a grpc whose reading stopped meaning what it means, each replacing
  it with a constant: a negative (``-0.05``) reddens 7, a reading that has not run down (``0.15``)
  reddens 7, a positive sliver (``0.05``) reddens 6 and a float zero (``0.0``) reddens 6. The last
  two are the ones worth the wire: before these cases existed both died only in the parameterized
  renderings, which redden on any constant because a constant is what they vary, and neither could
  be told from a real expiry. Both now die in the floor case as well, on ``isinstance(remaining,
  int)``, which is a reading grpc produced and no constant of either kind satisfies.
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
# What the client announces when the deadline is the thing that ends the call. Small enough to
# keep the suite quick, large enough to clear the loopback round trip that has to happen before
# the handler is even entered.
_ANNOUNCED_S = 0.2
# What a client announces when it means to wait and then changes its mind. Wide enough that a
# reading taken the instant the handler is entered cannot be mistaken for a window that ran down:
# the two cases below are told apart by which half of their own announcement the reading is in,
# and this one is announced fifty times wider than the one above.
_WIDE_ANNOUNCED_S = 10.0


class _NeverListingStore(InMemorySessionStore):
    """A session store whose ``list_sessions`` outlives any deadline a caller would announce.

    It also says when it was reached. A case that cancels has to cancel *after* the handler is
    entered or there is no handler to cancel and no line to read, and this event is what makes
    that ordering a fact rather than a wait.
    """

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
    """The ``ListSessions`` callable off a real stub, typed past `grpc-stubs`' unknowns."""
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
    """Start a listing, wait until the handler is really in it, then drop the call.

    The wait is on the handler's own event, so the cancellation cannot overtake the handler and
    leave nothing to abandon. Cancelling a `grpc.aio` call locally makes the awaiting client raise
    ``CancelledError`` rather than an ``AioRpcError``: there is no status, only a caller that
    stopped asking.
    """
    async with aio.insecure_channel(wire.target) as channel:
        call = _listing(channel)(ListSessionsRequest(), timeout=announced)
        await wire.entered.wait()
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cast("Awaitable[ListSessionsReply]", call)


async def _outlast_a_listing(target: str) -> None:
    """Announce the deadline in metadata alone, so only the brain's own clock can end the call.

    `grpc-timeout` is how a deadline crosses the wire, and the body sends it (ADR-0024's courtesy
    header). Passing it as metadata with no ``timeout=`` beside it arms no clock on this side, so
    there is no client timer that can fire first and no cancellation racing the deadline: the
    server's own deadline is the only thing that ends this call, and it cannot fire before it is
    due. That is what makes the reading below the floor rather than a coin toss.
    """
    async with aio.insecure_channel(target) as channel:
        announced = (("grpc-timeout", f"{int(_ANNOUNCED_S * 1000)}m"),)
        with pytest.raises(aio.AioRpcError) as err:
            await cast(
                "Awaitable[ListSessionsReply]",
                _listing(channel)(ListSessionsRequest(), metadata=announced),
            )
        assert err.value.code() is grpc.StatusCode.DEADLINE_EXCEEDED


async def _line_left_behind(driver: Awaitable[None]) -> logging.LogRecord:
    """Run ``driver`` against the wire and return the one abandonment line it leaves.

    The server cancels the handler after the client has already been told, so no assertion can
    follow the client's own failure: it has to wait for the line itself, which ``_Latch`` sets.
    """
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
    """The RPC's wire path, asserted, and the reading beside it, handed back unjudged."""
    # The wire path of the RPC that was dropped, which is the whole of what the interceptor knows
    # about a call it is deliberately generic over. Matched by its tail so the proto's package
    # name is spelled in the proto and nowhere else.
    method = record.__dict__["method"]
    assert isinstance(method, str)
    assert method.endswith(".BrainService/ListSessions")
    return record.__dict__["time_remaining"]


def _rendered(record: logging.LogRecord, printed: str) -> str:
    """What the line reads as, with the method interpolated and the reading spelled out."""
    method = record.__dict__["method"]
    assert isinstance(method, str)
    return f"WARNING:{_ABANDON_LOGGER}:{ABANDONED_MESSAGE} method={method} {printed}"


async def test_an_abandoned_unary_call_says_so_and_prints_the_time_it_had_left(
    never_answering_server: _Wire,
) -> None:
    """The whole point, end to end: the handler the caller dropped leaves a line behind.

    Before this, a call the body gave up on unwound in silence and read exactly like one that was
    never made. The remaining time is the reading the brain was handed and never took: here the
    deadline the caller announced is what ended the call, so the window has run down and what is
    left of it is nothing an operator would spend.

    Both clocks are armed on one announcement here, the client's ``timeout=`` and the deadline the
    header carries to the server, and which of them ends the call is a race. That is why this case
    bounds the reading instead of pinning it; the case below announces to one clock only and pins
    the floor exactly.
    """
    record = await _line_left_behind(_abandon_a_listing(never_answering_server.target))
    remaining = _reading_of(record)
    assert isinstance(remaining, float | int)
    # Two claims about one real reading, each asserted rather than described. It is never
    # negative, because grpc floors what it answers here and documents the answer as a nonnegative
    # float, so an expiry can never read as a caller who walked away with time to spare.
    assert remaining >= 0
    # And the announced window really has run down, rather than reading small because something
    # else ended the call. A bound and not the floor itself, because the floor is not what this
    # scenario always reads: `max(deadline - now, 0)` answers with its own second argument only
    # when the cancellation reaches this handler after the deadline passed, and the two clocks
    # racing here can deliver it while a sliver of the window is still unspent. Measured rather
    # than reasoned. With 48 busy loops on 24 cores and a full run of this suite beside them, 400
    # replays of this scenario read an integer `0` 349 times and a positive float 51 times, the
    # widest of those 0.0107 s: a tenth of this bound, and under 6% of the announced window.
    assert remaining < _ANNOUNCED_S / 2


async def test_a_caller_that_stopped_early_leaves_most_of_the_window_on_the_line(
    never_answering_server: _Wire,
) -> None:
    """The reading the shipped body produces on every call, taken off a real wire.

    The body announces a deadline and enforces a bound strictly shorter than it, so it drops the
    call while most of what it announced is still unspent, and the line says so. This is that
    shape: announce wide, wait until the handler is really running, then stop asking.
    """
    record = await _line_left_behind(
        _cancel_a_listing(never_answering_server, announced=_WIDE_ANNOUNCED_S)
    )
    remaining = _reading_of(record)
    # A float, and never the integer the floor answers with: a caller who stopped early left time
    # on the clock, so the subtraction behind the reading never went negative and `max` never
    # reached its second argument. This is the half of the reading a value handed to a fake cannot
    # say anything about, since a fake's type is whatever the file typed.
    assert isinstance(remaining, float)
    # Well above zero, which is the whole of what the record claims this row means. Measured under
    # the load above: 200 replays read between 9.9789 s and 10.0993 s against the 10 s announced,
    # so this bound clears the worst by 4.98 s.
    assert remaining > _WIDE_ANNOUNCED_S / 2
    # No upper bound, deliberately, and this is the surprise worth writing down: 41 of those 200
    # readings were *above* the 10 s announced, the widest 10.0993 s. The server's window is the
    # one the header encoded, and grpc-python rounds a `timeout=` up onto a coarse unit ladder
    # before encoding it, so this client's 10 s reaches the server as `10100ms` (read off the wire
    # in ADR-0024's encoding addendum). A case demanding the reading stay under the announcement
    # would be asserting something grpc does not promise.


async def test_a_deadline_the_brain_outlasts_alone_reads_as_the_integer_floor(
    never_answering_server: _Wire,
) -> None:
    """An expiry with one clock in it, so the floor is a fact rather than a likelihood.

    This is how an expiry actually reaches a deployed brain: the body was killed, or the
    connection half-opened, and the cancellation it would have sent never arrives, so the
    announced deadline is enforced by the only clock left. Announcing through the header alone is
    that, exactly: no client timer exists to fire early, the deadline can only be enforced once it
    is due, and `max(deadline - now, 0)` therefore always answers with its own second argument.

    That is the distinction the case above cannot draw. A grpc that stopped flooring the reading
    and reported the unspent sliver instead would read here as a small positive float, and a grpc
    that floored to a float rather than to an `int` would print `0.0`; both are indistinguishable
    from the truth in a race the sliver sometimes wins, and neither survives a scenario where the
    sliver cannot exist. 200 replays under the load above read an integer `0` every time.
    """
    record = await _line_left_behind(_outlast_a_listing(never_answering_server.target))
    remaining = _reading_of(record)
    # An `int`, which is `max`'s own second argument and nothing a clock produced: a reading still
    # counting down is a float, whatever its value.
    assert isinstance(remaining, int)
    assert remaining == 0
    # And what that renders as, now on a reading grpc produced rather than one this file handed
    # the wrap. A float zero fails this line even though it passes the two above.
    assert PlainFormatter().format(record) == _rendered(record, "time_remaining=0")


async def test_a_caller_that_announced_no_deadline_reads_as_nothing_at_all(
    never_answering_server: _Wire,
) -> None:
    """The third reading, over the wire: no deadline announced, and the caller simply goes.

    The shipped body announces a deadline on every unary call, so this row is not its shape; it is
    the shape of anything else that reaches this seam, and the record reads `None` as a fact about
    the caller rather than about the clock. What is being held here is that grpc answers `None`
    for a call with no deadline rather than folding it into a number, because a grpc that answered
    `0` would turn an operator's three-way reading into a two-way one with nothing complaining.
    """
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

    Each of the three is produced over the wire above, in the shape that produces it in
    production, and every claim about what grpc answers is held there. What is left for this case
    is the rendering, all three of them side by side, which is the one thing a table reads better
    than three scattered cases do: the wrap tells the three apart by printing the reading, never
    by deciding what it means, and a reader sees that here in one glance. The `0.83` row is the
    only reading in the file with no wire case of its own, because a specific positive value is
    arithmetic; that it is positive at all is asserted above on a real clock.
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
