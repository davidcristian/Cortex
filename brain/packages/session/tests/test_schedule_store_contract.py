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
    CalendarRule,
    FireOutcome,
    InMemoryScheduleStore,
    MonthDays,
    ScheduleClaim,
    ScheduleEdit,
    ScheduleStatus,
    ScheduleStore,
    ScheduleStoreError,
    Weekdays,
)
from cortex_session import DEFAULT_REDIS_URL, DeadLetter, RedisScheduleStore, schedule_claims
from cortex_session.schedule_codec import (
    DEAD_KEY,
    DELIVERABLE_KEY,
    DUE_KEY,
    encode,
    record_key,
)

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
        "edit",
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
        "edit": lambda: store.edit("s1", ScheduleEdit(text="x")),
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


async def test_a_monthly_rule_still_decodes_as_monthly_beside_the_yearly_key() -> None:
    """The present-key contract holds for THREE variants, not just for the original two.

    A yearly rule writes ``year_dates``, and the decoder checks it first. This proves that
    check falls through rather than shadowing: a record carrying ``month_days`` and no
    ``year_dates`` must still read back monthly (ADR-0025 yearly addendum).
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    item = schedule_contract.make_item("monthly")
    record = json.loads(encode(item, claim=None, claimed_at=None))
    record["rule"] = {"hour": 9, "minute": 0, "month_days": [1, 15]}
    await _seed_raw(client, "monthly", json.dumps(record))
    loaded = await store.get("monthly")
    assert loaded is not None
    assert loaded.rule == CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({1, 15})))


async def test_a_malformed_year_date_pair_fails_loudly_like_any_corrupt_field() -> None:
    """A stored pair that is not a pair is corruption, not a shape to guess at."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    item = schedule_contract.make_item("bent")
    record = json.loads(encode(item, claim=None, claimed_at=None))
    record["rule"] = {"hour": 9, "minute": 0, "year_dates": [[12, 25, 2026]]}
    await _seed_raw(client, "bent", json.dumps(record))
    with pytest.raises(ScheduleStoreError, match="corrupt schedule record"):
        await store.get("bent")


async def test_a_stored_unknown_zone_fails_loudly_naming_the_key() -> None:
    """A per-rule zone the tz database no longer resolves is a corrupt record, not a fallback.

    Creation validated the name, so this is only reachable if the tz database changed under a
    durable record; substituting the deployment zone would fire the rule at a wall time nobody
    asked for, so the codec fails loudly instead (ADR-0025 per-rule addendum).
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    item = schedule_contract.make_item("gone-zone")
    record = json.loads(encode(item, claim=None, claimed_at=None))
    record["rule"] = {"hour": 9, "minute": 0, "days": [0], "zone": "Mars/Olympus"}
    await _seed_raw(client, "gone-zone", json.dumps(record))
    with pytest.raises(ScheduleStoreError, match="unknown timezone 'Mars/Olympus'"):
        await store.get("gone-zone")


async def test_a_stored_non_string_zone_fails_loudly() -> None:
    """A stored zone that is not even a string is corruption, not a shape to guess at."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    item = schedule_contract.make_item("bent-zone")
    record = json.loads(encode(item, claim=None, claimed_at=None))
    record["rule"] = {"hour": 9, "minute": 0, "days": [0], "zone": 5}
    await _seed_raw(client, "bent-zone", json.dumps(record))
    with pytest.raises(ScheduleStoreError, match="unknown timezone"):
        await store.get("bent-zone")


async def test_a_rule_written_before_per_rule_zones_decodes_as_zone_less() -> None:
    """The additive-key contract: a rule record with no ``zone`` key reads back zone-less, so it
    keeps taking the deployment zone exactly as it did before per-rule zones (per-rule addendum)."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    item = schedule_contract.make_item("no-zone")
    record = json.loads(encode(item, claim=None, claimed_at=None))
    record["rule"] = {"hour": 9, "minute": 0, "days": [0, 4]}  # a pre-addendum rule: no zone key
    await _seed_raw(client, "no-zone", json.dumps(record))
    loaded = await store.get("no-zone")
    assert loaded is not None
    assert loaded.rule is not None
    assert loaded.rule == CalendarRule(hour=9, minute=0, on=Weekdays(days=frozenset({0, 4})))
    assert loaded.rule.zone is None


async def test_a_rule_written_before_month_days_decodes_as_a_weekly_one() -> None:
    """The additive-key contract: an old record carries ``days`` and no discriminator.

    Written by hand rather than by the encoder, because the point is a record this build can
    no longer produce: the shape every calendar rule had before day-of-month selectors landed
    (ADR-0025 monthly addendum). It must still read back as the weekly rule it was.
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    item = schedule_contract.make_item("legacy")
    record = json.loads(encode(item, claim=None, claimed_at=None))
    record["rule"] = {"hour": 9, "minute": 0, "days": [0, 4]}
    await _seed_raw(client, "legacy", json.dumps(record))
    loaded = await store.get("legacy")
    assert loaded is not None
    assert loaded.rule == CalendarRule(hour=9, minute=0, on=Weekdays(days=frozenset({0, 4})))


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


