"""One behavior suite over BOTH SessionStore implementations, plus adapter error paths.

The in-memory fake and the Redis adapter (backed by fakeredis) must be observably
interchangeable behind the port. That is this slice's ports-before-adapters gate.
"""

import json
from datetime import UTC, datetime
from typing import cast

import contract
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis

from cortex_core import InMemorySessionStore, Role, SessionStore, SessionStoreError
from cortex_core.sessions import TITLE_MAX
from cortex_session import DEFAULT_REDIS_URL, RedisSessionStore


@pytest.fixture(params=["in-memory", "redis"])
def store(request: pytest.FixtureRequest) -> SessionStore:
    """A fresh store of each implementation; the suite below runs against both."""
    if request.param == "in-memory":
        return InMemorySessionStore()
    return RedisSessionStore(FakeAsyncRedis(server=FakeServer()))


async def test_unknown_session_has_empty_history(store: SessionStore) -> None:
    await contract.check_empty_history(store)


async def test_append_then_history_preserves_order(store: SessionStore) -> None:
    await contract.check_append_then_history_order(store)


async def test_sessions_are_isolated(store: SessionStore) -> None:
    await contract.check_multi_session_isolation(store)


async def test_messages_roundtrip_with_timezone_fidelity(store: SessionStore) -> None:
    await contract.check_roundtrip_fidelity(store)


async def test_list_sessions_orders_and_summarizes(store: SessionStore) -> None:
    await contract.check_list_sessions_orders_and_summarizes(store)


async def test_set_title_overrides_the_first_message(store: SessionStore) -> None:
    await contract.check_set_title_overrides_the_first_message(store)


async def test_delete_removes_the_session(store: SessionStore) -> None:
    await contract.check_delete_removes_the_session(store)


async def test_delete_leaves_no_orphaned_redis_key_or_index_member() -> None:
    """Distrust-green: inspect Redis directly and prove the delete leaves NOTHING behind.

    The contract check drives the delete through the port; this asserts against the raw keyspace,
    so it reddens if the messages key, the title key, or the recency-index member survives.
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "hi"))
    await store.set_title("s", "a title")

    async def session_keys() -> list[bytes]:
        # keys()'s return is a partially-Any union; this call only ever reads bytes members back.
        raw = await client.keys("cortex:session:s:*")  # pyright: ignore[reportUnknownMemberType]
        return cast("list[bytes]", raw)

    assert await session_keys()  # both the messages and title keys exist before the delete
    assert await client.zscore("cortex:sessions", "s") is not None  # indexed before

    await store.delete("s")

    assert await session_keys() == []  # messages AND title gone
    assert await client.zscore("cortex:sessions", "s") is None  # index member gone


async def test_connection_failure_on_delete_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="deleting session 's'") as excinfo:
        await _disconnected_store().delete("s")
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_list_sessions_is_empty_for_a_store_with_no_sessions(store: SessionStore) -> None:
    assert list(await store.list_sessions(limit=10)) == []


async def test_list_sessions_respects_the_limit(store: SessionStore) -> None:
    """Only the newest `limit` sessions come back, most-recently-active first."""
    for hour, session_id in enumerate(("oldest", "middle", "newest")):
        await store.append(
            session_id,
            contract.make_message(
                Role.USER, session_id, at=datetime(2026, 7, 3, 9 + hour, tzinfo=UTC)
            ),
        )
    summaries = await store.list_sessions(limit=2)
    assert [s.session_id for s in summaries] == ["newest", "middle"]


async def test_list_sessions_skips_a_dangling_index_entry() -> None:
    """A session id in the recency index whose message list is gone is skipped, not fatal."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("real", contract.make_message(Role.USER, "hi"))
    await client.zadd("cortex:sessions", {"ghost": 9999999999.0})  # indexed, but no messages
    summaries = await store.list_sessions(limit=10)
    assert [s.session_id for s in summaries] == ["real"]


