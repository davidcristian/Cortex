import asyncio
from typing import cast

import contract
import pytest
from fakeredis import FakeAsyncRedis, FakeServer

from cortex_core import Role, SessionStoreError
from cortex_session import RedisSessionStore

OLD_KEY = "cortex:sessions:pinned"
KEY = "cortex:sessions:hoisted"


async def _members(client: FakeAsyncRedis, key: str) -> set[str]:
    raw = cast("set[bytes]", await client.smembers(key))  # pyright: ignore[reportUnknownMemberType]
    return {member.decode("utf-8") for member in raw}


async def _store_with_chats(*session_ids: str) -> tuple[FakeAsyncRedis, RedisSessionStore]:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisSessionStore(client)
    for session_id in session_ids:
        await store.append(session_id, contract.make_message(Role.USER, session_id))
    return client, store


async def test_the_first_listing_moves_every_old_member_into_the_hoisted_set() -> None:
    client, store = await _store_with_chats("a", "b", "c")
    await client.sadd(OLD_KEY, "a", "b")
    await client.sadd(KEY, "c")
    listed = await store.list_sessions(limit=10)
    assert {s.session_id for s in listed if s.hoisted} == {"a", "b", "c"}
    assert await _members(client, KEY) == {"a", "b", "c"}
    assert await client.exists(OLD_KEY) == 0


async def test_an_absent_old_set_leaves_the_hoisted_set_as_it_was() -> None:
    client, store = await _store_with_chats("a", "c")
    await client.sadd(KEY, "c")
    listed = await store.list_sessions(limit=10)
    assert [s.session_id for s in listed if s.hoisted] == ["c"]
    assert await _members(client, KEY) == {"c"}
    assert await client.exists(OLD_KEY) == 0


async def test_a_store_with_neither_set_creates_no_key() -> None:
    client, store = await _store_with_chats("a")
    await store.list_sessions(limit=10)
    assert await client.exists(KEY, OLD_KEY) == 0


async def test_two_stores_starting_at_once_keep_every_member() -> None:
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    await client.sadd(OLD_KEY, "a", "b")
    first = RedisSessionStore(FakeAsyncRedis(server=server))
    second = RedisSessionStore(FakeAsyncRedis(server=server))
    await asyncio.gather(first.set_hoisted("c", hoisted=True), second.list_sessions(limit=10))
    assert await _members(client, KEY) == {"a", "b", "c"}
    assert await client.exists(OLD_KEY) == 0


async def test_a_later_store_does_not_raise_a_chat_lowered_after_the_move() -> None:
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    await client.sadd(OLD_KEY, "a", "b")
    await RedisSessionStore(FakeAsyncRedis(server=server)).set_hoisted("a", hoisted=False)
    await RedisSessionStore(FakeAsyncRedis(server=server)).list_sessions(limit=10)
    assert await _members(client, KEY) == {"b"}


@pytest.mark.parametrize("hoisted", [True, False])
async def test_set_hoisted_moves_the_old_set_before_it_writes(*, hoisted: bool) -> None:
    client, store = await _store_with_chats()
    await client.sadd(OLD_KEY, "a")
    await store.set_hoisted("a", hoisted=hoisted)
    assert await _members(client, KEY) == ({"a"} if hoisted else set())
    assert await client.exists(OLD_KEY) == 0


async def test_delete_moves_the_old_set_before_it_removes_the_member() -> None:
    client, store = await _store_with_chats("a")
    await client.sadd(OLD_KEY, "a")
    await store.delete("a")
    assert await client.exists(KEY, OLD_KEY) == 0


async def test_the_move_runs_once_per_store() -> None:
    client, store = await _store_with_chats("a")
    await store.list_sessions(limit=10)
    await client.sadd(OLD_KEY, "a")
    await store.list_sessions(limit=10)
    assert await _members(client, OLD_KEY) == {"a"}
    assert await client.exists(KEY) == 0


async def test_a_failed_move_is_tried_again_on_the_next_call() -> None:
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    await client.sadd(OLD_KEY, "a")
    store = RedisSessionStore(FakeAsyncRedis(server=server))
    server.connected = False
    with pytest.raises(SessionStoreError, match="listing sessions failed"):
        await store.list_sessions(limit=10)
    server.connected = True
    await store.list_sessions(limit=10)
    assert await _members(client, KEY) == {"a"}
