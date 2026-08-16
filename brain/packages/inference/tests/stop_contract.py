"""Shared ``InferenceBackend`` stop-reason checks. Every implementation must pass all of them."""

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
    """One ``InferenceBackend`` implementation plus the world-condition the checks arrange."""

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

    This is the whole point of the arm: without it a reply that stopped where the count ran out is
    a reply that stopped where the answer did, and no consumer can tell.
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
    """The stop arrives after the reply text, why a completion ended being unknowable before it
    has."""
    events = await events_of(subject.capped())
    text_at = [index for index, event in enumerate(events) if isinstance(event, TextChunk)]
    stop_at = next(index for index, event in enumerate(events) if isinstance(event, DecodeStop))
    assert text_at, f"expected reply text beside the stop, got {events!r}"
    assert stop_at > max(text_at), f"the stop must follow the text it explains: {events!r}"


async def check_silence_is_a_legal_answer(subject: BackendUnderTest) -> None:
    """A backend whose engine reports no reason emits no stop, and nothing else changes.

    The port permits this, so a consumer may never read the absence of a stop as a model that
    finished; this check is what keeps that permission real rather than a sentence in a docstring.
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
