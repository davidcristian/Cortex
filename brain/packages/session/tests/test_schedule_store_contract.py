"""One behavior suite over BOTH ScheduleStore implementations, plus adapter mechanics
(ADR-0025).

The in-memory fake and the Redis adapter (backed by fakeredis) must be observably
interchangeable behind the port. The adapter-only mechanics of error wrapping, the durable-record
codec policy, and the claim-path quarantine are tested here against the Redis adapter alone.
"""

import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
import schedule_contract
from fakeredis import FakeAsyncRedis, FakeServer, FakeStrictRedis
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis

from cortex_core import (
    FireOutcome,
    InMemoryScheduleStore,
    ScheduleClaim,
    ScheduleStore,
    ScheduleStoreError,
)
from cortex_session import DEFAULT_REDIS_URL, RedisScheduleStore, schedule_claims
from cortex_session.schedule_codec import DEAD_KEY, DELIVERABLE_KEY, DUE_KEY, record_key

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_LEASE = timedelta(minutes=5)


@pytest.fixture(params=["in-memory", "redis"])
def store(request: pytest.FixtureRequest) -> ScheduleStore:
    """A fresh store of each implementation; every shared check runs against both."""
    if request.param == "in-memory":
        return InMemoryScheduleStore()
    return RedisScheduleStore(FakeAsyncRedis(server=FakeServer()))


@pytest.mark.parametrize("check", schedule_contract.ALL_CHECKS)
async def test_schedule_store_contract(
    store: ScheduleStore, check: Callable[[ScheduleStore], Awaitable[None]]
) -> None:
    await check(store)


def _disconnected_store() -> RedisScheduleStore:
    server = FakeServer()
    server.connected = False
    return RedisScheduleStore(FakeAsyncRedis(server=server))


def _dummy_claim() -> ScheduleClaim:
    item = schedule_contract.make_item("claimed")
    return ScheduleClaim(item=item, token="token")  # noqa: S106 - test fencing token, not a secret


@pytest.mark.parametrize(
    "operation",
    [
        "add",
        "get",
        "list_active",
        "cancel",
        "snooze",
        "claim_due",
        "finish",
        "release",
        "deliverable",
        "ack",
    ],
)
async def test_backend_failure_wraps_into_schedule_store_error(operation: str) -> None:
    store = _disconnected_store()
    outcome = FireOutcome(fired_at=_NOW, next_due=None, deliverable=False)
    ops: dict[str, Callable[[], Awaitable[object]]] = {
        "add": lambda: store.add(schedule_contract.make_item("s1")),
        "get": lambda: store.get("s1"),
        "list_active": store.list_active,
        "cancel": lambda: store.cancel("s1"),
        "snooze": lambda: store.snooze("s1", until=_NOW),
        "claim_due": lambda: store.claim_due(_NOW, lease=_LEASE, limit=8),
        "finish": lambda: store.finish(_dummy_claim(), outcome),
        "release": lambda: store.release(_dummy_claim()),
        "deliverable": store.deliverable,
        "ack": lambda: store.ack("s1"),
    }
    with pytest.raises(ScheduleStoreError) as excinfo:
        await ops[operation]()
    assert isinstance(excinfo.value.__cause__, redis_exceptions.ConnectionError)


