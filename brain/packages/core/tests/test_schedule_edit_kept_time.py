from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from cortex_core import (
    DisplayZone,
    EditScheduledTool,
    InMemoryScheduleStore,
    ScheduledItem,
    ScheduleStoreError,
    ScheduleTaskTool,
    ToolCall,
    TurnStamp,
    ZoneContext,
)

_NOW = datetime(2026, 11, 5, 5, 0, tzinfo=UTC)
_BERLIN = DisplayZone(name="Europe/Berlin", tz=ZoneInfo("Europe/Berlin"))
_LISBON = DisplayZone(name="Europe/Lisbon", tz=ZoneInfo("Europe/Lisbon"))
_ZONES = {zone.name: zone for zone in (_BERLIN, _LISBON)}


class _FixedClock:
    def now(self) -> datetime:
        return _NOW


class _Resolver:
    def resolve(self, name: str) -> DisplayZone | None:
        return _ZONES.get(name)


class _DownStore(InMemoryScheduleStore):
    async def get(self, item_id: str) -> ScheduledItem | None:
        msg = f"redis is down while reading {item_id}"
        raise ScheduleStoreError(msg)


def _call(name: str, arguments: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments, stamp=TurnStamp(session_id="s1"))


async def _stored(store: InMemoryScheduleStore, **timing: object) -> None:
    tool = ScheduleTaskTool(
        store,
        _FixedClock(),
        tasks_enabled=False,
        max_active=32,
        item_id_factory=lambda: "item-1",
        zones=ZoneContext(resolver=_Resolver()),
    )
    arguments: dict[str, object] = {"kind": "reminder", "text": "pay the gas bill", **timing}
    result = await tool.invoke(_call("schedule_task", arguments))
    assert not result.is_error, result.content


async def _edit(
    store: InMemoryScheduleStore, item_id: str = "item-1", **changes: object
) -> tuple[str, bool]:
    tool = EditScheduledTool(store, _FixedClock(), zones=ZoneContext(resolver=_Resolver()))
    result = await tool.invoke(_call("edit_scheduled", {"id": item_id, **changes}))
    return result.content, result.is_error


async def test_a_moved_day_without_at_time_keeps_the_stored_wall_clock_time() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at_time="09:30", on_month_days=[15])
    content, is_error = await _edit(store, on_month_days=[20])
    assert not is_error, content
    (item,) = await store.list_active()
    assert item.rule is not None
    assert (item.rule.wall_time, item.due_at) == (
        "09:30",
        datetime(2026, 11, 20, 9, 30, tzinfo=UTC),
    )
    assert content == "edited item-1: now due 2026-11-20T09:30:00+00:00"


async def test_a_moved_day_keeps_the_stored_zone_too() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at_time="09:00", on_days=["mon"], in_zone="Europe/Berlin")
    content, is_error = await _edit(store, on_days=["fri"])
    assert not is_error, content
    (item,) = await store.list_active()
    assert item.rule is not None
    assert item.rule.zone == _BERLIN
    assert item.due_at == datetime(2026, 11, 6, 8, 0, tzinfo=UTC)


async def test_a_moved_day_with_its_own_zone_keeps_that_zone() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at_time="09:00", on_days=["mon"], in_zone="Europe/Berlin")
    content, is_error = await _edit(store, on_days=["fri"], in_zone="Europe/Lisbon")
    assert not is_error, content
    (item,) = await store.list_active()
    assert item.rule is not None
    assert (item.rule.wall_time, item.rule.zone) == ("09:00", _LISBON)
    assert item.due_at == datetime(2026, 11, 6, 9, 0, tzinfo=UTC)


async def test_a_given_at_time_is_never_replaced_by_the_stored_one() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at_time="09:00", on_month_days=[15])
    content, is_error = await _edit(store, at_time="18:00", on_month_days=[20])
    assert not is_error, content
    (item,) = await store.list_active()
    assert item.rule is not None
    assert item.rule.wall_time == "18:00"


async def test_a_day_selector_on_a_fixed_interval_item_is_still_corrected() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, in_seconds=3600, every_seconds=86400)
    content, is_error = await _edit(store, on_month_days=[20])
    assert is_error
    assert content == (
        "'on_days', 'on_month_days', and 'on_dates' apply only together with 'at_time'"
    )
    (item,) = await store.list_active()
    assert item.rule is None


async def test_a_text_only_edit_reads_no_item_before_parsing() -> None:
    store = InMemoryScheduleStore()
    await _stored(store, at_time="09:00", on_month_days=[15])
    content, is_error = await _edit(store, text="pay the water bill")
    assert not is_error, content
    (item,) = await store.list_active()
    assert item.text == "pay the water bill"


async def test_a_moved_day_on_an_unknown_item_keeps_the_correction() -> None:
    content, is_error = await _edit(InMemoryScheduleStore(), item_id="item-9", on_days=["fri"])
    assert is_error
    assert content == (
        "'on_days', 'on_month_days', and 'on_dates' apply only together with 'at_time'"
    )


async def test_a_moved_day_while_the_store_is_down_reports_the_store() -> None:
    content, is_error = await _edit(_DownStore(), on_days=["fri"])
    assert is_error
    assert content == "the schedule store is unavailable: redis is down while reading item-1"