async def test_set_title_persists_under_its_own_key_and_is_read_back_truncated() -> None:
    """The title is a plain string under `:title`, and an over-wide one is bounded at read time."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "first user message"))
    await store.set_title("s", "T" * (TITLE_MAX + 20))
    stored = cast("bytes", await client.get("cortex:session:s:title"))
    assert stored.decode("utf-8") == "T" * (TITLE_MAX + 20)  # stored verbatim, bounded on read
    (summary,) = await store.list_sessions(limit=10)
    assert summary.title == "T" * TITLE_MAX + "…"


async def test_connection_failure_on_set_title_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="setting the title for session 's'") as excinfo:
        await _disconnected_store().set_title("s", "a title")
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_connection_failure_on_list_sessions_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="listing sessions") as excinfo:
        await _disconnected_store().list_sessions(limit=10)
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_a_failure_reading_the_ends_wraps_the_cause() -> None:
    """The batched end-reads are their own failure point, not just the index read.

    A listed key that is not a list (a layout collision) fails inside the pipeline, after
    the recency index has already answered, and still crosses the port as one wrapped
    listing failure rather than a raw redis error.
    """
    client = FakeAsyncRedis(server=FakeServer())
    await client.set("cortex:session:collided:messages", "not a list at all")
    await client.zadd("cortex:sessions", {"collided": 1.0})
    with pytest.raises(SessionStoreError, match="listing sessions") as excinfo:
        await RedisSessionStore(client).list_sessions(limit=10)
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ResponseError)


async def test_list_sessions_reads_only_the_ends_of_a_session() -> None:
    """A corrupt record BETWEEN the ends cannot take the chat list down (ADR-0021).

    The listing is bounded to each session's two ends, so it never decodes the middle.
    `history` reads the whole list and still fails loudly on the same record, so the
    context a turn is built from keeps its fail-loud guarantee.
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "the first message"))
    await client.rpush("cortex:session:s:messages", "not json at all")  # index 1
    await store.append("s", contract.make_message(Role.ASSISTANT, "the last message"))
    (summary,) = await store.list_sessions(limit=10)
    assert (summary.title, summary.preview) == ("the first message", "the last message")
    with pytest.raises(SessionStoreError, match="corrupt session record at index 1"):
        await store.history("s")


async def test_a_corrupt_end_record_still_fails_a_listing_at_its_true_index() -> None:
    """The ends are decoded, so a bad one is fatal and named by its real position.

    The tail's index comes from the session's length (read with the pair), not from the
    position it lands at in the bounded read.
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "hi"))
    await client.rpush("cortex:session:s:messages", _record(text="middle"))  # index 1
    await client.rpush("cortex:session:s:messages", _record(v=2))  # index 2, the tail
    with pytest.raises(SessionStoreError, match=r"index 2: kind 'message' v 2"):
        await store.list_sessions(limit=10)


async def test_a_corrupt_first_record_fails_a_listing_at_index_zero() -> None:
    """The head is decoded from position 0 of the list, whatever follows it."""
    client = FakeAsyncRedis(server=FakeServer())
    await client.rpush("cortex:session:s:messages", "not json at all", _record())
    await client.zadd("cortex:sessions", {"s": 1.0})
    with pytest.raises(SessionStoreError, match="corrupt session record at index 0"):
        await RedisSessionStore(client).list_sessions(limit=10)


def _disconnected_store() -> RedisSessionStore:
    server = FakeServer()
    server.connected = False
    return RedisSessionStore(FakeAsyncRedis(server=server))


async def test_connection_failure_on_append_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="append to session 's'") as excinfo:
        await _disconnected_store().append("s", contract.make_message(Role.USER, "hi"))
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_connection_failure_on_history_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="history read for session 's'") as excinfo:
        await _disconnected_store().history("s")
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_close_failure_wraps_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeAsyncRedis(server=FakeServer())

    async def failing_aclose() -> None:
        msg = "boom"
        raise redis_exceptions.ConnectionError(msg)

    monkeypatch.setattr(client, "aclose", failing_aclose)
    with pytest.raises(SessionStoreError, match="closing") as excinfo:
        await RedisSessionStore(client).aclose()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


@pytest.mark.parametrize(
    "payload",
    [
        "not json at all",
        '[{"role": "user"}]',  # valid JSON, but not an object
        '{"role": "user", "text": "hi", "turn_id": "t-1"}',  # missing "at"
        '{"role": "user", "text": "hi", "at": "2026-07-03T12:00:00", "turn_id": "t"}',  # naive
    ],
)
async def test_corrupt_record_wraps_into_session_store_error(payload: str) -> None:
    client = FakeAsyncRedis(server=FakeServer())
    await client.rpush("cortex:session:s:messages", payload)
    with pytest.raises(SessionStoreError, match="corrupt session record at index 0"):
        await RedisSessionStore(client).history("s")


def _record(**overrides: object) -> str:
    fields: dict[str, object] = {
        "v": 1,
        "kind": "message",
        "role": "user",
        "text": "hi",
        "at": "2026-07-03T12:00:00+00:00",
        "turn_id": "t-1",
    }
    fields.update(overrides)
    return json.dumps({k: v for k, v in fields.items() if v is not None})


async def test_records_are_written_with_schema_version_and_kind() -> None:
    """The escape hatch is IN every persisted record: v/kind roundtrip through Redis."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    original = contract.make_message(Role.USER, "hi")
    await store.append("s", original)
    (raw,) = await client.lrange("cortex:session:s:messages", 0, -1)
    fields: dict[str, object] = json.loads(raw)
    assert fields["v"] == 1
    assert fields["kind"] == "message"
    assert list(await store.history("s")) == [original]