async def test_close_failure_wraps_the_cause(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeAsyncRedis(server=FakeServer())

    async def failing_aclose() -> None:
        msg = "boom"
        raise redis_exceptions.ConnectionError(msg)

    monkeypatch.setattr(client, "aclose", failing_aclose)
    with pytest.raises(ScheduleStoreError, match="closing the Redis client failed"):
        await RedisScheduleStore(client).aclose()


async def test_aclose_releases_the_client() -> None:
    store = RedisScheduleStore(FakeAsyncRedis(server=FakeServer()))
    await store.aclose()


async def test_from_url_builds_a_store(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def fake_from_url(url: str) -> Redis:
        captured.append(url)
        return FakeAsyncRedis(server=FakeServer())

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    store = RedisScheduleStore.from_url()
    item = schedule_contract.make_item("from-url")
    await store.add(item)
    assert await store.get("from-url") == item
    assert captured == [DEFAULT_REDIS_URL]


async def _seed_raw(
    client: FakeAsyncRedis, item_id: str, raw: str, *, due_at: datetime | None = None
) -> None:
    """Plant a raw record + due-index entry, as a corrupted writer would have left them."""
    await client.set(record_key(item_id), raw)
    await client.zadd(DUE_KEY, {item_id: (due_at if due_at is not None else _NOW).timestamp()})


async def test_corrupt_record_fails_loudly_on_get() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await _seed_raw(client, "bad", "not json")
    with pytest.raises(ScheduleStoreError, match="corrupt schedule record"):
        await store.get("bad")


async def test_unknown_kind_or_version_fails_loudly_naming_the_reader() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await _seed_raw(client, "vnext", json.dumps({"v": 2, "kind": "schedule"}))
    with pytest.raises(ScheduleStoreError, match="unreadable schedule record"):
        await store.get("vnext")


async def test_corrupt_record_fails_loudly_on_list_active() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await _seed_raw(client, "bad", '["not", "an", "object"]')
    with pytest.raises(ScheduleStoreError, match="corrupt schedule record"):
        await store.list_active()


async def test_claim_path_quarantines_a_corrupt_record() -> None:
    """The poison-pill defense: one bad record dead-letters; the pass still claims the rest.

    The poison is due EARLIER than the healthy item, so it is the FIRST claim candidate, and
    a regression back to halt-the-pass would leave `good` unclaimed and fail here.
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    good = schedule_contract.make_item("good", due_at=_NOW - timedelta(minutes=1))
    await store.add(good)
    await _seed_raw(client, "poison", "not json", due_at=_NOW - timedelta(minutes=2))
    claims = await store.claim_due(_NOW, lease=_LEASE, limit=8)
    assert [claim.item.id for claim in claims] == ["good"]
    assert await client.hget(DEAD_KEY, "poison") == b"not json"
    assert await client.get(record_key("poison")) is None
    assert await client.zscore(DUE_KEY, "poison") is None
    # The next pass no longer sees the quarantined id at all.
    assert await store.claim_due(_NOW + _LEASE + _LEASE, lease=_LEASE, limit=8) != ()


async def test_claim_drops_a_dangling_index_entry() -> None:
    """An index member without a record (a crash relic) is dropped, not an error."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await client.zadd(DUE_KEY, {"ghost": _NOW.timestamp()})
    assert await store.claim_due(_NOW, lease=_LEASE, limit=8) == ()
    assert await client.zscore(DUE_KEY, "ghost") is None


async def test_list_active_skips_a_dangling_index_entry() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await client.zadd(DUE_KEY, {"ghost": _NOW.timestamp()})
    assert await store.list_active() == ()


async def test_deliverable_skips_a_dangling_index_entry() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await client.zadd(DELIVERABLE_KEY, {"ghost": _NOW.timestamp()})
    assert await store.deliverable() == ()


async def test_claim_due_releases_the_surplus_past_limit() -> None:
    """Claims merged from both indexes past the limit are released back to PENDING."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    older = schedule_contract.make_item("older", due_at=_NOW - timedelta(minutes=10))
    newer = schedule_contract.make_item("newer", due_at=_NOW - timedelta(minutes=2))
    await store.add(older)
    # Claim `older` one lease ago so it is FIRING and exactly lease-expired at _NOW.
    (first_claim,) = await store.claim_due(_NOW - _LEASE, lease=_LEASE, limit=1)
    await store.add(newer)
    # One slot, two candidates (one per index): the oldest-due wins across both classes.
    (winner,) = await store.claim_due(_NOW, lease=_LEASE, limit=1)
    assert winner.item.id == "older"
    assert winner.token != first_claim.token  # re-claimed under a fresh fencing token
    # The surplus (`newer`) was claimed then released: immediately claimable again.
    (surplus,) = await store.claim_due(_NOW, lease=_LEASE, limit=1)
    assert surplus.item.id == "newer"


# --- the WATCH fence: a racing transition between guard read and write loses cleanly ---


def _poke_on_decode(
    monkeypatch: pytest.MonkeyPatch, server: FakeServer, poke: Callable[[FakeStrictRedis], None]
) -> None:
    """Patch the transition-side decode to run `poke` (a concurrent write) mid-transition.

    `decode` runs between the WATCH'd guard read and the MULTI/EXEC write in every fenced
    transition, so a poke here lands exactly in the race window the WATCH must close.
    """
    poker = FakeStrictRedis(server=server)
    original = schedule_claims.decode  # pyright: ignore[reportPrivateImportUsage] - patched in place
    fired: list[bool] = []

    def poking_decode(raw: bytes | str, item_id: str) -> object:
        state = original(raw, item_id)
        if not fired:
            fired.append(True)
            poke(poker)
        return state

    monkeypatch.setattr(schedule_claims, "decode", poking_decode)


async def test_finish_racing_a_cancel_is_fenced_not_resurrected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancel landing between finish's guard read and its write wins, so nothing re-arms."""
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    store = RedisScheduleStore(client)
    await store.add(schedule_contract.make_item("raced", every=timedelta(hours=1)))
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=8)

    def cancel_it(poker: FakeStrictRedis) -> None:
        poker.delete(record_key("raced"))
        poker.zrem("cortex:schedules:firing", "raced")

    _poke_on_decode(monkeypatch, server, cancel_it)
    outcome = FireOutcome(fired_at=_NOW, next_due=_NOW + timedelta(hours=1), deliverable=True)
    assert await store.finish(claim, outcome) is False
    assert await client.get(record_key("raced")) is None  # the cancel stuck
    assert await client.zscore(DUE_KEY, "raced") is None
    assert await client.zscore(DELIVERABLE_KEY, "raced") is None


async def test_release_racing_a_cancel_is_fenced(monkeypatch: pytest.MonkeyPatch) -> None:
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    store = RedisScheduleStore(client)
    await store.add(schedule_contract.make_item("raced"))
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=8)

    def delete_it(poker: FakeStrictRedis) -> None:
        poker.delete(record_key("raced"))

    _poke_on_decode(monkeypatch, server, delete_it)
    assert await store.release(claim) is False
    assert await client.get(record_key("raced")) is None
    assert await client.zscore(DUE_KEY, "raced") is None


