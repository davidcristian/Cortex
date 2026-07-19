"""One behavior suite over BOTH PreferenceStore implementations, plus the adapter's error paths.

The in-memory fake and the Redis adapter (backed by fakeredis) must be observably interchangeable
behind the port. This is the ports-before-adapters gate for the user's settings record.
"""

from collections.abc import Awaitable, Callable

import preference_contract
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis import exceptions as redis_exceptions

from cortex_core import InMemoryPreferenceStore, PreferenceStore, PreferenceStoreError
from cortex_session import DEFAULT_REDIS_URL, RedisPreferenceStore


@pytest.fixture(params=["in-memory", "redis"])
def store(request: pytest.FixtureRequest) -> PreferenceStore:
    """A fresh store of each implementation; every shared check runs against both."""
    if request.param == "in-memory":
        return InMemoryPreferenceStore()
    return RedisPreferenceStore(FakeAsyncRedis(server=FakeServer()))


@pytest.mark.parametrize("check", preference_contract.ALL_CHECKS)
async def test_preference_store_contract(
    store: PreferenceStore, check: Callable[[PreferenceStore], Awaitable[None]]
) -> None:
    await check(store)


def _disconnected_store() -> RedisPreferenceStore:
    server = FakeServer()
    server.connected = False
    return RedisPreferenceStore(FakeAsyncRedis(server=server))


@pytest.mark.parametrize("operation", ["all", "set", "clear"])
async def test_backend_failure_wraps_into_preference_store_error(operation: str) -> None:
    store = _disconnected_store()
    ops: dict[str, Callable[[], Awaitable[object]]] = {
        "all": store.all,
        "set": lambda: store.set("overlay.theme", "midnight"),
        # The clear path is a different Redis command (HDEL), so it needs its own proof.
        "clear": lambda: store.set("overlay.theme", ""),
    }
    with pytest.raises(PreferenceStoreError) as excinfo:
        await ops[operation]()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_close_failure_wraps_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeAsyncRedis(server=FakeServer())

    async def failing_aclose() -> None:
        message = "boom"
        raise redis_exceptions.ConnectionError(message)

    monkeypatch.setattr(client, "aclose", failing_aclose)
    store = RedisPreferenceStore(client)
    with pytest.raises(PreferenceStoreError) as excinfo:
        await store.aclose()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_close_releases_the_client() -> None:
    store = RedisPreferenceStore(FakeAsyncRedis(server=FakeServer()))
    await store.aclose()


def test_from_url_builds_its_own_client() -> None:
    store = RedisPreferenceStore.from_url(DEFAULT_REDIS_URL)
    assert isinstance(store, RedisPreferenceStore)


async def test_decodes_fields_a_configured_client_returns_as_text() -> None:
    """A client built with decode_responses answers str, not bytes; both must read the same."""
    client = FakeAsyncRedis(server=FakeServer(), decode_responses=True)
    store = RedisPreferenceStore(client)
    await store.set("overlay.mark", "wobble")
    assert dict(await store.all()) == {"overlay.mark": "wobble"}


async def test_the_fake_can_be_armed_to_fail() -> None:
    """The fake's error arm raises the same typed error, so callers can prove their handling."""
    store = InMemoryPreferenceStore(initial={"overlay.mark": "foam"})
    store.fail_with = "store is down"
    with pytest.raises(PreferenceStoreError):
        await store.all()
    with pytest.raises(PreferenceStoreError):
        await store.set("overlay.mark", "ping")
