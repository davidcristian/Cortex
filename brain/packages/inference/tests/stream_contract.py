"""Shared ``InferenceBackend`` streaming checks. Every implementation must pass all of them."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from cortex_core import (
    DecodeCadence,
    DecodeStop,
    GenerationBounds,
    InferenceBackend,
    InferenceError,
    InferenceEvent,
    Message,
    ReasoningChunk,
    Role,
    TextChunk,
    ToolCall,
)

CONTRACT_MODEL = "cortex"

# A logical id shaped like a tier this repo could have (ADR-0004) and hosted by neither leg's
# deployment. Shaped that way on purpose: what the check is about is a wiring change naming a model
# nobody serves, which reads like a real id and not like garbage.
UNSERVED_MODEL = "scribe"

# The reply a deliberating completion arrives at, the thinking it did first, and the words it says
# before asking for a tool. Constants rather than fixture-local strings, so a check compares what
# crossed the port against one description both implementations were built to.
CONTRACT_REPLY = "The answer is here"
CONTRACT_THINKING = "let me check"
CONTRACT_ASIDE = "checking "
CONTRACT_CALL = ToolCall(id="c1", name="read", arguments={"path": "/x"})

_AT = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)

_WEDGE_WATCHDOG_S = 5.0


@dataclass(frozen=True, slots=True)
class BackendUnderTest:
    """One ``InferenceBackend`` implementation plus the worlds the checks arrange."""

    deliberating: Callable[[], InferenceBackend]
    calling: Callable[[], InferenceBackend]
    wordless: Callable[[], InferenceBackend]
    unreachable: Callable[[], InferenceBackend]
    aclose: Callable[[], Awaitable[None]]


def _messages() -> list[Message]:
    return [Message(role=Role.USER, text="what is the answer", at=_AT, turn_id="t-1")]


async def events_of(
    backend: InferenceBackend,
    model: str = CONTRACT_MODEL,
    *,
    bounds: GenerationBounds | None = None,
) -> list[InferenceEvent]:
    """Drive one completion to exhaustion and return everything it yielded, in order."""
    return [event async for event in backend.stream(model, _messages(), bounds=bounds)]


def _text(events: Sequence[InferenceEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextChunk))


def _thinking(events: Sequence[InferenceEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, ReasoningChunk))


async def check_the_reply_is_its_text_deltas_joined_in_order(subject: BackendUnderTest) -> None:
    """Joining the text deltas in the order they arrived gives the reply, and nothing else does."""
    events = await events_of(subject.deliberating())
    assert _text(events) == CONTRACT_REPLY, f"the deltas do not join to the reply: {events!r}"


async def check_thinking_arrives_apart_and_before_the_reply(subject: BackendUnderTest) -> None:
    """A reasoning model's deliberation is its own event kind, and it is over before the reply
    starts.
    """
    events = await events_of(subject.deliberating())
    assert _thinking(events) == CONTRACT_THINKING, f"the thinking did not cross: {events!r}"
    assert CONTRACT_THINKING not in _text(events), f"thinking leaked into the reply: {events!r}"
    thinking_at = [i for i, event in enumerate(events) if isinstance(event, ReasoningChunk)]
    text_at = [i for i, event in enumerate(events) if isinstance(event, TextChunk)]
    assert max(thinking_at) < min(text_at), f"thinking must precede the reply: {events!r}"


async def check_a_deliberation_the_request_asked_against_still_crosses(
    subject: BackendUnderTest,
) -> None:
    """Asked for no thinking and answered with a trace anyway, an implementation hands it over."""
    events = await events_of(subject.deliberating(), bounds=GenerationBounds(thinking=False))
    assert _thinking(events) == CONTRACT_THINKING, f"the ignored switch hid the trace: {events!r}"
    assert _text(events) == CONTRACT_REPLY, f"the reply did not survive the switch: {events!r}"


async def check_a_tool_call_crosses_the_port_assembled(subject: BackendUnderTest) -> None:
    """A completion that asks for a tool yields that call once, whole."""
    events = await events_of(subject.calling())
    calls = [event for event in events if isinstance(event, ToolCall)]
    assert calls == [CONTRACT_CALL], f"expected exactly the one assembled call, got {events!r}"


async def check_a_tool_call_never_precedes_the_words_beside_it(subject: BackendUnderTest) -> None:
    """The model's words come before the call it makes, never after."""
    events = await events_of(subject.calling())
    assert _text(events) == CONTRACT_ASIDE, f"the aside did not cross: {events!r}"
    call_at = next(i for i, event in enumerate(events) if isinstance(event, ToolCall))
    text_at = [i for i, event in enumerate(events) if isinstance(event, TextChunk)]
    assert call_at > max(text_at), f"the call must follow the words beside it: {events!r}"


