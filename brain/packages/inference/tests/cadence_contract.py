"""Shared ``InferenceBackend`` decode-cadence checks. Every implementation must pass all of them."""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from cortex_core import DecodeCadence, InferenceBackend, InferenceEvent, Message, Role, TextChunk

# What a passing implementation must report when the world-condition says its engine reported it.
# One rate and one token count, so a check can assert the value crossed the port rather than that
# something cadence-shaped did.
CONTRACT_TPS = 17.29
CONTRACT_TOKENS = 96
CONTRACT_MODEL = "deep-model"

_AT = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class BackendUnderTest:
    """One ``InferenceBackend`` implementation plus the world-condition the checks arrange."""

    with_timings: Callable[[], InferenceBackend]
    without_timings: Callable[[], InferenceBackend]
    aclose: Callable[[], Awaitable[None]]


async def _events(backend: InferenceBackend) -> list[InferenceEvent]:
    """Drive one completion to exhaustion and return everything it yielded, in order."""
    messages = [Message(role=Role.USER, text="how fast", at=_AT, turn_id="t-1")]
    return [event async for event in backend.stream(CONTRACT_MODEL, messages)]


async def check_reports_the_servers_rate(subject: BackendUnderTest) -> None:
    """A backend whose engine reported timings emits exactly one cadence, carrying them."""
    events = await _events(subject.with_timings())
    cadences = [event for event in events if isinstance(event, DecodeCadence)]
    assert len(cadences) == 1, f"expected exactly one cadence, got {events!r}"
    assert cadences[0].tokens_per_second == CONTRACT_TPS
    assert cadences[0].tokens == CONTRACT_TOKENS


async def check_cadence_closes_the_stream(subject: BackendUnderTest) -> None:
    """The cadence arrives after the text it describes, a rate being unknowable before then."""
    events = await _events(subject.with_timings())
    text_at = [index for index, event in enumerate(events) if isinstance(event, TextChunk)]
    cadence_at = next(i for i, event in enumerate(events) if isinstance(event, DecodeCadence))
    assert text_at, f"expected reply text beside the cadence, got {events!r}"
    assert cadence_at > max(text_at), f"cadence must follow the text it describes: {events!r}"


async def check_silence_is_a_legal_answer(subject: BackendUnderTest) -> None:
    """A backend whose engine reports no timings emits no cadence, and nothing else changes.

    The port permits this, so a consumer may never read the absence of a cadence as a healthy
    rate; this check is what keeps that permission real rather than a sentence in a docstring.
    """
    events = await _events(subject.without_timings())
    assert not [event for event in events if isinstance(event, DecodeCadence)]
    assert _text(events) == _text(await _events(subject.with_timings()))


def _text(events: Sequence[InferenceEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TextChunk))


# One check: given an implementation plus its world-condition knob, assert on what came out.
type CadenceCheck = Callable[[BackendUnderTest], Awaitable[None]]

CADENCE_CHECKS: tuple[CadenceCheck, ...] = (
    check_reports_the_servers_rate,
    check_cadence_closes_the_stream,
    check_silence_is_a_legal_answer,
)
