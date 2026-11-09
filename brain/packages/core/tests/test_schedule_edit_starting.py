from datetime import UTC, datetime

import pytest

from cortex_core import (
    EditScheduledTool,
    InMemoryScheduleStore,
    ScheduleTaskTool,
    ToolCall,
    TurnStamp,
)

_NOW = datetime(2026, 11, 5, 5, 0, tzinfo=UTC)


class _FixedClock:
    def now(self) -> datetime:
        return _NOW


def _call(name: str, arguments: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments, stamp=TurnStamp(session_id="s1"))


async def _stored(**timing: object) -> InMemoryScheduleStore:
    store = InMemoryScheduleStore()
    tool = ScheduleTaskTool(
        store, _FixedClock(), tasks_enabled=False, max_active=32, item_id_factory=lambda: "item-1"
    )
    arguments: dict[str, object] = {"kind": "reminder", "text": "pay the gas bill", **timing}
    result = await tool.invoke(_call("schedule_task", arguments))
    assert not result.is_error, result.content
    return store


async def _edit(store: InMemoryScheduleStore, **changes: object) -> tuple[str, bool]:
    tool = EditScheduledTool(store, _FixedClock())
    result = await tool.invoke(_call("edit_scheduled", {"id": "item-1", **changes}))
    return result.content, result.is_error


async def _due(store: InMemoryScheduleStore) -> datetime:
    (item,) = await store.list_active()
    return item.due_at


async def test_an_edit_keeps_a_later_first_day_it_is_given() -> None:
    store = await _stored(at_time="09:00", on_month_days=[15], starting="2027-06-15")
    content, is_error = await _edit(
        store, at_time="10:00", on_month_days=[15], starting="2027-06-15"
    )
    assert not is_error, content
    assert await _due(store) == datetime(2027, 6, 15, 10, 0, tzinfo=UTC)
    assert "now due" in content


async def test_an_edit_without_a_first_day_names_the_earlier_fire() -> None:
    store = await _stored(at_time="09:00", on_month_days=[15], starting="2027-06-15")
    content, is_error = await _edit(store, at_time="10:00", on_month_days=[15])
    assert not is_error, content
    assert await _due(store) == datetime(2026, 11, 15, 10, 0, tzinfo=UTC)
    assert "now due" in content


@pytest.mark.parametrize(
    ("selector", "due"),
    [
        ({}, datetime(2027, 6, 15, 9, 0, tzinfo=UTC)),
        ({"on_days": ["mon"]}, datetime(2027, 6, 21, 9, 0, tzinfo=UTC)),
        ({"on_month_days": [1]}, datetime(2027, 7, 1, 9, 0, tzinfo=UTC)),
        ({"on_dates": ["03-01"]}, datetime(2028, 3, 1, 9, 0, tzinfo=UTC)),
    ],
)
async def test_each_day_form_starts_on_its_first_match_on_or_after_the_day(
    selector: dict[str, object], due: datetime
) -> None:
    store = await _stored(at_time="08:00")
    content, is_error = await _edit(store, at_time="09:00", starting="2027-06-15", **selector)
    assert not is_error, content
    assert await _due(store) == due


async def test_a_one_time_reminder_given_a_first_day_without_at_time_is_corrected() -> None:
    store = await _stored(at="2026-11-20T09:00:00")
    content, is_error = await _edit(store, text="pay the water bill", starting="2027-06-15")
    assert is_error
    assert content == "'starting' sets the first day of an 'at_time' repeat; give 'at_time' too"
    (item,) = await store.list_active()
    assert (item.text, item.due_at, item.rule) == (
        "pay the gas bill",
        datetime(2026, 11, 20, 9, 0, tzinfo=UTC),
        None,
    )


async def test_a_one_time_reminder_given_at_time_and_a_first_day_repeats_from_it() -> None:
    store = await _stored(at="2026-11-20T09:00:00")
    content, is_error = await _edit(store, at_time="09:00", starting="2027-06-15", repeat=True)
    assert not is_error, content
    assert await _due(store) == datetime(2027, 6, 15, 9, 0, tzinfo=UTC)


async def test_a_first_day_of_today_never_moves_to_a_time_already_past() -> None:
    store = await _stored(at_time="08:00")
    content, is_error = await _edit(store, at_time="04:00", starting="2026-11-05")
    assert not is_error, content
    assert await _due(store) == datetime(2026, 11, 6, 4, 0, tzinfo=UTC)


async def test_a_first_day_before_today_is_refused_and_names_today() -> None:
    store = await _stored(at_time="08:00")
    content, is_error = await _edit(store, at_time="09:00", starting="2026-11-04")
    assert is_error
    assert "'starting' 2026-11-04 has already passed; today is 2026-11-05 (UTC)" in content
    assert await _due(store) == datetime(2026, 11, 5, 8, 0, tzinfo=UTC)


async def test_a_first_day_that_is_not_a_date_is_refused() -> None:
    store = await _stored(at_time="08:00")
    content, is_error = await _edit(store, at_time="09:00", starting="15 June")
    assert is_error
    assert "'starting' must be an ISO-8601 calendar date" in content


def test_the_edit_spec_offers_the_first_day() -> None:
    spec = EditScheduledTool(InMemoryScheduleStore(), _FixedClock()).spec
    assert (
        "first day the rule selects on or after it"
        in (spec.parameters["properties"]["starting"]["description"])
    )
    assert "or its first on or after 'starting'" in spec.description
