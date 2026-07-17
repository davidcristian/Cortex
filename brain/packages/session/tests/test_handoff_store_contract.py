"""One behavior suite over BOTH HandoffStore implementations, plus adapter error paths.

The in-memory fake and the Redis adapter (backed by fakeredis) must be observably
interchangeable behind the port. This is the ports-before-adapters gate for the brain-handoff
store (ADR-0030); the tainted-ledger round trip in the shared checks is the pinned proof that
taint persistence survives the swap.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any, cast

import handoff_contract
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis

from cortex_core import HandoffState, HandoffStore, HandoffStoreError, InMemoryHandoffStore
from cortex_session import DEFAULT_REDIS_URL, RedisHandoffStore
from cortex_session.handoff_codec import ACTIVE_KEY, encode_record


@pytest.fixture(params=["in-memory", "redis"])
def store(request: pytest.FixtureRequest) -> HandoffStore:
    """A fresh store of each implementation; every shared check runs against both."""
    if request.param == "in-memory":
        return InMemoryHandoffStore()
    return RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))


@pytest.mark.parametrize("check", handoff_contract.ALL_CHECKS)
async def test_handoff_store_contract(
    store: HandoffStore, check: Callable[[HandoffStore], Awaitable[None]]
) -> None:
    await check(store)


def _disconnected_store() -> RedisHandoffStore:
    server = FakeServer()
    server.connected = False
    return RedisHandoffStore(FakeAsyncRedis(server=server))


@pytest.mark.parametrize("operation", ["put", "get", "transition", "delete", "active"])
async def test_backend_failure_wraps_into_handoff_store_error(operation: str) -> None:
    store = _disconnected_store()
    record = handoff_contract.make_record("t1")
    ops: dict[str, Callable[[], Awaitable[object]]] = {
        "put": lambda: store.put(record),
        "get": lambda: store.get("t1"),
        "transition": lambda: store.transition("t1", HandoffState.FAILED),
        "delete": lambda: store.delete("t1"),
        "active": store.active,
    }
    with pytest.raises(HandoffStoreError) as excinfo:
        await ops[operation]()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_terminal_put_failure_wraps_too() -> None:
    """The terminal write path (pointer read + TTL'd set) wraps its backend failure alike."""
    store = _disconnected_store()
    record = handoff_contract.make_record("t1", state=HandoffState.DONE)
    with pytest.raises(HandoffStoreError, match="put for handoff 't1' failed") as excinfo:
        await store.put(record)
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_close_failure_wraps_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeAsyncRedis(server=FakeServer())

    async def failing_aclose() -> None:
        msg = "boom"
        raise redis_exceptions.ConnectionError(msg)

    monkeypatch.setattr(client, "aclose", failing_aclose)
    with pytest.raises(HandoffStoreError, match="closing") as excinfo:
        await RedisHandoffStore(client).aclose()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_corrupt_record_wraps_into_handoff_store_error() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    await client.set("cortex:handoff:t1", "not json at all")
    with pytest.raises(HandoffStoreError, match="corrupt handoff record at 'cortex:handoff:t1'"):
        await RedisHandoffStore(client).get("t1")


async def test_record_missing_a_taint_field_is_corrupt_not_a_default() -> None:
    """A document without its taint fields fails LOUDLY; defaulting them would fail open."""
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    del fields["sources"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    with pytest.raises(HandoffStoreError, match="corrupt handoff record at 'cortex:handoff:t1'"):
        await RedisHandoffStore(client).get("t1")


async def test_record_with_an_unknown_source_kind_is_corrupt() -> None:
    """A forged/unknown provenance kind never decodes into an attested-looking source."""
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    fields["sources"] = [{"kind": "root-of-trust", "value": "evil"}]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    with pytest.raises(HandoffStoreError, match="corrupt handoff record at 'cortex:handoff:t1'"):
        await RedisHandoffStore(client).get("t1")


async def test_terminal_records_expire_and_live_ones_do_not() -> None:
    """A non-terminal record has no TTL (boot recovery must find it); a terminal one does."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisHandoffStore(client)
    record = handoff_contract.make_record("t1")
    await store.put(record)
    assert await client.ttl("cortex:handoff:t1") == -1
    assert await store.transition("t1", HandoffState.DONE) is True
    assert 0 < await client.ttl("cortex:handoff:t1") <= 3600


async def test_a_dangling_active_pointer_reads_as_no_active_handoff() -> None:
    """A pointer naming a gone record self-heals to None on read (nothing is mutated)."""
    client = FakeAsyncRedis(server=FakeServer())
    await client.set(ACTIVE_KEY, "ghost")
    store = RedisHandoffStore(client)
    assert await store.active() is None
    assert await client.get(ACTIVE_KEY) is not None  # read-only: the pointer is left alone


async def test_a_terminal_record_behind_the_pointer_is_not_active() -> None:
    """A hand-crafted finished-but-still-pointed record never resurrects as in flight."""
    client = FakeAsyncRedis(server=FakeServer())
    done = replace(handoff_contract.make_record("t1"), state=HandoffState.DONE)
    await client.set("cortex:handoff:t1", encode_record(done))
    await client.set(ACTIVE_KEY, "t1")
    assert await RedisHandoffStore(client).active() is None


async def test_from_url_wires_a_client_for_the_given_or_default_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def fake_from_url(url: str) -> FakeAsyncRedis:
        seen.append(url)
        return FakeAsyncRedis(server=FakeServer())

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    store = RedisHandoffStore.from_url("redis://example.invalid:6390/7")
    record = handoff_contract.make_record("t1")
    await store.put(record)
    assert await store.get("t1") == record
    await store.aclose()
    RedisHandoffStore.from_url()
    assert seen == ["redis://example.invalid:6390/7", DEFAULT_REDIS_URL]