async def test_unknown_extra_keys_are_ignored_for_forward_compatibility() -> None:
    """A v1 message with keys this reader has never heard of still decodes cleanly."""
    client = FakeAsyncRedis(server=FakeServer())
    payload = _record(annotations=["future", "optional", "keys"], confidence=0.9)
    await client.rpush("cortex:session:s:messages", payload)
    (loaded,) = await RedisSessionStore(client).history("s")
    assert loaded.role is Role.USER
    assert loaded.text == "hi"
    assert loaded.turn_id == "t-1"


async def test_pre_versioning_records_decode_as_v1_messages() -> None:
    """Records written before v/kind existed keep reading back (missing == v1 message)."""
    client = FakeAsyncRedis(server=FakeServer())
    await client.rpush("cortex:session:s:messages", _record(v=None, kind=None))
    (loaded,) = await RedisSessionStore(client).history("s")
    assert loaded.text == "hi"


async def test_unknown_kind_raises_naming_index_kind_and_version() -> None:
    """A record kind this reader does not know fails loudly, never silently skipped."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "hi"))  # index 0 is fine
    await client.rpush("cortex:session:s:messages", _record(kind="tool_call"))
    with pytest.raises(
        SessionStoreError, match=r"index 1: kind 'tool_call' v 1 .*kind 'message' v 1"
    ):
        await store.history("s")


async def test_unsupported_version_raises_naming_index_kind_and_version() -> None:
    """A record version newer than this reader fails loudly, never silently skipped."""
    client = FakeAsyncRedis(server=FakeServer())
    await client.rpush("cortex:session:s:messages", _record(v=2))
    with pytest.raises(
        SessionStoreError, match=r"index 0: kind 'message' v 2 .*kind 'message' v 1"
    ):
        await RedisSessionStore(client).history("s")


async def test_from_url_wires_a_client_for_the_given_or_default_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def fake_from_url(url: str) -> FakeAsyncRedis:
        seen.append(url)
        return FakeAsyncRedis(server=FakeServer())

    # Patch the classmethod on the class the adapter calls into; the adapter must
    # forward the given (or default) URL untouched and wrap whatever client it gets.
    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    store = RedisSessionStore.from_url("redis://example.invalid:6390/7")
    await contract.check_append_then_history_order(store)
    await store.aclose()
    RedisSessionStore.from_url()
    assert seen == ["redis://example.invalid:6390/7", DEFAULT_REDIS_URL]
