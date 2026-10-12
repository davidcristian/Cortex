from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from cortex_core import (
    InMemoryScheduleStore,
    ScheduleTaskTool,
    ToolCall,
    Trust,
    TurnStamp,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)
_BULB = {"kind": "reminder", "text": "Check the bulb order.", "at": "2026-07-13T10:00:00"}


class FixedClock:
    def now(self) -> datetime:
        return _NOW


def _ids() -> Callable[[], str]:
    counter = iter(range(1, 100))
    return lambda: f"item-{next(counter)}"


def _tool(*, max_active: int = 32) -> tuple[ScheduleTaskTool, InMemoryScheduleStore]:
    store = InMemoryScheduleStore()
    tool = ScheduleTaskTool(
        store, FixedClock(), tasks_enabled=True, max_active=max_active, item_id_factory=_ids()
    )
    return tool, store


def _call(arguments: dict[str, Any], *, tainted: bool = False, chat: str = "chat") -> ToolCall:
    stamp = TurnStamp(session_id=chat, tainted=tainted)
    return ToolCall(id="c1", name="schedule_task", arguments=arguments, stamp=stamp)


async def test_a_repeated_request_names_the_stored_item_and_adds_no_copy() -> None:
    tool, store = _tool()
    await tool.invoke(_call(_BULB))
    result = await tool.invoke(_call(_BULB))
    assert not result.is_error
    assert result.trust is Trust.TRUSTED
    assert result.content == (
        "already scheduled reminder item-1: due 2026-07-13T10:00:00+00:00; it was on the "
        "schedule before this call, so no copy was added"
    )
    assert [item.id for item in await store.list_active()] == ["item-1"]


@pytest.mark.parametrize(
    "text", ["check the BULB order.", "Check  the\tbulb order.", "Check the bulb order"]
)
async def test_case_spacing_and_a_final_full_stop_do_not_make_a_new_request(text: str) -> None:
    tool, store = _tool()
    await tool.invoke(_call(_BULB))
    result = await tool.invoke(_call({**_BULB, "text": text}))
    assert result.content.startswith("already scheduled reminder item-1")
    assert len(await store.list_active()) == 1


async def test_a_repeat_from_another_chat_names_the_stored_item() -> None:
    tool, store = _tool()
    await tool.invoke(_call(_BULB, chat="yesterday"))
    result = await tool.invoke(_call(_BULB, chat="today"))
    assert result.content.startswith("already scheduled reminder item-1")
    assert [item.session_id for item in await store.list_active()] == ["yesterday"]


async def test_a_repeated_recurring_request_reports_the_stored_recurrence() -> None:
    tool, store = _tool()
    daily = {"kind": "reminder", "text": "vitamins", "at_time": "09:00"}
    await tool.invoke(_call(daily))
    result = await tool.invoke(_call(daily))
    assert result.content.startswith("already scheduled reminder item-1: due 2026-07-13T09:00")
    assert ", every day at 09:00; it was on the schedule" in result.content
    assert len(await store.list_active()) == 1


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"kind": "task"}, id="kind"),
        pytest.param({"text": "Check the lamp order."}, id="text"),
        pytest.param({"text": "Check the bulb order!"}, id="final-mark"),
        pytest.param({"at": "2026-07-13T10:01:00"}, id="due-time"),
        pytest.param({"every_seconds": 3600}, id="interval"),
        pytest.param({"at": None, "at_time": "10:00"}, id="daily-rule"),
        pytest.param({"kind": "task", "model": "fast"}, id="model"),
    ],
)
async def test_a_request_that_differs_in_one_field_is_added(change: dict[str, Any]) -> None:
    tool, store = _tool()
    base = {**_BULB, "kind": "task"} if "model" in change else _BULB
    await tool.invoke(_call(base))
    arguments = {key: value for key, value in {**base, **change}.items() if value is not None}
    result = await tool.invoke(_call(arguments))
    assert result.content.startswith("scheduled ")
    assert "item-2" in result.content
    assert len(await store.list_active()) == 2


async def test_a_weekly_rule_is_not_the_daily_rule_due_at_the_same_time() -> None:
    tool, store = _tool()
    daily = {"kind": "reminder", "text": "standup", "at_time": "10:00"}
    await tool.invoke(_call(daily))
    result = await tool.invoke(_call({**daily, "on_days": ["mon"]}))
    assert result.content.startswith("scheduled reminder item-2: due 2026-07-13T10:00")
    first, second = await store.list_active()
    assert first.due_at == second.due_at
    assert first.rule != second.rule


async def test_a_tainted_item_never_stands_in_for_a_clean_request() -> None:
    tool, store = _tool()
    await tool.invoke(_call(_BULB, tainted=True))
    result = await tool.invoke(_call(_BULB))
    assert result.content.startswith("scheduled reminder item-2")
    assert [item.tainted for item in await store.list_active()] == [True, False]


async def test_a_clean_item_stands_in_for_a_tainted_request() -> None:
    tool, store = _tool()
    await tool.invoke(_call(_BULB))
    result = await tool.invoke(_call(_BULB, tainted=True))
    assert result.content.startswith("already scheduled reminder item-1")
    assert [item.tainted for item in await store.list_active()] == [False]


async def test_a_tainted_item_stands_in_for_a_tainted_request() -> None:
    tool, store = _tool()
    await tool.invoke(_call(_BULB, tainted=True))
    result = await tool.invoke(_call(_BULB, tainted=True))
    assert result.content.startswith("already scheduled reminder item-1")
    assert len(await store.list_active()) == 1


async def test_a_repeated_request_on_a_full_schedule_names_the_stored_item() -> None:
    tool, store = _tool(max_active=1)
    await tool.invoke(_call(_BULB))
    result = await tool.invoke(_call(_BULB))
    assert not result.is_error
    assert result.content.startswith("already scheduled reminder item-1")
    other = await tool.invoke(_call({**_BULB, "text": "water the plants"}))
    assert other.is_error
    assert other.content.startswith("NOT SCHEDULED")
    assert len(await store.list_active()) == 1