async def check_the_closing_events_arrive_once_each_and_in_one_order(
    subject: BackendUnderTest,
) -> None:
    """A completion reporting both closes with one stop and then one cadence, after everything."""
    events = await events_of(subject.deliberating())
    stops = [i for i, event in enumerate(events) if isinstance(event, DecodeStop)]
    cadences = [i for i, event in enumerate(events) if isinstance(event, DecodeCadence)]
    assert len(stops) == 1, f"expected exactly one stop, got {events!r}"
    assert len(cadences) == 1, f"expected exactly one cadence, got {events!r}"
    assert stops[0] < cadences[0], f"the stop precedes the cadence: {events!r}"
    said = [i for i, event in enumerate(events) if isinstance(event, TextChunk | ReasoningChunk)]
    assert stops[0] > max(said), f"the closing events follow what they describe: {events!r}"


async def check_a_completion_with_nothing_to_say_is_still_a_completion(
    subject: BackendUnderTest,
) -> None:
    """A stream may yield nothing at all, and that is an answer rather than a failure."""
    assert await events_of(subject.wordless()) == []


async def check_an_abandoned_completion_costs_the_backend_nothing(
    subject: BackendUnderTest,
) -> None:
    """A caller may stop reading partway, and the next completion still arrives whole."""
    backend = subject.deliberating()
    opened = backend.stream(CONTRACT_MODEL, _messages())
    await anext(opened)
    if isinstance(opened, AsyncGenerator):
        await opened.aclose()
    async with asyncio.timeout(_WEDGE_WATCHDOG_S):
        events = await events_of(backend)
    assert _text(events) == CONTRACT_REPLY, f"the next completion was not whole: {events!r}"


async def check_a_backend_that_cannot_answer_fails_with_inference_error(
    subject: BackendUnderTest,
) -> None:
    """The port has one failure channel and every implementation owes it."""
    try:
        await events_of(subject.unreachable())
    except InferenceError:
        return
    msg = "a backend that cannot answer streamed anyway"
    raise AssertionError(msg)


async def check_a_backend_answers_only_for_a_model_it_serves(subject: BackendUnderTest) -> None:
    """Asked for a model it does not serve, a backend fails rather than answering for it."""
    try:
        events = await events_of(subject.deliberating(), UNSERVED_MODEL)
    except InferenceError:
        return
    msg = f"a backend answered for {UNSERVED_MODEL!r}, which it does not serve: {events!r}"
    raise AssertionError(msg)


# One check: given an implementation plus its world builders, assert on what came out.
type StreamCheck = Callable[[BackendUnderTest], Awaitable[None]]

STREAM_CHECKS: tuple[StreamCheck, ...] = (
    check_the_reply_is_its_text_deltas_joined_in_order,
    check_thinking_arrives_apart_and_before_the_reply,
    check_a_deliberation_the_request_asked_against_still_crosses,
    check_a_tool_call_crosses_the_port_assembled,
    check_a_tool_call_never_precedes_the_words_beside_it,
    check_the_closing_events_arrive_once_each_and_in_one_order,
    check_a_completion_with_nothing_to_say_is_still_a_completion,
    check_an_abandoned_completion_costs_the_backend_nothing,
    check_a_backend_that_cannot_answer_fails_with_inference_error,
    check_a_backend_answers_only_for_a_model_it_serves,
)
