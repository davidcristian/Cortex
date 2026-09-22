import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import cast

import contract
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis

from cortex_core import InMemorySessionStore, Role, SessionStore, SessionStoreError
from cortex_core.sessions import TITLE_MAX, HistoryRecap
from cortex_session import DEFAULT_REDIS_URL, RedisSessionStore


@pytest.fixture(params=["in-memory", "redis"])
def store(request: pytest.FixtureRequest) -> SessionStore:
    """A fresh store of each implementation; the suite below runs against both."""
    if request.param == "in-memory":
        return InMemorySessionStore()
    return RedisSessionStore(FakeAsyncRedis(server=FakeServer()))


@pytest.mark.parametrize("check", contract.ALL_CHECKS)
async def test_session_store_contract(
    store: SessionStore, check: Callable[[SessionStore], Awaitable[None]]
) -> None:
    await check(store)


async def test_delete_leaves_no_orphaned_redis_key_or_index_member() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "hi"))
    await store.set_title("s", "a title")
    await store.set_hoisted("s", hoisted=True)

    async def session_keys() -> list[bytes]:
        raw = await client.keys("cortex:session:s:*")  # pyright: ignore[reportUnknownMemberType]
        return cast("list[bytes]", raw)

    assert await session_keys()
    assert await client.zscore("cortex:sessions", "s") is not None
    assert await client.sismember("cortex:sessions:hoisted", "s")

    await store.delete("s")

    assert await session_keys() == []
    assert await client.zscore("cortex:sessions", "s") is None
    assert not await client.sismember("cortex:sessions:hoisted", "s")


async def test_connection_failure_on_delete_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="deleting session 's'") as excinfo:
        await _disconnected_store().delete("s")
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_list_sessions_is_empty_for_a_store_with_no_sessions(store: SessionStore) -> None:
    assert list(await store.list_sessions(limit=10)) == []


async def test_list_sessions_respects_the_limit(store: SessionStore) -> None:
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
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("real", contract.make_message(Role.USER, "hi"))
    await client.zadd("cortex:sessions", {"ghost": 9999999999.0})
    summaries = await store.list_sessions(limit=10)
    assert [s.session_id for s in summaries] == ["real"]


async def test_set_title_persists_under_its_own_key_and_is_read_back_truncated() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "first user message"))
    await store.set_title("s", "T" * (TITLE_MAX + 20))
    stored = cast("bytes", await client.get("cortex:session:s:title"))
    assert stored.decode("utf-8") == "T" * (TITLE_MAX + 20)
    (summary,) = await store.list_sessions(limit=10)
    assert summary.title == "T" * TITLE_MAX + "…"


async def test_connection_failure_on_set_title_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="setting the title for session 's'") as excinfo:
        await _disconnected_store().set_title("s", "a title")
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_set_hoisted_persists_under_the_hoisted_set_key() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.set_hoisted("s", hoisted=True)
    assert await client.sismember("cortex:sessions:hoisted", "s")
    await store.set_hoisted("s", hoisted=True)
    assert await client.scard("cortex:sessions:hoisted") == 1
    await store.set_hoisted("s", hoisted=False)
    assert not await client.sismember("cortex:sessions:hoisted", "s")


async def test_list_sessions_unions_a_hoisted_chat_older_than_the_window() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    base = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)
    await store.append("old", contract.make_message(Role.USER, "old", at=base))
    for offset, session_id in enumerate(("n1", "n2", "n3"), start=1):
        at = datetime(2026, 7, 3, 8 + offset, tzinfo=UTC)
        await store.append(session_id, contract.make_message(Role.USER, "new", at=at))
    await store.set_hoisted("old", hoisted=True)
    ids = [s.session_id for s in await store.list_sessions(limit=3)]
    assert ids == ["old", "n3", "n2", "n1"]


async def test_list_sessions_skips_a_dangling_hoisted_entry() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("real", contract.make_message(Role.USER, "hi"))
    await client.sadd("cortex:sessions:hoisted", "ghost")
    summaries = await store.list_sessions(limit=10)
    assert [s.session_id for s in summaries] == ["real"]


async def test_connection_failure_on_set_hoisted_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="hoisting or lowering session 's'") as excinfo:
        await _disconnected_store().set_hoisted("s", hoisted=True)
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_connection_failure_on_list_sessions_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="listing sessions") as excinfo:
        await _disconnected_store().list_sessions(limit=10)
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_a_failure_reading_the_ends_wraps_the_cause() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    await client.set("cortex:session:collided:messages", "not a list at all")
    await client.zadd("cortex:sessions", {"collided": 1.0})
    with pytest.raises(SessionStoreError, match="listing sessions") as excinfo:
        await RedisSessionStore(client).list_sessions(limit=10)
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ResponseError)


