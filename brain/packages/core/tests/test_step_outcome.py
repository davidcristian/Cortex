"""Behaviour tests for the post-dispatch outcome the capture indicator rests on (ADR-0029
outcome addendum).

The overlay's capture dot is one of the three consent surfaces that let ``capture_screen`` ship
without an approval card, and before this event it could only say the assistant **asked** to look
at the screen: the ``ToolActivity`` chip is emitted just before the dispatch, so a capture the
host kill switch refused, one whose self-exclusion failed closed, one the body never answered,
and a gated one the user declined all produced the identical event. These tests drive the real
loop over the real ``ToolDispatcher`` and the real ``CaptureScreenTool`` so each of those four
paths is measured rather than argued, and they pin the two properties the surface depends on:
every announced dispatch is settled exactly once, and the outcome's ``ok`` is the audit line's
own verdict about the same dispatch.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime

import pytest

from cortex_core import (
    CAPTURE_SCREEN_TOOL_NAME,
    BodyFailure,
    BodyGatewayError,
    CaptureScreenTool,
    DispatchPolicy,
    InferenceEvent,
    InMemoryBodyGateway,
    InMemoryToolRegistry,
    Message,
    RecordingAuditSink,
    RecordingConfirmer,
    TaintLedger,
    TextChunk,
    ToolCall,
    ToolDispatcher,
    ToolError,
    ToolResult,
    ToolSpec,
)
from cortex_core.inference import GenerationBounds, JsonSchema
from cortex_core.loop_events import StepOutcome, ToolStep
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop

# The body's own answer when the host kill switch is off AND when the overlay could not exclude
# itself: both wire `DeniedScreenCapture`, which answers `CaptureError::Disabled`, so the two
# failure modes are one string by the time the brain sees them. Each carries the kind the real
# gateway classifies its status into, so what settles `ok=False` here is the same value the
# wire produces: a refusal for the kill switch, an unanswered call for the deadline.
_DISABLED = BodyGatewayError(
    "body capture_screen failed: screen capture is disabled on this host",
    kind=BodyFailure.REFUSED,
)
_TIMED_OUT = BodyGatewayError(
    "body capture_screen failed: Deadline Exceeded", kind=BodyFailure.UNREACHABLE
)


# What the model sends for a whole-screen read; the tool requires the target explicitly.
_DISPLAY = {"target": "display"}


class _Clock:
    """Fixed clock: nothing here asserts on time."""

    def now(self) -> datetime:
        return datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


class _CallThenAnswer:
    """One round asking for ``name``, then a final answer. The shape every capture turn has."""

    def __init__(self, name: str = CAPTURE_SCREEN_TOOL_NAME, *, rounds: int = 1) -> None:
        self._name = name
        self._rounds = rounds
        self._seen = 0
        # capture_screen requires a target, so the fake model names one the way a real one must.
        self._arguments = _DISPLAY if name == CAPTURE_SCREEN_TOOL_NAME else {}

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        self._seen += 1
        if self._seen <= self._rounds:
            yield ToolCall(id=f"c{self._seen}", name=self._name, arguments=self._arguments)
            return
        yield TextChunk(text="done")


class _CaptureRegistry:
    """ToolRegistry over the real built-in, so the pixels ride the real result."""

    def __init__(self, tool: CaptureScreenTool) -> None:
        self._tool = tool

    async def describe_tools(self) -> Sequence[ToolSpec]:
        return (self._tool.spec,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        return await self._tool.invoke(call)


def _context(dispatcher: ToolDispatcher | None, **kwargs: object) -> ToolLoopContext:
    return ToolLoopContext(
        dispatcher=dispatcher,
        clock=_Clock(),
        turn_id="t-1",
        taint=TaintLedger(),
        nonce="nonce",
        session_id="s",
        **kwargs,  # pyright: ignore[reportArgumentType]
    )


async def _capture_turn(
    *, body: InMemoryBodyGateway, gated: bool = False, approve: bool = True
) -> tuple[list[object], RecordingAuditSink]:
    """Run one capture turn through the real loop and return what it yielded plus the audit."""
    tool = CaptureScreenTool(body)
    policy = DispatchPolicy(gated_names=(CAPTURE_SCREEN_TOOL_NAME,) if gated else ())
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(
        _CaptureRegistry(tool),
        audit,
        _Clock(),
        confirmer=RecordingConfirmer(answer=approve),
        policy=policy,
    )
    working: list[Message] = []
    loop = stream_tool_loop(_CallThenAnswer(), "cortex", working, _context(dispatcher))
    yielded: list[object] = [event async for event in loop]
    return yielded, audit


def _outcomes(yielded: Sequence[object]) -> list[StepOutcome]:
    return [event for event in yielded if isinstance(event, StepOutcome)]


def _steps(yielded: Sequence[object]) -> list[ToolStep]:
    return [event for event in yielded if isinstance(event, ToolStep)]


async def test_a_capture_that_reached_the_model_settles_ok() -> None:
    """The control arm, and the only one that may strengthen the indicator's claim: the body
    answered, the pixels are on the result, and the outcome says so."""
    yielded, audit = await _capture_turn(body=InMemoryBodyGateway())

    assert _outcomes(yielded) == [StepOutcome(tool_name=CAPTURE_SCREEN_TOOL_NAME, ok=True)]
    assert [record.ok for record in audit.records] == [True]


@pytest.mark.parametrize(
    ("mode", "failure"),
    [
        ("the host kill switch refused", _DISABLED),
        ("the overlay's self-exclusion failed closed", _DISABLED),
        ("the body never answered", _TIMED_OUT),
    ],
)
async def test_a_capture_the_body_refused_or_never_answered_settles_not_ok(
    mode: str, failure: BodyGatewayError
) -> None:
    """Three of the four modes the entry named. The first two are literally one code path: the
    shell wires ``DeniedScreenCapture`` when either the switch is off or the exclusion failed,
    so they are indistinguishable in the error text, let alone in the event. All three reach the
    brain as a ``BodyGatewayError`` the tool turns into a recoverable error result."""
    del mode
    yielded, audit = await _capture_turn(body=InMemoryBodyGateway(fail=failure))

    assert _steps(yielded) == [
        ToolStep(tool_name=CAPTURE_SCREEN_TOOL_NAME, summary=_steps(yielded)[0].summary)
    ]
    assert _outcomes(yielded) == [StepOutcome(tool_name=CAPTURE_SCREEN_TOOL_NAME, ok=False)]
    assert [record.ok for record in audit.records] == [False]


async def test_a_gated_capture_the_user_declined_settles_not_ok() -> None:
    """The fourth mode: with ``CORTEX_TOOLS_GATED`` naming the tool, a declined card returns an
    error result without the tool being invoked at all, and the chip was already on screen."""
    body = InMemoryBodyGateway()
    yielded, audit = await _capture_turn(body=body, gated=True, approve=False)

    assert _steps(yielded) != []
    assert _outcomes(yielded) == [StepOutcome(tool_name=CAPTURE_SCREEN_TOOL_NAME, ok=False)]
    assert [record.ok for record in audit.records] == [False]
    # The declined call never reached the body, which is what makes it a distinct mode from the
    # three above rather than a second way of spelling them.
    assert body.captures == ()


async def test_a_gated_capture_on_a_tainted_turn_settles_not_ok_without_asking_anyone() -> None:
    """The hard denial (a gated tool on a turn that already read untrusted content) is the one
    dispatch outcome that consults nobody, and it too resolves into the same result the outcome
    is read from."""
    tool = CaptureScreenTool(InMemoryBodyGateway())
    audit = RecordingAuditSink()
    confirmer = RecordingConfirmer(answer=True)
    dispatcher = ToolDispatcher(
        _CaptureRegistry(tool),
        audit,
        _Clock(),
        confirmer=confirmer,
        policy=DispatchPolicy(gated_names=(CAPTURE_SCREEN_TOOL_NAME,)),
    )
    taint = TaintLedger()
    taint.observe(ToolResult(call_id="seed", content="from the web"))
    context = ToolLoopContext(
        dispatcher=dispatcher,
        clock=_Clock(),
        turn_id="t-1",
        taint=taint,
        nonce="nonce",
        session_id="s",
    )
    working: list[Message] = []
    yielded = [
        event async for event in stream_tool_loop(_CallThenAnswer(), "cortex", working, context)
    ]

    assert _outcomes(yielded) == [StepOutcome(tool_name=CAPTURE_SCREEN_TOOL_NAME, ok=False)]
    assert confirmer.requests == ()


async def test_a_tool_that_raises_settles_not_ok() -> None:
    """A registry fault is the dispatcher's own error result, so it settles like every other
    failure rather than escaping past the outcome."""

    async def _boom(arguments: Mapping[str, object]) -> str:
        del arguments
        msg = "the sidecar died"
        raise ToolError(msg)

    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a file", parameters={}), _boom)}
    )
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _Clock())
    working: list[Message] = []
    yielded = [
        event
        async for event in stream_tool_loop(
            _CallThenAnswer("read"), "cortex", working, _context(dispatcher)
        )
    ]

    assert _outcomes(yielded) == [StepOutcome(tool_name="read", ok=False)]


async def test_every_announced_dispatch_is_settled_exactly_once() -> None:
    """The pairing the consent surface rests on, over a turn with several rounds: a step with no
    outcome would leave the indicator stuck at the weaker claim forever, and an outcome with no
    step would settle something that was never announced."""

    async def _ok(arguments: Mapping[str, object]) -> str:
        return f"read {arguments['path']}"

    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a file", parameters={}), _ok)}
    )
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _Clock())

    class _ThreeRounds:
        """Three rounds, each asking for a different path so salience admits all of them."""

        def __init__(self) -> None:
            self._seen = 0

        async def stream(
            self,
            model: str,
            messages: Sequence[Message],
            *,
            tools: Sequence[ToolSpec] = (),
            schema: JsonSchema | None = None,
            bounds: GenerationBounds | None = None,
        ) -> AsyncIterator[InferenceEvent]:
            del model, messages, tools, schema, bounds
            self._seen += 1
            if self._seen <= 3:
                yield ToolCall(id=f"c{self._seen}", name="read", arguments={"path": self._seen})
                return
            yield TextChunk(text="done")

    working: list[Message] = []
    yielded = [
        event
        async for event in stream_tool_loop(_ThreeRounds(), "cortex", working, _context(dispatcher))
    ]
    paired = [event for event in yielded if isinstance(event, ToolStep | StepOutcome)]

    assert len(_steps(yielded)) == 3
    # Alternating, never two steps before an outcome: the outcome is emitted after its own
    # dispatch resolves, not batched at the end of the round.
    assert [type(event).__name__ for event in paired] == ["ToolStep", "StepOutcome"] * 3


async def test_a_call_the_loop_refused_announces_nothing_and_settles_nothing() -> None:
    """A bound refusing a call before it runs renders no chip, so it must leave no outcome
    either: an outcome without a step is a settling event for something never shown."""

    async def _ok(arguments: Mapping[str, object]) -> str:
        del arguments
        return "data"

    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a file", parameters={}), _ok)}
    )
    audit = RecordingAuditSink()
    dispatcher = ToolDispatcher(registry, audit, _Clock())
    context = _context(dispatcher, budget=DispatchBudget(limit=0))
    working: list[Message] = []
    yielded = [
        event
        async for event in stream_tool_loop(_CallThenAnswer("read"), "cortex", working, context)
    ]

    assert _steps(yielded) == []
    assert _outcomes(yielded) == []
    # The call did reach the dispatcher, which refused and audited it: the missing pair is the
    # display half, not the audit half.
    assert [record.ok for record in audit.records] == [False]


async def test_a_call_matching_no_advertised_spec_announces_nothing_and_settles_nothing() -> None:
    """A name no snapshot carried still dispatches and still fails, but neither the chip nor the
    outcome may carry a string the model authored."""

    async def _ok(arguments: Mapping[str, object]) -> str:
        del arguments
        return "data"

    registry = InMemoryToolRegistry(
        {"read": (ToolSpec(name="read", description="read a file", parameters={}), _ok)}
    )
    dispatcher = ToolDispatcher(registry, RecordingAuditSink(), _Clock())
    working: list[Message] = []
    yielded = [
        event
        async for event in stream_tool_loop(
            _CallThenAnswer("invented"), "cortex", working, _context(dispatcher)
        )
    ]

    assert _steps(yielded) == []
    assert _outcomes(yielded) == []


async def test_a_consumer_that_closes_on_the_step_gets_no_outcome() -> None:
    """The one gap, stated rather than papered over: closing the loop between the step and its
    outcome ends the turn, and a turn with no stream has no surface left to settle."""
    body = InMemoryBodyGateway()
    dispatcher = ToolDispatcher(
        _CaptureRegistry(CaptureScreenTool(body)), RecordingAuditSink(), _Clock()
    )
    working: list[Message] = []
    loop = stream_tool_loop(_CallThenAnswer(), "cortex", working, _context(dispatcher))

    first = await anext(loop)
    await loop.aclose()

    assert isinstance(first, ToolStep)
    # Nothing was dispatched, so the indicator is left exactly where the step put it: lit and
    # claiming only that the assistant asked.
    assert body.captures == ()


async def test_the_capture_that_reached_the_model_is_the_one_that_settles_ok() -> None:
    """What ``ok`` means for this tool, tied to the fact the indicator claims: a non-error
    capture result always carries pixels, so ``ok=True`` is never a claim about an empty one."""
    body = InMemoryBodyGateway()
    tool = CaptureScreenTool(body)

    result = await tool.invoke(ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments=_DISPLAY))
    failed = await CaptureScreenTool(InMemoryBodyGateway(fail=_DISABLED)).invoke(
        ToolCall(id="c2", name=CAPTURE_SCREEN_TOOL_NAME, arguments=_DISPLAY)
    )

    assert (result.is_error, len(result.images)) == (False, 1)
    assert (failed.is_error, failed.images) == (True, ())
    # And the success arm really did go through the body rather than short-circuiting.
    assert len(body.captures) == 1
