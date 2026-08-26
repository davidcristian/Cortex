"""Shared ``InferenceBackend`` streaming checks. Every implementation must pass all of them.

This is the ports-before-adapters gate for the stream itself (AGENTS.md: the real adapter must
pass the same contract test as the fake). It is the third file of the port's list, beside
``cadence_contract.py`` and ``stop_contract.py``, which hold one closing event each; what is left
is the shape of the completion those two events close, and it was the arm restated rather than
shared, described once by the core's suite over its own twin and again by the adapter's suite over
a llama-server transcript.

**What a stream owes, said without saying when.** Two implementations produce their events at
different rates from different sources, one from a script and one from bytes arriving over HTTP,
so nothing below counts events, sizes one, or asks when it arrives. Every check is an obligation
or an order:

- the reply is its text deltas joined in the order they arrived, and no other event kind carries
  any of it;
- a reasoning model's deliberation crosses as its own kind and none of it arrives after the reply
  has begun;
- a deliberation that arrived despite a request asking for none crosses all the same, an
  implementation reporting what its deployment did rather than filtering it into the silence the
  caller asked for;
- a tool call crosses whole, its id, name and arguments one value, never the fragments a wire
  splits it into;
- a tool call never precedes the words beside it, which is the promise the port's own word
  "interleaved" used to deny;
- the two closing events arrive at most once each and, where both arrive, the stop precedes the
  cadence and both follow everything they describe;
- a completion with nothing to say is a completion, owing no stop, no cadence and no error;
- a completion a caller stops reading costs the backend nothing, the next one arriving whole;
- a backend that cannot answer fails its caller with ``InferenceError``, and the port
  deliberately does not say at which moment;
- a backend answers only for a model it serves, an id outside its deployment failing rather than
  being answered for by whatever model is behind it.

What is **not** owed is written down in ``docs/modules/brain-inference.md`` rather than checked
here: a delta carrying no text is permitted by the port and dropped by the adapter as a
translation detail, so the two legitimately differ there, and the number, size and spacing of the
deltas belong to the engine.

The two legs are held to different depths on purpose, as the sibling lists' are. On the
**adapter** leg the answer is derived: the transcripts are real llama.cpp bodies, so passing means
the parser assembled the fact out of bytes nobody shaped for it, an arguments string split across
two chunks included. On the **scripted** leg the events the fixture handed the twin come back as
handed, and what those cases pin is that the twin honours the world it was given.

The world-conditions no verb can create are what the engine behind a backend had to say, so each
implementation supplies four builders: a reasoning model answering, a completion that asks for a
tool, a completion that says nothing at all, and a backend that cannot answer. Every check asserts
on the events that came out of ``stream``, never on how the implementation got them.

The served-model check needs no fifth builder, and that is the point of writing it this way: every
builder here stands for a deployment that serves ``CONTRACT_MODEL`` and nothing else, the adapter's
because its manager is constructed with that one resident and the twin's because it is told the
same, so asking any of them for ``UNSERVED_MODEL`` is already the world the check wants. The
ignored-switch check needs none either, for the same reason read the other way: ``deliberating`` is
a deployment that thought, and asking *it* for no thinking is exactly the world where a switch went
unhonoured, which is a real deployment and not a hypothetical (ADR-0005 switch-is-advisory
addendum).
"""

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

# What a wedged backend looks like when it must not be a hung run. It asserts nothing about how
# fast an implementation answers, only that the abandonment check below fails rather than parking
# the suite forever, which is the same device (and the same bound) the adapter's own
# lease-release test uses.
_WEDGE_WATCHDOG_S = 5.0


@dataclass(frozen=True, slots=True)
class BackendUnderTest:
    """One ``InferenceBackend`` implementation plus the worlds the checks arrange.

    Four builders, each a world the engine behind a backend can be in and no method can put it in:
    ``deliberating`` is a reasoning model thinking and then answering, closing with both a stop and
    a cadence; ``calling`` is a completion that says a few words and then asks for a tool;
    ``wordless`` is a completion with nothing in it at all; ``unreachable`` is a backend that
    cannot answer. Named builders rather than parameters so a check reads as the world it arranges.
    ``aclose`` releases whatever the fixture built (the real adapter holds an HTTP client).
    """

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
    """Joining the text deltas in the order they arrived gives the reply, and nothing else does.

    The whole reason the port streams is that a caller may show a partial answer, so what it owes
    is that the parts add up to the answer. How many parts, how long each is, and how far apart
    they arrive are the engine's business and are asserted nowhere.
    """
    events = await events_of(subject.deliberating())
    assert _text(events) == CONTRACT_REPLY, f"the deltas do not join to the reply: {events!r}"


