import logging

import contract
import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis import exceptions as redis_exceptions

from cortex_core import Role, SessionStoreError
from cortex_core.sessions import HistoryRecap
from cortex_session import RedisSessionStore, StoreRetry
from cortex_session.retry import RETRY_LOG_MSG, MonotonicTimer, with_retry
from cortex_session.store import append_once
from cortex_session.store_codec import encode_message

_SHIPPED_WAITS = [0.05, 0.1, 0.2, 0.4, 0.8, 1.0, 0.45]


class _RestartingRedis:
    """A timer on a fake clock that brings the fake server back after every ``back_after`` waits."""

    def __init__(self, server: FakeServer, *, back_after: int | None) -> None:
        self.waits: list[float] = []
        self.clock_ms = 0
        self._server = server
        self._back_after = back_after

    def now_ms(self) -> int:
        return self.clock_ms

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.clock_ms += round(seconds * 1000)
        if self._back_after is not None and len(self.waits) % self._back_after == 0:
            self._server.connected = True


def _down_store(
    *, back_after: int | None
) -> tuple[RedisSessionStore, _RestartingRedis, FakeServer]:
    server = FakeServer()
    server.connected = False
    timer = _RestartingRedis(server, back_after=back_after)
    return RedisSessionStore(FakeAsyncRedis(server=server), timer=timer), timer, server


async def test_an_append_waits_out_a_restart_and_stores_the_message_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store, timer, _ = _down_store(back_after=4)
    message = contract.make_message(Role.ASSISTANT, "Apple and banana.")
    with caplog.at_level(logging.WARNING, logger="cortex_session.retry"):
        await store.append("s", message)
    assert list(await store.history("s")) == [message]
    assert timer.waits == [0.05, 0.1, 0.2, 0.4]
    retries = [record for record in caplog.records if record.getMessage() == RETRY_LOG_MSG]
    assert [record.__dict__["wait_ms"] for record in retries] == [50, 100, 200, 400]
    assert {record.__dict__["error"] for record in retries} == {"ConnectionError"}


async def test_an_outage_past_the_budget_fails_with_the_connection_error() -> None:
    store, timer, _ = _down_store(back_after=None)
    with pytest.raises(SessionStoreError, match="append to session 's'") as excinfo:
        await store.append("s", contract.make_message(Role.USER, "hi"))
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)
    assert timer.waits == _SHIPPED_WAITS
    assert timer.clock_ms == 3000


async def test_a_stalled_connect_counts_against_the_budget_and_is_tried_again() -> None:
    timer = _RestartingRedis(FakeServer(), back_after=None)
    tries: list[int] = []

    async def stalls_twice() -> str:
        tries.append(timer.now_ms())
        if len(tries) <= 2:
            timer.clock_ms += 1000
            msg = "Timeout connecting to server"
            raise redis_exceptions.TimeoutError(msg)
        return "stored"

    assert await with_retry(stalls_twice, StoreRetry(), timer) == "stored"
    assert tries == [0, 1050, 2150]


async def test_a_try_that_ends_past_the_budget_is_the_last() -> None:
    timer = _RestartingRedis(FakeServer(), back_after=None)

    async def stalls() -> None:
        timer.clock_ms += 2000
        msg = "Timeout connecting to server"
        raise redis_exceptions.TimeoutError(msg)

    with pytest.raises(redis_exceptions.TimeoutError):
        await with_retry(stalls, StoreRetry(), timer)
    assert timer.waits == [0.05]
    assert timer.clock_ms == 4050


async def test_every_read_and_write_waits_out_a_restart() -> None:
    store, timer, server = _down_store(back_after=1)
    calls = [
        lambda: store.append("s", contract.make_message(Role.USER, "hi")),
        lambda: store.set_title("s", "a title"),
        lambda: store.set_recap("s", HistoryRecap(text="a recap", covers=1)),
        lambda: store.set_hoisted("s", hoisted=True),
        lambda: store.history("s"),
        lambda: store.recap("s"),
        lambda: store.list_sessions(limit=5),
        lambda: store.delete("s"),
    ]
    for call in calls:
        server.connected = False
        await call()
    assert timer.waits == [0.05] * len(calls)
    assert list(await store.history("s")) == []


@pytest.mark.parametrize(
    "lost",
    [redis_exceptions.ConnectionError, redis_exceptions.TimeoutError, redis_exceptions.WatchError],
    ids=["drop", "stall", "fence"],
)
async def test_an_append_whose_reply_was_lost_after_it_ran_is_stored_once(
    lost: type[redis_exceptions.RedisError],
) -> None:
    client = FakeAsyncRedis(server=FakeServer())
    message = contract.make_message(Role.ASSISTANT, "kept once")
    record = encode_message(message)
    tries: list[int] = []

    async def lossy_append() -> None:
        await append_once(client, "s", record, message.at.timestamp())
        tries.append(1)
        if len(tries) == 1:
            msg = "the reply to a write that ran was lost"
            raise lost(msg)

    await with_retry(lossy_append, StoreRetry(), _RestartingRedis(FakeServer(), back_after=None))
    assert len(tries) == 2
    assert list(await RedisSessionStore(client).history("s")) == [message]
    assert await client.zscore("cortex:sessions", "s") == message.at.timestamp()


@pytest.mark.parametrize(
    "error",
    [
        redis_exceptions.AuthenticationError,
        redis_exceptions.AuthorizationError,
        redis_exceptions.ExternalAuthProviderError,
        redis_exceptions.ResponseError,
    ],
)
async def test_a_refused_credential_or_a_server_error_is_not_retried(
    error: type[redis_exceptions.RedisError],
) -> None:
    timer = _RestartingRedis(FakeServer(), back_after=None)

    async def failing() -> None:
        msg = "not a restart"
        raise error(msg)

    with pytest.raises(error):
        await with_retry(failing, StoreRetry(), timer)
    assert timer.waits == []


async def test_the_monotonic_timer_moves_forward_across_a_wait() -> None:
    timer = MonotonicTimer()
    before = timer.now_ms()
    await timer.sleep(0.02)
    assert timer.now_ms() - before >= 15
