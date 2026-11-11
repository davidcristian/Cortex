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


@pytest.mark.parametrize("field", ["tainted", "opaque", "sources", "untrusted_urls"])
async def test_record_missing_a_taint_field_is_corrupt_not_a_default(field: str) -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    del fields[field]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    with pytest.raises(HandoffStoreError, match="corrupt handoff record at 'cortex:handoff:t1'"):
        await RedisHandoffStore(client).get("t1")


async def test_a_record_written_before_recalled_only_reads_it_as_false() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    record = handoff_contract.make_record("t1", recalled=True)
    fields = cast("dict[str, Any]", json.loads(encode_record(record)))
    del fields["recalled_only"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert loaded.recalled_only is False
    assert loaded.taint_ledger().tainted is True


async def test_a_record_written_before_recalled_ids_reads_them_as_none() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    record = handoff_contract.make_record("t1", recalled=True)
    fields = cast("dict[str, Any]", json.loads(encode_record(record)))
    del fields["recalled_ids"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert loaded.recalled_ids == ()
    assert loaded.recalled_only is True


async def test_a_record_written_before_the_forget_mark_reads_it_as_asked() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    del fields["forget_asked"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert loaded.forget_asked is True


async def test_a_record_written_before_the_refused_mark_reads_as_no_refusal() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    record = handoff_contract.make_record("t1")
    fields = cast("dict[str, Any]", json.loads(encode_record(record)))
    del fields["forget_refused"]
    del fields["forget_declined"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert not loaded.forget_refused
    assert not loaded.forget_declined


async def test_a_record_written_before_the_forget_counts_reads_them_as_zero() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    record = handoff_contract.make_record("t1", forgets=(2, 1))
    fields = cast("dict[str, Any]", json.loads(encode_record(record)))
    del fields["forget_calls"], fields["forget_unmatched"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded == replace(record, forget_calls=0, forget_unmatched=0)


async def test_record_with_an_unknown_source_kind_is_corrupt() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    fields["sources"] = [{"kind": "root-of-trust", "value": "evil"}]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    with pytest.raises(HandoffStoreError, match="corrupt handoff record at 'cortex:handoff:t1'"):
        await RedisHandoffStore(client).get("t1")


async def test_record_with_a_system_message_in_its_loop_tail_is_corrupt() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    fields["loop_tail"][0]["role"] = "system"
    await client.set("cortex:handoff:t1", json.dumps(fields))
    with pytest.raises(
        HandoffStoreError, match="corrupt handoff record at 'cortex:handoff:t1'"
    ) as excinfo:
        await RedisHandoffStore(client).get("t1")
    assert "never holds a system message" in str(excinfo.value.__cause__)


async def test_terminal_records_expire_and_live_ones_do_not() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    store = RedisHandoffStore(client)
    record = handoff_contract.make_record("t1")
    await store.put(record)
    assert await client.ttl("cortex:handoff:t1") == -1
    assert await store.transition("t1", HandoffState.DONE) is True
    assert 0 < await client.ttl("cortex:handoff:t1") <= 3600


async def test_a_dangling_active_pointer_reads_as_no_active_handoff() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    await client.set(ACTIVE_KEY, "ghost")
    store = RedisHandoffStore(client)
    assert await store.active() is None
    assert await client.get(ACTIVE_KEY) is not None


async def test_a_terminal_record_behind_the_pointer_is_not_active() -> None:
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


async def test_a_record_written_before_the_file_and_monthly_marks_reads_as_neither() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    record = handoff_contract.make_record("t1")
    fields = cast("dict[str, Any]", json.loads(encode_record(record)))
    del fields["sidecar_refused"]
    del fields["monthly_stored"]
    del fields["stored_time"]
    del fields["daily_stored"]
    del fields["made_repeating"]
    del fields["once_after_weekly"]
    del fields["weekday_off"]
    del fields["early_first_fire"]
    del fields["weekly_stored"]
    del fields["cancelled"]
    del fields["forget_inside"]
    del fields["forget_longer"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert (loaded.sidecar_refused, loaded.monthly_stored, loaded.stored_time) == (False, False, "")
    assert loaded.daily_stored == ()
    assert loaded.made_repeating == ()
    assert not loaded.once_after_weekly
    assert loaded.weekday_off == ()
    assert loaded.early_first_fire == ()
    assert loaded.weekly_stored == ()
    assert loaded.cancelled == ()
    assert loaded.forget_inside == ()
    assert loaded.forget_longer == ()


async def test_a_record_keeps_the_ids_its_turn_stored_to_repeat_daily() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    record = replace(
        handoff_contract.make_record("t1"), daily_stored=("abc", "def"), made_repeating=("ghi",)
    )
    await store.put(record)
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.daily_stored == ("abc", "def")
    assert loaded.made_repeating == ("ghi",)


@pytest.mark.parametrize("once", [True, False])
async def test_a_record_keeps_whether_a_one_time_item_followed_a_weekly_refusal(
    *, once: bool
) -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    await store.put(replace(handoff_contract.make_record("t1"), once_after_weekly=once))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.once_after_weekly is once


@pytest.mark.parametrize("left", [True, False])
async def test_a_record_keeps_whether_its_last_forget_left_a_number(*, left: bool) -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    await store.put(replace(handoff_contract.make_record("t1"), forget_numbers_left=left))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.forget_numbers_left is left


async def test_a_record_written_before_the_number_mark_reads_as_none_left() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    del fields["forget_numbers_left"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert loaded.forget_numbers_left is False


@pytest.mark.parametrize("held", [(("abc", "2026-11-13"), ("", "2026-11-11")), ()])
async def test_a_record_keeps_each_item_a_day_off_the_named_weekday_and_its_date(
    held: tuple[tuple[str, str], ...],
) -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    record = replace(handoff_contract.make_record("t1"), weekday_off=held)
    await store.put(record)
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.weekday_off == held


async def test_a_record_keeps_the_rows_a_forget_kept_for_a_longer_value() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    held = ("card ending 7890",)
    await store.put(replace(handoff_contract.make_record("t1"), forget_inside=held))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.forget_inside == held


async def test_a_record_keeps_the_rows_a_forget_kept_for_the_message_value() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    held = ("phone account 015 123 456 7890",)
    await store.put(replace(handoff_contract.make_record("t1"), forget_longer=held))
    loaded = await store.get("t1")
    assert loaded is not None
    assert (loaded.forget_longer, loaded.forget_inside) == (held, ())


async def test_a_record_keeps_the_texts_of_the_items_a_cancel_deleted() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    held = ("water the plants", "abc")
    await store.put(replace(handoff_contract.make_record("t1"), cancelled=held))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.cancelled == held


async def test_a_record_keeps_each_rule_on_chosen_weekdays_and_its_days() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    held = (("abc", "Wednesday"),)
    await store.put(replace(handoff_contract.make_record("t1"), weekly_stored=held))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.weekly_stored == held


async def test_a_record_keeps_each_repeat_first_firing_before_the_named_day() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    held = (("abc", "2026-11-10T09:00", 0),)
    await store.put(replace(handoff_contract.make_record("t1"), early_first_fire=held))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.early_first_fire == held


async def test_a_record_holding_english_day_words_reads_them_as_day_counts() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    fields["early_first_fire"] = [
        ["a", "2026-11-10T09:00", "today"],
        ["b", "2026-11-11T09:00", "tomorrow"],
        ["c", "2026-11-13T09:00", "in 3 days"],
    ]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert [days for _, _, days in loaded.early_first_fire] == [0, 1, 3]


async def test_a_record_holding_an_unknown_day_word_is_corrupt() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    fields["early_first_fire"] = [["a", "2026-11-10T09:00", "soon"]]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    with pytest.raises(HandoffStoreError, match="corrupt handoff record at 'cortex:handoff:t1'"):
        await RedisHandoffStore(client).get("t1")


async def test_a_record_keeps_the_rows_its_forgets_kept() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    await store.put(replace(handoff_contract.make_record("t1"), forget_kept=("a row", "b row")))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.forget_kept == ("a row", "b row")


async def test_a_record_keeps_every_row_its_forgets_kept_on_a_card_or_not() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    await store.put(replace(handoff_contract.make_record("t1"), forget_spared=("a row", "b row")))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.forget_spared == ("a row", "b row")
    assert loaded.taint_ledger().forget_spared == ("a row", "b row")


async def test_a_record_keeps_how_many_rows_its_forgets_deleted() -> None:
    store = RedisHandoffStore(FakeAsyncRedis(server=FakeServer()))
    await store.put(replace(handoff_contract.make_record("t1"), forget_deleted=3))
    loaded = await store.get("t1")
    assert loaded is not None
    assert loaded.forget_deleted == 3


async def test_a_record_written_before_the_kept_rows_reads_as_none_kept() -> None:
    client = FakeAsyncRedis(server=FakeServer())
    fields = cast("dict[str, Any]", json.loads(encode_record(handoff_contract.make_record("t1"))))
    del fields["forget_kept"]
    del fields["forget_spared"]
    await client.set("cortex:handoff:t1", json.dumps(fields))
    loaded = await RedisHandoffStore(client).get("t1")
    assert loaded is not None
    assert loaded.forget_kept == ()
    assert loaded.forget_spared == ()
