"""One behavior suite over BOTH TaskStore implementations, plus adapter error paths (ADR-0010).

The in-memory fake and the Redis adapter (backed by fakeredis) must be observably interchangeable
behind the port. This is the ports-before-adapters gate for the subagent task store.
"""

import json
from collections.abc import Awaitable, Callable

import pytest
import task_contract
from fakeredis import FakeAsyncRedis, FakeServer
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis

from cortex_core import InMemoryTaskStore, SubagentResult, SubagentTask, TaskStore, TaskStoreError
from cortex_session import DEFAULT_REDIS_URL, RedisTaskStore


@pytest.fixture(params=["in-memory", "redis"])
def store(request: pytest.FixtureRequest) -> TaskStore:
    """A fresh store of each implementation; every shared check runs against both."""
    if request.param == "in-memory":
        return InMemoryTaskStore()
    return RedisTaskStore(FakeAsyncRedis(server=FakeServer()))


@pytest.mark.parametrize("check", task_contract.ALL_CHECKS)
async def test_task_store_contract(
    store: TaskStore, check: Callable[[TaskStore], Awaitable[None]]
) -> None:
    await check(store)


def _disconnected_store() -> RedisTaskStore:
    server = FakeServer()
    server.connected = False
    return RedisTaskStore(FakeAsyncRedis(server=server))


@pytest.mark.parametrize("operation", ["put_task", "get_task", "put_result", "get_result"])
async def test_backend_failure_wraps_into_task_store_error(operation: str) -> None:
    store = _disconnected_store()
    task = task_contract.make_task("t1")
    result = SubagentResult(task_id="t1", output="done")
    ops: dict[str, Callable[[], Awaitable[object]]] = {
        "put_task": lambda: store.put_task(task),
        "get_task": lambda: store.get_task("t1"),
        "put_result": lambda: store.put_result(result),
        "get_result": lambda: store.get_result("t1"),
    }
    with pytest.raises(TaskStoreError) as excinfo:
        await ops[operation]()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_close_failure_wraps_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeAsyncRedis(server=FakeServer())

    async def failing_aclose() -> None:
        msg = "boom"
        raise redis_exceptions.ConnectionError(msg)

    monkeypatch.setattr(client, "aclose", failing_aclose)
    with pytest.raises(TaskStoreError, match="closing") as excinfo:
        await RedisTaskStore(client).aclose()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_corrupt_task_record_wraps_into_task_store_error() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    await client.set("cortex:task:t1", "not json at all")
    with pytest.raises(TaskStoreError, match="corrupt task record at 'cortex:task:t1'"):
        await RedisTaskStore(client).get_task("t1")


async def test_a_task_record_missing_an_identity_is_corrupt_rather_than_unattributed() -> None:
    """A record missing an identity key reads as corrupt rather than as work with no attribution
    (ADR-0009 fired-work).

    The record below is what a build from before the fired item existed would have left, every
    other field intact. Each identity is a required key, because a codec that supplied ``""`` for
    a key it could not find would put a claim in the trail, that no schedule item is behind the
    work, on the strength of a field nobody ever wrote.
    """
    client = FakeAsyncRedis(server=FakeServer())
    older = {
        "id": "t1",
        "instruction": "go",
        "context": "",
        "at": task_contract.make_task("t1").at.isoformat(),
        "model": "",
        "tainted": False,
        "session_id": "chat-1",
        "turn_id": "t-1",
    }
    await client.set("cortex:task:t1", json.dumps(older))
    with pytest.raises(TaskStoreError, match="corrupt task record at 'cortex:task:t1'"):
        await RedisTaskStore(client).get_task("t1")


async def test_corrupt_result_record_wraps_into_task_store_error() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    await client.set("cortex:task:t1:result", json.dumps({"task_id": "t1"}))  # missing fields
    with pytest.raises(TaskStoreError, match="corrupt result record at 'cortex:task:t1:result'"):
        await RedisTaskStore(client).get_result("t1")


async def test_from_url_wires_a_client_for_the_given_or_default_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def fake_from_url(url: str) -> FakeAsyncRedis:
        seen.append(url)
        return FakeAsyncRedis(server=FakeServer())

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    store = RedisTaskStore.from_url("redis://example.invalid:6390/7")
    task = SubagentTask(id="t1", instruction="go", context="", at=task_contract.make_task("t1").at)
    await store.put_task(task)
    assert await store.get_task("t1") == task
    await store.aclose()
    RedisTaskStore.from_url()
    assert seen == ["redis://example.invalid:6390/7", DEFAULT_REDIS_URL]