async def test_edit_racing_a_cancel_is_fenced_not_resurrected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancel landing between edit's guard read and its write wins; nothing resurrects."""
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    store = RedisScheduleStore(client)
    await store.add(schedule_contract.make_item("raced"))

    def delete_it(poker: FakeStrictRedis) -> None:
        poker.delete(record_key("raced"))
        poker.zrem(DUE_KEY, "raced")

    _poke_on_decode(monkeypatch, server, delete_it)
    assert await store.edit("raced", ScheduleEdit(text="new")) is False
    assert await client.get(record_key("raced")) is None  # the cancel stuck; not re-written
    assert await client.zscore(DUE_KEY, "raced") is None


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


async def test_dead_letters_lists_in_id_order_and_purges_one_scope() -> None:
    """The operator inspection pair over the quarantine hash (dead-letter addendum).

    Two entries at once pin the documented id order AND that a purge drops only its own
    field: a `delete(DEAD_KEY)` purge or a listing that returned one entry would pass a
    single-entry test but fail here.
    """
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await _seed_raw(client, "zeta", "junk-z")
    await _seed_raw(client, "alpha", "junk-a")
    survivor = schedule_contract.make_item("survivor", due_at=_NOW - timedelta(minutes=1))
    await store.add(survivor)
    claims = await store.claim_due(_NOW, lease=_LEASE, limit=8)
    assert [claim.item.id for claim in claims] == ["survivor"]  # the pass degraded by two
    assert await store.dead_letters() == (
        DeadLetter(item_id="alpha", raw="junk-a"),
        DeadLetter(item_id="zeta", raw="junk-z"),
    )
    assert await store.purge_dead_letter("alpha") is True
    assert await store.dead_letters() == (
        DeadLetter(item_id="zeta", raw="junk-z"),
    )  # zeta survived
    assert await store.purge_dead_letter("alpha") is False
    assert await store.purge_dead_letter("zeta") is True
    assert await store.dead_letters() == ()


async def test_dead_letters_render_hostile_bytes_with_replacement() -> None:
    """Corrupt bytes stay inspectable: decoding never becomes a second crash."""
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisScheduleStore(client)
    await client.hset(DEAD_KEY, "bad", b"\xff\xfe not utf-8")  # pyright: ignore[reportUnknownMemberType]
    (letter,) = await store.dead_letters()
    assert letter.item_id == "bad"
    assert "not utf-8" in letter.raw
    assert "�" in letter.raw  # the undecodable bytes became replacement characters


async def test_dead_letter_operations_wrap_backend_failure() -> None:
    store = _disconnected_store()
    with pytest.raises(ScheduleStoreError, match="listing dead-lettered"):
        await store.dead_letters()
    with pytest.raises(ScheduleStoreError, match="purging dead-lettered"):
        await store.purge_dead_letter("x")


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


async def test_claim_honors_a_snooze_that_committed_before_the_watch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The before-WATCH race: a snooze commits between claim_due's due snapshot and the
    per-item WATCH, moving the record forward. WATCH cannot see it, so the claim must
    re-check the read record and skip, not fire the reminder at the stale time (snooze
    addendum). Without the re-check the item is claimed FIRING and its future due-entry lost.
    """
    server = FakeServer()
    client = FakeAsyncRedis(server=server)
    store = RedisScheduleStore(client)
    await store.add(schedule_contract.make_item("raced", due_at=_NOW - timedelta(minutes=1)))
    until = _NOW + timedelta(minutes=10)
    original_ids = schedule_claims.ids
    snoozed: list[bool] = []

    async def snoozing_ids(client_: Redis, key: str, **kwargs: object) -> list[str]:
        result = await original_ids(client_, key, **kwargs)  # pyright: ignore[reportArgumentType]
        if key == DUE_KEY and not snoozed:
            # The due snapshot has just captured "raced"; commit the snooze before the WATCH.
            snoozed.append(True)
            await store.snooze("raced", until=until)
        return result

    monkeypatch.setattr(schedule_claims, "ids", snoozing_ids)
    assert await store.claim_due(_NOW, lease=_LEASE, limit=8) == ()  # the snoozed item is skipped
    loaded = await store.get("raced")
    assert loaded is not None
    assert loaded.status is ScheduleStatus.PENDING  # still armed, not fired
    assert loaded.due_at == until  # the snooze survives
    assert await client.zscore(DUE_KEY, "raced") == until.timestamp()  # its future due-entry intact
