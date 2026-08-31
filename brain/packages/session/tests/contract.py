"""Shared SessionStore behavior checks. Every implementation must pass all of them."""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from cortex_core import ImagePart, Message, Role, SessionStore, SessionStoreError
from cortex_core.sessions import HistoryRecap

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
    # Equality between aware datetimes compares instants, so the offset is asserted on its own:
    # a store that quietly converted to UTC would otherwise pass this check.
    assert loaded.at.utcoffset() == timedelta(hours=5, minutes=30)


async def check_list_sessions_orders_and_summarizes(store: SessionStore) -> None:
    """list_sessions returns recent chats newest-active first, with a derived title/preview."""
    older, newer = _session_id(), _session_id()
    early = datetime(2026, 7, 3, 9, 0, tzinfo=UTC)
    late = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
    await store.append(older, make_message(Role.USER, "question about cats", at=early, turn_id="a"))
    await store.append(older, make_message(Role.ASSISTANT, "cats are great", at=early, turn_id="a"))
    await store.append(newer, make_message(Role.USER, "question about dogs", at=late, turn_id="b"))
    mine = [s for s in await store.list_sessions(limit=50) if s.session_id in {older, newer}]
    assert [s.session_id for s in mine] == [newer, older]
    by_id = {s.session_id: s for s in mine}
    assert by_id[older].title == "question about cats"
    assert by_id[older].preview == "cats are great"
    assert by_id[older].last_activity == early
    assert by_id[newer].title == "question about dogs"
    assert by_id[newer].preview == "question about dogs"
    assert by_id[newer].last_activity == late


async def check_set_title_overrides_the_first_message(store: SessionStore) -> None:
    """A stored title wins over the first-message derivation; the preview is unaffected."""
    session_id = _session_id()
    await store.append(session_id, make_message(Role.USER, "a rambly first question about cats"))
    await store.append(session_id, make_message(Role.ASSISTANT, "cats sleep a lot"))

    async def title_and_preview() -> tuple[str, str]:
        (mine,) = [s for s in await store.list_sessions(limit=50) if s.session_id == session_id]
        return mine.title, mine.preview

    assert await title_and_preview() == ("a rambly first question about cats", "cats sleep a lot")
    await store.set_title(session_id, "Cat sleep habits")
    assert await title_and_preview() == ("Cat sleep habits", "cats sleep a lot")
    await store.set_title(session_id, "Feline naps")
    assert await title_and_preview() == ("Feline naps", "cats sleep a lot")


async def check_delete_removes_the_session(store: SessionStore) -> None:
    """Deleting a chat forgets every trace of it, is idempotent, and spares other chats."""
    doomed, kept = _session_id(), _session_id()
    await store.append(doomed, make_message(Role.USER, "secret question", at=_AT, turn_id="d"))
    await store.append(doomed, make_message(Role.ASSISTANT, "secret answer", at=_AT, turn_id="d"))
    await store.set_title(doomed, "A private label")
    await store.set_pinned(doomed, pinned=True)
    await store.set_recap(doomed, HistoryRecap(text="they discussed the secret", covers=2))
    await store.append(kept, make_message(Role.USER, "an unrelated chat", at=_AT, turn_id="k"))

    await store.delete(doomed)

    assert list(await store.history(doomed)) == []
    assert await store.recap(doomed) is None
    listed = {s.session_id for s in await store.list_sessions(limit=50)}
    assert doomed not in listed
    assert kept in listed
    await store.delete(doomed)

    await store.append(doomed, make_message(Role.USER, "a brand new topic", at=_AT, turn_id="n"))
    (reborn,) = [s for s in await store.list_sessions(limit=50) if s.session_id == doomed]
    assert reborn.title == "a brand new topic"
    assert reborn.pinned is False


async def check_set_pinned_marks_and_clears_the_summary(store: SessionStore) -> None:
    """``set_pinned`` toggles ``SessionSummary.pinned``; setting the same value twice is a no-op."""
    session_id = _session_id()
    await store.append(session_id, make_message(Role.USER, "toggle my pin"))

    async def is_pinned() -> bool:
        (mine,) = [s for s in await store.list_sessions(limit=50) if s.session_id == session_id]
        return mine.pinned

    assert await is_pinned() is False
    await store.set_pinned(session_id, pinned=True)
    assert await is_pinned() is True
    await store.set_pinned(session_id, pinned=True)
    assert await is_pinned() is True
    await store.set_pinned(session_id, pinned=False)
    assert await is_pinned() is False


