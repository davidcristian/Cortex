"""Shared SessionStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract tests (in-memory fake + fakeredis-backed Redis
adapter) and by the integration-marked live-Redis test. Each check generates its own
session ids, all prefixed `contract-` (safe against a shared live server, and the prefix
the live test sweeps by; see tests/test_store_live.py).
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from cortex_core import Message, Role, SessionStore

_AT = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)


def _session_id() -> str:
    return f"contract-{uuid4()}"


def make_message(role: Role, text: str, *, at: datetime = _AT, turn_id: str = "t-1") -> Message:
    return Message(role=role, text=text, at=at, turn_id=turn_id)


async def check_empty_history(store: SessionStore) -> None:
    """An unknown session reads back as empty history, not an error."""
    session_id = _session_id()
    assert list(await store.history(session_id)) == []


async def check_append_then_history_order(store: SessionStore) -> None:
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


async def check_multi_session_isolation(store: SessionStore) -> None:
    """Appends to one session never leak into another."""
    one, two = _session_id(), _session_id()
    await store.append(one, make_message(Role.USER, "for one"))
    await store.append(two, make_message(Role.USER, "for two"))
    await store.append(one, make_message(Role.ASSISTANT, "reply for one"))
    assert [m.text for m in await store.history(one)] == ["for one", "reply for one"]
    assert [m.text for m in await store.history(two)] == ["for two"]


async def check_roundtrip_fidelity(store: SessionStore) -> None:
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


async def check_list_sessions_orders_and_summarizes(store: SessionStore) -> None:
    """list_sessions returns recent chats newest-active first, with a derived title/preview.

    Robust against a shared live server: it filters the global list down to the two sessions
    it created, then asserts their relative order and summaries, the filtered sublist of a
    sorted list being sorted too. What DOES break it is being crowded out of the `limit=50`
    window by 50 more-recent sessions, which is why the live test sweeps its own ids after
    every check instead of letting them pile up (see tests/test_store_live.py)."""
    older, newer = _session_id(), _session_id()
    early = datetime(2026, 7, 3, 9, 0, tzinfo=UTC)
    late = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
    await store.append(older, make_message(Role.USER, "question about cats", at=early, turn_id="a"))
    await store.append(older, make_message(Role.ASSISTANT, "cats are great", at=early, turn_id="a"))
    await store.append(newer, make_message(Role.USER, "question about dogs", at=late, turn_id="b"))
    mine = [s for s in await store.list_sessions(limit=50) if s.session_id in {older, newer}]
    assert [s.session_id for s in mine] == [newer, older]  # most-recently-active first
    by_id = {s.session_id: s for s in mine}
    # older: title from the first (user) message, preview from the last (assistant) message.
    assert by_id[older].title == "question about cats"
    assert by_id[older].preview == "cats are great"
    assert by_id[older].last_activity == early
    # newer: one message, so title and preview both come from it.
    assert by_id[newer].title == "question about dogs"
    assert by_id[newer].preview == "question about dogs"
    assert by_id[newer].last_activity == late


async def check_set_title_overrides_the_first_message(store: SessionStore) -> None:
    """A stored title wins over the first-message derivation; the preview is unaffected.

    Proves both stores honor ``set_title`` behind the port (ADR-0021 titles addendum): the
    override replaces only the title, a later call overwrites it, and it survives being read
    back through ``list_sessions``. Robust against a shared live server by filtering to its id.
    """
    session_id = _session_id()
    await store.append(session_id, make_message(Role.USER, "a rambly first question about cats"))
    await store.append(session_id, make_message(Role.ASSISTANT, "cats sleep a lot"))

    async def title_and_preview() -> tuple[str, str]:
        (mine,) = [s for s in await store.list_sessions(limit=50) if s.session_id == session_id]
        return mine.title, mine.preview

    assert await title_and_preview() == ("a rambly first question about cats", "cats sleep a lot")
    await store.set_title(session_id, "Cat sleep habits")
    assert await title_and_preview() == ("Cat sleep habits", "cats sleep a lot")
    await store.set_title(session_id, "Feline naps")  # a later title overwrites the earlier one
    assert await title_and_preview() == ("Feline naps", "cats sleep a lot")


ALL_CHECKS = (
    check_empty_history,
    check_append_then_history_order,
    check_multi_session_isolation,
    check_roundtrip_fidelity,
    check_list_sessions_orders_and_summarizes,
    check_set_title_overrides_the_first_message,
)
