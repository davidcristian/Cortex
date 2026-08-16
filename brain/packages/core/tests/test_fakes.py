"""Behavior tests for the reference port implementations shipped in the core."""

from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    ConfirmationRequest,
    DecodeStop,
    EchoInferenceBackend,
    InferenceError,
    InMemorySessionStore,
    Message,
    RecordingConfirmer,
    Role,
    StopReason,
    SystemClock,
    TextChunk,
)

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _message(role: Role, text: str, turn_id: str = "t-1") -> Message:
    return Message(role=role, text=text, at=_AT, turn_id=turn_id)


async def _deltas(backend: EchoInferenceBackend, messages: tuple[Message, ...]) -> list[str]:
    return [e.text async for e in backend.stream("cortex", messages) if isinstance(e, TextChunk)]


async def test_in_memory_store_starts_empty() -> None:
    store = InMemorySessionStore()
    assert list(await store.history("unknown")) == []


async def test_in_memory_store_preserves_append_order() -> None:
    store = InMemorySessionStore()
    first = _message(Role.USER, "one")
    second = _message(Role.ASSISTANT, "two")
    await store.append("s", first)
    await store.append("s", second)
    assert list(await store.history("s")) == [first, second]


async def test_in_memory_store_isolates_sessions() -> None:
    store = InMemorySessionStore()
    await store.append("a", _message(Role.USER, "for a"))
    await store.append("b", _message(Role.USER, "for b"))
    assert [m.text for m in await store.history("a")] == ["for a"]
    assert [m.text for m in await store.history("b")] == ["for b"]


async def test_echo_backend_scripts_the_dictated_reply() -> None:
    deltas = await _deltas(EchoInferenceBackend(), (_message(Role.USER, "hello"),))
    assert len(deltas) >= 3
    assert "".join(deltas) == "reply 1: hello"


async def test_echo_backend_counts_only_user_messages() -> None:
    history = (
        _message(Role.USER, "one"),
        _message(Role.ASSISTANT, "reply 1: one"),
        _message(Role.USER, "two"),
    )
    deltas = await _deltas(EchoInferenceBackend(), history)
    assert "".join(deltas) == "reply 2: two"


async def test_echo_backend_closes_its_reply_by_saying_it_finished() -> None:
    """Every backend owes the port an answer about why a completion ended, this one included.

    Its answer is truthful rather than fabricated, which is the line between this and the decode
    cadence it deliberately never reports: the echo ends because its script does, and it honours no
    bounds, so it can never end any other way (ADR-0005 finish-reason addendum).
    """
    stream = EchoInferenceBackend().stream("cortex", (_message(Role.USER, "hello"),))
    events = [event async for event in stream]
    assert [event for event in events if isinstance(event, DecodeStop)] == [
        DecodeStop(StopReason.FINISHED)
    ]
    assert isinstance(events[-1], DecodeStop), "the stop closes the reply it describes"


async def test_echo_backend_requires_a_user_message() -> None:
    stream = EchoInferenceBackend().stream("cortex", (_message(Role.ASSISTANT, "hi"),))
    with pytest.raises(InferenceError, match="at least one user message"):
        await anext(stream)


def test_system_clock_is_timezone_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)


async def test_recording_confirmer_returns_its_fixed_answer_and_records_requests() -> None:
    request = ConfirmationRequest(tool_name="send_email", arguments={"to": "x"}, reason="outbound")
    approver = RecordingConfirmer(answer=True)
    denier = RecordingConfirmer(answer=False)
    assert await approver.confirm(request) is True
    assert await denier.confirm(request) is False
    assert approver.requests == (request,)
    assert denier.requests == (request,)
