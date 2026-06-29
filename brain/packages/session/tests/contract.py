"""Shared SessionStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract tests (in-memory fake + fakeredis-backed Redis
adapter) and by the integration-marked live-Redis test. Each check generates its own
session ids (safe against a shared live server) and returns them so live runs can
clean up after themselves.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import Message, Role, SessionStore

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _session_id() -> str:
    return f"contract-{uuid4()}"


def make_message(role: Role, text: str, *, at: datetime = _AT, turn_id: str = "t-1") -> Message:
    return Message(role=role, text=text, at=at, turn_id=turn_id)


async def check_empty_history(store: SessionStore) -> list[str]:
    """An unknown session reads back as empty history, not an error."""
    session_id = _session_id()
    assert list(await store.history(session_id)) == []
    return [session_id]


async def check_append_then_history_order(store: SessionStore) -> list[str]:
    """History returns exactly what was appended, in append order."""
    session_id = _session_id()
    messages = [
        make_message(Role.USER, "one", turn_id="t-1"),
        make_message(Role.ASSISTANT, "reply 1: one", turn_id="t-1"),
        make_message(Role.USER, "two", turn_id="t-2"),
    ]
    for message in messages:
        await store.append(session_id, message)
    assert list(await store.history(session_id)) == messages
    return [session_id]


async def check_multi_session_isolation(store: SessionStore) -> list[str]:
    """Appends to one session never leak into another."""
    one, two = _session_id(), _session_id()
    await store.append(one, make_message(Role.USER, "for one"))
    await store.append(two, make_message(Role.USER, "for two"))
    await store.append(one, make_message(Role.ASSISTANT, "reply for one"))
    assert [m.text for m in await store.history(one)] == ["for one", "reply for one"]
    assert [m.text for m in await store.history(two)] == ["for two"]
    return [one, two]


async def check_roundtrip_fidelity(store: SessionStore) -> list[str]:
    """Every field survives the roundtrip exactly (including the timezone offset)."""
    session_id = _session_id()
    original = make_message(
        Role.ASSISTANT,
        "unicode ✓ / newline\n / quotes \"'",
        at=datetime(
            2026, 7, 3, 17, 45, 30, 123456, tzinfo=timezone(timedelta(hours=5, minutes=30))
        ),
        turn_id="turn-42",
    )
    await store.append(session_id, original)
    (loaded,) = await store.history(session_id)
    assert loaded == original
    assert loaded.role is Role.ASSISTANT
    assert loaded.text == original.text
    assert loaded.turn_id == original.turn_id
    # Aware-datetime equality compares instants; pin the offset separately so a
    # store that silently normalizes to UTC fails this check.
    assert loaded.at.utcoffset() == timedelta(hours=5, minutes=30)
    return [session_id]


ALL_CHECKS = (
    check_empty_history,
    check_append_then_history_order,
    check_multi_session_isolation,
    check_roundtrip_fidelity,
)