async def check_a_pinned_chat_escapes_the_recency_window(store: SessionStore) -> None:
    """A `pinned` chat older than the recency window still lists, above the recency group."""
    old = _session_id()
    newer = [_session_id() for _ in range(3)]
    base = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)
    await store.append(old, make_message(Role.USER, "pinned old topic", at=base, turn_id="o"))
    for offset, session_id in enumerate(newer, start=1):
        at = base + timedelta(hours=offset)
        await store.append(session_id, make_message(Role.USER, "recent", at=at, turn_id="n"))
    await store.set_pinned(old, pinned=True)

    listed = await store.list_sessions(limit=3)

    ids = [s.session_id for s in listed]
    assert old in ids
    assert ids.count(old) == 1
    by_id = {s.session_id: s for s in listed}
    assert by_id[old].pinned is True
    old_index = ids.index(old)
    first_unpinned = next(i for i, s in enumerate(listed) if not s.pinned)
    assert old_index < first_unpinned
    mine_newer = [s for s in listed if s.session_id in set(newer)]
    assert [s.session_id for s in mine_newer] == list(reversed(newer))
    assert all(s.pinned is False for s in mine_newer)


async def check_a_pinned_recent_chat_is_not_duplicated(store: SessionStore) -> None:
    """A chat that is both `pinned` and inside the recency window appears exactly once."""
    session_id = _session_id()
    await store.append(session_id, make_message(Role.USER, "pinned and recent"))
    await store.set_pinned(session_id, pinned=True)
    listed = await store.list_sessions(limit=50)
    matches = [s for s in listed if s.session_id == session_id]
    assert len(matches) == 1
    assert matches[0].pinned is True


async def check_append_refuses_an_image_bearing_message(store: SessionStore) -> None:
    """No store persists images: they are turn-local and go away with the turn."""
    session_id = _session_id()
    picture = ImagePart(data=b"\x89PNG", mime_type="image/png", width=8, height=8)
    message = Message(
        role=Role.TOOL,
        text="screen capture",
        at=_AT,
        turn_id="t-1",
        tool_call_id="c-1",
        images=(picture,),
    )
    with pytest.raises(SessionStoreError, match="never persists images"):
        await store.append(session_id, message)
    assert list(await store.history(session_id)) == []


async def check_recap_is_absent_then_roundtrips_and_overwrites(store: SessionStore) -> None:
    """A session has no recap until one is written; then it reads back whole and last write wins."""
    session_id = _session_id()
    await store.append(session_id, make_message(Role.USER, "the opening question"))

    assert await store.recap(session_id) is None

    first = HistoryRecap(text="They agreed to ship on Friday. Budget is 4,000.", covers=6)
    await store.set_recap(session_id, first)
    assert await store.recap(session_id) == first

    later = HistoryRecap(text="They agreed to ship on Friday, then moved it to Monday.", covers=14)
    await store.set_recap(session_id, later)
    assert await store.recap(session_id) == later


async def check_recaps_do_not_leak_between_sessions(store: SessionStore) -> None:
    """One chat's recap is never another's: it is keyed by the session it summarizes."""
    one, two = _session_id(), _session_id()
    await store.set_recap(one, HistoryRecap(text="about cats", covers=2))
    assert await store.recap(two) is None
    await store.set_recap(two, HistoryRecap(text="about dogs", covers=4))
    assert (await store.recap(one)) == HistoryRecap(text="about cats", covers=2)


async def check_recap_survives_a_reconnect(store: SessionStore) -> None:
    """A recap read back after the write is store state, not process state (the hard rule)."""
    session_id = _session_id()
    written = HistoryRecap(text="a paragraph the writing model no longer remembers", covers=8)
    await store.set_recap(session_id, written)
    reloaded = await store.recap(session_id)
    assert reloaded is not None
    assert reloaded.text == written.text
    assert reloaded.covers == written.covers


ALL_CHECKS = (
    check_empty_history,
    check_append_then_history_order,
    check_multi_session_isolation,
    check_roundtrip_fidelity,
    check_list_sessions_orders_and_summarizes,
    check_set_title_overrides_the_first_message,
    check_delete_removes_the_session,
    check_set_pinned_marks_and_clears_the_summary,
    check_a_pinned_chat_escapes_the_recency_window,
    check_a_pinned_recent_chat_is_not_duplicated,
    check_append_refuses_an_image_bearing_message,
    check_recap_is_absent_then_roundtrips_and_overwrites,
    check_recaps_do_not_leak_between_sessions,
    check_recap_survives_a_reconnect,
)