async def test_list_sessions_reads_only_the_ends_of_a_session() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "the first message"))
    await client.rpush("cortex:session:s:messages", "not json at all")
    await store.append("s", contract.make_message(Role.ASSISTANT, "the last message"))
    (summary,) = await store.list_sessions(limit=10)
    assert (summary.title, summary.preview) == ("the first message", "the last message")
    with pytest.raises(SessionStoreError, match="corrupt session record at index 1"):
        await store.history("s")


async def test_a_corrupt_end_record_still_fails_a_listing_at_its_true_index() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "hi"))
    await client.rpush("cortex:session:s:messages", _record(text="middle"))
    await client.rpush("cortex:session:s:messages", _record(v=2))
    with pytest.raises(SessionStoreError, match=r"index 2: kind 'message' v 2"):
        await store.list_sessions(limit=10)


async def test_a_corrupt_first_record_fails_a_listing_at_index_zero() -> None:
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
        '[{"role": "user"}]',
        '{"role": "user", "text": "hi", "turn_id": "t-1"}',
        '{"role": "user", "text": "hi", "at": "2026-07-03T12:00:00", "turn_id": "t"}',
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
    client = FakeAsyncRedis(server=FakeServer())
    payload = _record(annotations=["future", "optional", "keys"], confidence=0.9)
    await client.rpush("cortex:session:s:messages", payload)
    (loaded,) = await RedisSessionStore(client).history("s")
    assert loaded.role is Role.USER
    assert loaded.text == "hi"
    assert loaded.turn_id == "t-1"


async def test_pre_versioning_records_decode_as_v1_messages() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    await client.rpush("cortex:session:s:messages", _record(v=None, kind=None))
    (loaded,) = await RedisSessionStore(client).history("s")
    assert loaded.text == "hi"


async def test_unknown_kind_raises_naming_index_kind_and_version() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "hi"))
    await client.rpush("cortex:session:s:messages", _record(kind="tool_call"))
    with pytest.raises(
        SessionStoreError, match=r"index 1: kind 'tool_call' v 1 .*kind 'message' v 1"
    ):
        await store.history("s")


async def test_unsupported_version_raises_naming_index_kind_and_version() -> None:
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

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    store = RedisSessionStore.from_url("redis://example.invalid:6390/7")
    await contract.check_append_then_history_order(store)
    await store.aclose()
    RedisSessionStore.from_url()
    assert seen == ["redis://example.invalid:6390/7", DEFAULT_REDIS_URL]


async def test_recap_persists_as_one_versioned_document_under_its_own_key() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.set_recap("s", HistoryRecap(text="they settled on Friday", covers=12))
    raw = cast("bytes", await client.get("cortex:session:s:recap"))
    assert json.loads(raw) == {
        "v": 1,
        "kind": "recap",
        "text": "they settled on Friday",
        "covers": 12,
    }


async def test_deleting_a_session_removes_its_recap_key() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await store.append("s", contract.make_message(Role.USER, "hi"))
    await store.set_recap("s", HistoryRecap(text="a private account", covers=2))
    assert await client.exists("cortex:session:s:recap")
    await store.delete("s")
    assert not await client.exists("cortex:session:s:recap")


async def test_an_unreadable_recap_kind_or_version_fails_loudly() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await client.set("cortex:session:s:recap", json.dumps({"v": 2, "kind": "recap", "text": "x"}))
    with pytest.raises(SessionStoreError, match=r"unreadable recap .*kind 'recap' v 2"):
        await store.recap("s")


async def test_a_corrupt_recap_document_names_the_session() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await client.set("cortex:session:s:recap", "{not json")
    with pytest.raises(SessionStoreError, match="corrupt recap for session 's'"):
        await store.recap("s")


async def test_a_recap_document_that_would_be_an_invalid_value_is_corrupt() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    await client.set(
        "cortex:session:s:recap", json.dumps({"v": 1, "kind": "recap", "text": "x", "covers": 0})
    )
    with pytest.raises(SessionStoreError, match="corrupt recap for session 's'"):
        await store.recap("s")


async def test_connection_failure_on_set_recap_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="setting the recap for session 's'") as excinfo:
        await _disconnected_store().set_recap("s", HistoryRecap(text="a", covers=1))
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_connection_failure_on_recap_read_wraps_the_cause() -> None:
    with pytest.raises(SessionStoreError, match="recap read for session 's'") as excinfo:
        await _disconnected_store().recap("s")
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)
