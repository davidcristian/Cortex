"""Shared ``InferenceBackend`` stop-reason checks. Every implementation must pass all of them.

This is the ports-before-adapters gate for the finish-reason arm (AGENTS.md: the real adapter must
pass the same contract test as the fake). It is driven twice by ``test_stop_contract.py``: over the
core's ``ScriptedInferenceBackend``, and over the real ``LlamaCppBackend`` reading a llama-server
SSE transcript through an httpx ``MockTransport``, with the real pure ``SingleResidentModelManager``
underneath. It is a second file beside ``cadence_contract.py`` rather than three more checks inside
it, because the two closing events are independent facts and a contract that bundled them would
make a build reporting one and not the other unrepresentable.

The two legs are held to different depths on purpose, exactly as the cadence contract's are. On the
**adapter** leg the answer is derived: the transcript is a real llama.cpp body carrying the words a
live server emits, and passing means the parser found the reason in bytes nobody shaped for it. On
the **scripted** leg the events the fixture handed the twin come back verbatim, and what those
cases pin is that the twin honours the world-condition it was given. That is all a fake can be
held to, which is why the real adapter is driven through these same checks.

The world-condition no verb can create is what the engine behind a backend says about why a
completion ended, so each implementation supplies it as three named builders: a completion the
model ended itself, one a token limit cut, and one whose engine says nothing at all. Every check
asserts on the events that came out of ``stream``, never on how the implementation got them.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from cortex_core import (
    DecodeStop,
    InferenceBackend,
    InferenceEvent,
    Message,
    Role,
    StopReason,
    TextChunk,
)

CONTRACT_MODEL = "subagent"

_AT = datetime(2026, 8, 16, 12, 0, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class BackendUnderTest:
    """One ``InferenceBackend`` implementation plus the world-condition the checks arrange.

    Three builders make a backend whose next completion streams the same reply text under three
    different endings: the model finishing its own turn, a token limit cutting it, and an engine
    that reports no reason at all. They are named builders rather than a parameter so a check reads
    as the world it arranges. ``aclose`` releases whatever the fixture built (the real adapter
    holds an HTTP client).
    """

    finished: Callable[[], InferenceBackend]
    capped: Callable[[], InferenceBackend]
    silent: Callable[[], InferenceBackend]
    aclose: Callable[[], Awaitable[None]]


async def events_of(backend: InferenceBackend) -> list[InferenceEvent]:
    """Drive one completion to exhaustion and return everything it yielded, in order."""
    messages = [Message(role=Role.USER, text="why did you stop", at=_AT, turn_id="t-1")]
    return [event async for event in backend.stream(CONTRACT_MODEL, messages)]


def _stops(events: Sequence[InferenceEvent]) -> list[DecodeStop]:
    return [event for event in events if isinstance(event, DecodeStop)]


def _text(events: Sequence[InferenceEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextChunk))


async def check_a_cut_completion_says_it_was_cut(subject: BackendUnderTest) -> None:
    """A completion a token limit ended reports exactly one stop, carrying ``CAPPED``.

    Without this event a reply that stopped where the token count ran out looks exactly like a
    reply that stopped where the answer did, and no consumer can tell the two apart.
    """
    events = await events_of(subject.capped())
    assert _stops(events) == [DecodeStop(StopReason.CAPPED)], f"expected one cap, got {events!r}"


async def check_a_finished_completion_is_not_a_cut_one(subject: BackendUnderTest) -> None:
    """A model that ended its own turn reports ``FINISHED``, which is the other half of the pair.

    A backend that answered ``CAPPED`` for everything would pass the check above and fail here, so
    the two together are what make the distinction real rather than a constant.
    """
    events = await events_of(subject.finished())
    assert _stops(events) == [DecodeStop(StopReason.FINISHED)], f"expected one end, got {events!r}"


async def check_the_stop_follows_the_text_it_explains(subject: BackendUnderTest) -> None:
    """The stop arrives after the reply text, since why a completion ended is not known until the
    text has been produced."""
    events = await events_of(subject.capped())
    text_at = [index for index, event in enumerate(events) if isinstance(event, TextChunk)]
    stop_at = next(index for index, event in enumerate(events) if isinstance(event, DecodeStop))
    assert text_at, f"expected reply text beside the stop, got {events!r}"
    assert stop_at > max(text_at), f"the stop must follow the text it explains: {events!r}"


async def check_silence_is_a_legal_answer(subject: BackendUnderTest) -> None:
    """A backend whose engine reports no reason emits no stop, and nothing else changes.

    The port permits this, so a consumer may never read the absence of a stop as a model that
    finished, and this check holds every implementation to that permission.
    """
    events = await events_of(subject.silent())
    assert not _stops(events), f"expected no stop at all, got {events!r}"
    assert _text(events) == _text(await events_of(subject.finished()))


# One check: given an implementation plus its world-condition builders, assert on what came out.
type StopCheck = Callable[[BackendUnderTest], Awaitable[None]]

STOP_CHECKS: tuple[StopCheck, ...] = (
    check_a_cut_completion_says_it_was_cut,
    check_a_finished_completion_is_not_a_cut_one,
    check_the_stop_follows_the_text_it_explains,
    check_silence_is_a_legal_answer,
)