async def test_ack_racing_a_concurrent_transition_is_fenced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ack whose record was touched mid-transition must not write back its stale read."""
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    store = RedisScheduleStore(client)
    await store.add(schedule_contract.make_item("raced"))
    (claim,) = await store.claim_due(_NOW, lease=_LEASE, limit=8)
    fired = FireOutcome(fired_at=_NOW, next_due=None, deliverable=True)
    assert await store.finish(claim, fired) is True

    def touch_it(poker: FakeStrictRedis) -> None:
        raw = poker.get(record_key("raced"))
        assert raw is not None
        poker.set(record_key("raced"), raw)  # any touch: e.g. a re-claim racing the ack

    _poke_on_decode(monkeypatch, server, touch_it)
    assert await store.ack("raced") is False
    (still_due,) = await store.deliverable()  # nothing was clobbered; the ack can retry
    assert still_due.id == "raced"


async def test_claim_racing_a_cancel_is_fenced(monkeypatch: pytest.MonkeyPatch) -> None:
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    store = RedisScheduleStore(client)
    await store.add(schedule_contract.make_item("raced", due_at=_NOW - timedelta(minutes=1)))

    def delete_it(poker: FakeStrictRedis) -> None:
        poker.delete(record_key("raced"))

    _poke_on_decode(monkeypatch, server, delete_it)
    assert await store.claim_due(_NOW, lease=_LEASE, limit=8) == ()
    assert await client.get(record_key("raced")) is None  # the cancel stuck; nothing FIRING


async def test_snooze_racing_a_cancel_is_fenced_not_resurrected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancel landing between snooze's guard read and its write wins; nothing resurrects."""
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    store = RedisScheduleStore(client)
    await store.add(schedule_contract.make_item("raced"))

    def delete_it(poker: FakeStrictRedis) -> None:
        poker.delete(record_key("raced"))
        poker.zrem(DUE_KEY, "raced")

    _poke_on_decode(monkeypatch, server, delete_it)
    assert await store.snooze("raced", until=_NOW + timedelta(minutes=30)) is False
    assert await client.get(record_key("raced")) is None  # the cancel stuck
    assert await client.zscore(DUE_KEY, "raced") is None  # not re-indexed by the loser
