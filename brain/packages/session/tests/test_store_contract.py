"""One behavior suite over BOTH SessionStore implementations, plus adapter error paths.

The in-memory fake and the Redis adapter (backed by fakeredis) must be observably
interchangeable behind the port. That is this slice's ports-before-adapters gate.
"""

import json

import contract
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis

from cortex_core import InMemorySessionStore, Role, SessionStore, SessionStoreError
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