async def check_thinking_arrives_apart_and_before_the_reply(subject: BackendUnderTest) -> None:
    """A reasoning model's deliberation is its own event kind, and it is over before the reply
    starts.

    Two promises in one world, because they are one promise to a consumer: the thinking is
    ephemeral status and the reply is the turn (ADR-0020), so a consumer that renders the first as
    a status chip and persists the second must never find one inside the other, and must never be
    asked to reopen the chip after the answer has begun.
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
    """Asked for no thinking and answered with a trace anyway, an implementation hands it over.

    ``GenerationBounds(thinking=False)`` is a request to the deployment's chat template and not a
    guarantee about the model: measured live, the shipped subagent pick honours it on a plain
    request and deliberates straight through it on one carrying a ``response_format``, spending the
    whole of a paired cap on the trace and returning an empty reply (ADR-0005 switch-is-advisory
    addendum). What the port owes in that world is the evidence. A caller cannot ask a template
    what it did, so a trace arriving after the switch was sent is the only thing that says the
    switch did not hold, and an implementation that filtered it here to make the port look truthful
    would leave the failure with nothing to read at all: an empty reply, a cap, and silence where
    the tokens went.

    The reply is asserted beside it because the obligation is to report and not to react. Nothing
    about the request changes when a deployment ignores it, so the completion is the same
    completion, and an implementation may not start refusing, retrying or truncating one.
    """
    events = await events_of(subject.deliberating(), bounds=GenerationBounds(thinking=False))
    assert _thinking(events) == CONTRACT_THINKING, f"the ignored switch hid the trace: {events!r}"
    assert _text(events) == CONTRACT_REPLY, f"the reply did not survive the switch: {events!r}"


async def check_a_tool_call_crosses_the_port_assembled(subject: BackendUnderTest) -> None:
    """A completion that asks for a tool yields that call once, whole.

    A dispatcher is handed the call and runs it; there is no protocol for a half-built one, so an
    implementation whose transport splits the arguments across chunks owes the caller the joined
    value rather than the pieces. That is what makes this the derived half on the adapter's leg.
    """
    events = await events_of(subject.calling())
    calls = [event for event in events if isinstance(event, ToolCall)]
    assert calls == [CONTRACT_CALL], f"expected exactly the one assembled call, got {events!r}"


async def check_a_tool_call_never_precedes_the_words_beside_it(subject: BackendUnderTest) -> None:
    """The model's words come before the call it makes, never after.

    The port's description said "interleaved", which no implementation has ever done and which a
    consumer would have to defend against: the text of a completion is persisted with the call it
    accompanies, so text arriving after a call would belong to a message already written.
    """
    events = await events_of(subject.calling())
    assert _text(events) == CONTRACT_ASIDE, f"the aside did not cross: {events!r}"
    call_at = next(i for i, event in enumerate(events) if isinstance(event, ToolCall))
    text_at = [i for i, event in enumerate(events) if isinstance(event, TextChunk)]
    assert call_at > max(text_at), f"the call must follow the words beside it: {events!r}"


async def check_the_closing_events_arrive_once_each_and_in_one_order(
    subject: BackendUnderTest,
) -> None:
    """A completion reporting both closes with one stop and then one cadence, after everything.

    Each sibling list holds its own event alone, so this is the only place the pair is described:
    why a completion ended explains the text that just ended, and how fast it decoded is the
    machine's own footnote to all of it. Both are facts about a completion that has finished, so
    neither may arrive before the thinking and the text it describes.
    """
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
    """A stream may yield nothing at all, and that is an answer rather than a failure.

    A model can end a completion having said nothing (a bare stop word, a cap of zero useful
    tokens), and every caller in the core reads the join of no deltas as the empty reply. So the
    port owes an empty stream no stop, no cadence and no error, and a consumer may not treat one
    as a broken backend.
    """
    assert await events_of(subject.wordless()) == []


async def check_an_abandoned_completion_costs_the_backend_nothing(
    subject: BackendUnderTest,
) -> None:
    """A caller may stop reading partway, and the next completion still arrives whole.

    Every ``finally: aclose()`` in the core is written for this (``drain_text``, the tool loop,
    the turn's own event stream), because a user's Stop lands as a consumer that walks away
    mid-completion. What the port owes is that walking away is free: an implementation holding
    anything for the duration of a stream, a GPU lease above all, must let go of it when the
    stream is dropped rather than when a collector gets around to the generator.
    """
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
    """The port has one failure channel and every implementation owes it.

    What is pinned is the *type* a caller would have to catch, not the moment: asking for the
    stream and consuming it are one act here, deliberately, because the port promises an
    ``AsyncIterator`` and an implementation is free to be a generator that fails on its first
    event or a method that fails before it returns one. Both shapes are live in this tree.
    """
    try:
        await events_of(subject.unreachable())
    except InferenceError:
        return
    msg = "a backend that cannot answer streamed anyway"
    raise AssertionError(msg)


async def check_a_backend_answers_only_for_a_model_it_serves(subject: BackendUnderTest) -> None:
    """Asked for a model it does not serve, a backend fails rather than answering for it.

    The one obligation here that is about the request rather than about the stream, and the reason
    it is an obligation at all: ``model`` is the caller's whole statement of which weights it wants
    (ADR-0004), so a backend that answers an id it does not host hands back a reply from some other
    model under the name of the one that was asked for, and the caller has no way to tell. Which
    ids a deployment serves stays the ``ModelManager``'s subject, and where a backend fronted a
    router the refusal would come off the wire instead; what the port fixes is only that a reply
    never arrives for an id the implementation could not have served.

    It matters most to the twin, and that is why it is in the shared list rather than in the
    adapter's own suite: a fake more permissive than the adapter hides defects rather than
    inventing them, so a mis-wired model id would land green here and fail on the first real turn.
    """
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
