"""Shared SessionStore behavior checks. Every implementation must pass all of them.

Driven by the parametrized contract tests (in-memory fake + fakeredis-backed Redis
adapter) and by the integration-marked live-Redis test. Both hand every check the same
precondition, an EMPTY store: the fixture builds a fresh one per test, and the live run
works in a database of its own that it empties after every check (tests/live_redis.py).
Each check still generates its own session ids, all prefixed `contract-`, so a record that
outlives a run is recognizable on sight.
"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from cortex_core import ImagePart, Message, Role, SessionStore, SessionStoreError

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

    It filters the global list down to the two sessions it created, then asserts their
    relative order and summaries, the filtered sublist of a sorted list being sorted too.
    Filtering is belt and braces now that both runners start it from an empty store: what
    actually broke this check was being crowded out of the `limit=50` window by more-recent
    sessions it never created, which no filter can survive and only an empty store prevents
    (see tests/live_redis.py)."""
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
    back through ``list_sessions``. It filters to its own id, so the read names one row.
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


async def check_delete_removes_the_session(store: SessionStore) -> None:
    """Deleting a chat forgets every trace of it, is idempotent, and spares other chats.

    The destructive "forget this chat" write (ADR-0021 delete addendum). After delete: its
    history reads empty (the unknown-session behavior), it is gone from ``list_sessions``, and a
    stored title override AND a pin no longer apply (a chat later re-created under the same id
    derives its title from the first message and lists unpinned, proving the ``:title`` key and the
    pinned-set member went too, not just the messages). A second delete of the now-absent chat is a
    no-op, and an untouched sibling chat is unaffected.
    """
    doomed, kept = _session_id(), _session_id()
    await store.append(doomed, make_message(Role.USER, "secret question", at=_AT, turn_id="d"))
    await store.append(doomed, make_message(Role.ASSISTANT, "secret answer", at=_AT, turn_id="d"))
    await store.set_title(doomed, "A private label")
    await store.set_pinned(doomed, pinned=True)
    await store.append(kept, make_message(Role.USER, "an unrelated chat", at=_AT, turn_id="k"))

    await store.delete(doomed)

    assert list(await store.history(doomed)) == []  # the transcript is gone
    listed = {s.session_id for s in await store.list_sessions(limit=50)}
    assert doomed not in listed  # dropped from the recency index
    assert kept in listed  # a sibling chat is untouched
    await store.delete(doomed)  # deleting an already-gone chat is a no-op, not an error

    # Re-create a chat under the same id: its title derives from the first message and it lists
    # unpinned, so neither the old override nor the old pin survived the delete (both keys removed).
    await store.append(doomed, make_message(Role.USER, "a brand new topic", at=_AT, turn_id="n"))
    (reborn,) = [s for s in await store.list_sessions(limit=50) if s.session_id == doomed]
    assert reborn.title == "a brand new topic"
    assert reborn.pinned is False


async def check_set_pinned_marks_and_clears_the_summary(store: SessionStore) -> None:
    """``set_pinned`` toggles ``SessionSummary.pinned``, idempotent by value (pinning addendum).

    A chat lists unpinned by default; pinning marks it, pinning again is a no-op, and unpinning
    clears it. It filters to its own id, so the read names one row.
    """
    session_id = _session_id()
    await store.append(session_id, make_message(Role.USER, "toggle my pin"))

    async def is_pinned() -> bool:
        (mine,) = [s for s in await store.list_sessions(limit=50) if s.session_id == session_id]
        return mine.pinned

    assert await is_pinned() is False  # unpinned by default
    await store.set_pinned(session_id, pinned=True)
    assert await is_pinned() is True
    await store.set_pinned(session_id, pinned=True)  # idempotent: re-pinning is a no-op
    assert await is_pinned() is True
    await store.set_pinned(session_id, pinned=False)
    assert await is_pinned() is False


async def check_a_pinned_chat_escapes_the_recency_window(store: SessionStore) -> None:
    """A pinned chat OLDER than the recency window still lists, above the recency group.

    This is the whole point of pinning (ADR-0021 pinning addendum), and the flagship distrust-green
    check: with a window of three and three newer chats, the old chat is crowded out of recency and
    appears ONLY because it is pinned. Removing the read-path union (so ``list_sessions`` returns
    just the recency window) reddens the ``old in ids`` assertion. Its three newer chats have to BE
    the window, which is the assumption no filtering can rescue and the reason the live run gets a
    database of its own rather than a share of the brain's (tests/live_redis.py).
    """
    old = _session_id()
    newer = [_session_id() for _ in range(3)]
    base = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)
    await store.append(old, make_message(Role.USER, "pinned old topic", at=base, turn_id="o"))
    for offset, session_id in enumerate(newer, start=1):
        at = base + timedelta(hours=offset)
        await store.append(session_id, make_message(Role.USER, "recent", at=at, turn_id="n"))
    await store.set_pinned(old, pinned=True)

    listed = await store.list_sessions(limit=3)  # a window filled by the three newer chats

    ids = [s.session_id for s in listed]
    assert old in ids  # the pin rescued it from outside the recency window
    assert ids.count(old) == 1  # and exactly once
    by_id = {s.session_id: s for s in listed}
    assert by_id[old].pinned is True
    # It sorts above every unpinned chat present, the pinned-first grouping.
    old_index = ids.index(old)
    first_unpinned = next(i for i, s in enumerate(listed) if not s.pinned)
    assert old_index < first_unpinned
    # The newer chats list unpinned and newest-active first among themselves.
    mine_newer = [s for s in listed if s.session_id in set(newer)]
    assert [s.session_id for s in mine_newer] == list(reversed(newer))
    assert all(s.pinned is False for s in mine_newer)


async def check_a_pinned_recent_chat_is_not_duplicated(store: SessionStore) -> None:
    """A chat both pinned AND inside the recency window appears exactly once (pinning addendum).

    The union deduplicates ids before fetching, so a pinned-and-recent chat is one row, not two.
    Removing the dedup (concatenating the window and the pinned set) reddens the count assertion.
    """
    session_id = _session_id()
    await store.append(session_id, make_message(Role.USER, "pinned and recent"))
    await store.set_pinned(session_id, pinned=True)
    listed = await store.list_sessions(limit=50)  # a wide window, so the chat is also in recency
    matches = [s for s in listed if s.session_id == session_id]
    assert len(matches) == 1
    assert matches[0].pinned is True


async def check_append_refuses_an_image_bearing_message(store: SessionStore) -> None:
    """No store ever persists pixels (ADR-0029): they are turn-local and die with the turn.

    ``Message`` already refuses images on every role but ``TOOL``, so the message this check builds
    is the one a caller could plausibly reach a store with: the ``Role.TOOL`` message the tool
    loop puts a capture on. The store has to refuse it loudly, because the record schema has no
    field for an image and would otherwise drop the picture in silence.
    """
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
)
