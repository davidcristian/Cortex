import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from serving_contract import ALL_CHECKS, Check

from cortex_core import ServingProbe
from cortex_session import STORE_DOWN, RedisPing, RedisSessionStore


def _ping(*, answering: bool) -> ServingProbe:
    server = FakeServer()
    server.connected = answering
    return RedisPing(FakeAsyncRedis(server=server))


@pytest.mark.parametrize("check", ALL_CHECKS)
async def test_redis_ping_passes_the_serving_probe_contract(check: Check) -> None:
    await check(_ping)


async def test_the_store_probe_asks_the_redis_the_store_calls() -> None:
    server = FakeServer()
    store = RedisSessionStore(FakeAsyncRedis(server=server))
    probe = store.probe()
    assert await probe.fault() is None
    server.connected = False
    assert await probe.fault() == STORE_DOWN
    server.connected = True
    assert await probe.fault() is None
