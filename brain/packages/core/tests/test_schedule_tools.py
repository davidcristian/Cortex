from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from cortex_core import (
    DAY_NAMES,
    MAX_MONTH_DAY,
    TAINTED_TASK_MSG,
    CalendarRule,
    CancelScheduledTool,
    CompositeToolRegistry,
    DisplayZone,
    EditScheduledTool,
    FireOutcome,
    InMemoryScheduleStore,
    ListScheduledTool,
    MonthDay,
    MonthDays,
    RecordingAuditSink,
    ScheduledItem,
    ScheduleEdit,
    ScheduleKind,
    ScheduleStoreError,
    ScheduleTaskTool,
    SnoozeScheduledTool,
    ToolCall,
    ToolDispatcher,
    Trust,
    TurnStamp,
    Weekdays,
    YearDays,
    ZoneContext,
)

_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _NOW


def _ids() -> Callable[[], str]:
    counter = iter(range(1, 100))

    def make() -> str:
        return f"item-{next(counter)}"

    return make


def _tool(
    store: InMemoryScheduleStore | None = None,
    *,
    tasks_enabled: bool = True,
    max_active: int = 32,
) -> tuple[ScheduleTaskTool, InMemoryScheduleStore]:
    store = store if store is not None else InMemoryScheduleStore()
    tool = ScheduleTaskTool(
        store,
        FixedClock(),
        tasks_enabled=tasks_enabled,
        max_active=max_active,
        item_id_factory=_ids(),
    )
    return tool, store


def _call(arguments: dict[str, Any], *, tainted: bool = False, session_id: str = "") -> ToolCall:
    stamp = TurnStamp(session_id=session_id, tainted=tainted)
    return ToolCall(id="c1", name="schedule_task", arguments=arguments, stamp=stamp)


class FailingStore(InMemoryScheduleStore):
    """A store that is down: every port method the tools use raises ScheduleStoreError."""

    def _down(self) -> ScheduleStoreError:
        msg = "redis down"
        return ScheduleStoreError(msg)

    async def add(self, item: ScheduledItem) -> None:
        del item
        raise self._down()

    async def list_active(self) -> Sequence[ScheduledItem]:
        raise self._down()

    async def cancel(self, item_id: str) -> bool:
        del item_id
        raise self._down()

    async def get(self, item_id: str) -> ScheduledItem | None:
        del item_id
        raise self._down()


def test_spec_includes_the_current_utc_time() -> None:
    tool, _ = _tool()
    assert "2026-07-12T12:00:00+00:00" in tool.spec.description


class SteppingClock:
    """``now()`` advances one minute per call, which shows the spec is rebuilt and not cached."""

    def __init__(self) -> None:
        self._minute = 0

    def now(self) -> datetime:
        self._minute += 1
        return _NOW + timedelta(minutes=self._minute)


async def test_spec_is_rebuilt_per_walk_with_the_live_clock() -> None:
    tool = ScheduleTaskTool(
        InMemoryScheduleStore(), SteppingClock(), tasks_enabled=False, max_active=8
    )
    dispatcher = ToolDispatcher(CompositeToolRegistry([tool]), RecordingAuditSink(), FixedClock())

    async def described() -> str:
        specs = {spec.name: spec for spec in await dispatcher.describe_tools()}
        return specs["schedule_task"].description

    first = await described()
    second = await described()
    assert first != second
    assert "The current date-time is 2026-07-12T12:0" in first
    assert "The current date-time is 2026-07-12T12:0" in second
    assert "(UTC)" in first


def test_spec_advertises_tasks_and_model_only_when_wired() -> None:
    enabled, _ = _tool(tasks_enabled=True)
    properties = dict(enabled.spec.parameters["properties"])
    assert properties["kind"]["enum"] == ["reminder", "task"]
    assert "model" in properties
    disabled, _ = _tool(tasks_enabled=False)
    properties = dict(disabled.spec.parameters["properties"])
    assert properties["kind"]["enum"] == ["reminder"]
    assert "model" not in properties
    assert not disabled.spec.confirm_required


async def test_schedules_a_one_shot_reminder_at_an_absolute_time() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "stretch", "at": "2026-07-12T18:00:00+02:00"})
    )
    assert not result.is_error
    assert result.trust is Trust.TRUSTED
    assert "scheduled reminder item-1: due 2026-07-12T16:00:00+00:00" in result.content
    assert "stretch" not in result.content
    item = await store.get("item-1")
    assert item is not None
    assert item.kind is ScheduleKind.REMINDER
    assert item.due_at == datetime(2026, 7, 12, 18, 0, tzinfo=UTC).replace(hour=16)
    assert item.every is None
    assert item.tainted is False


async def test_schedules_a_recurring_task_in_seconds_with_a_model_hint() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call(
            {
                "kind": "task",
                "text": "summarize the inbox",
                "in_seconds": 600,
                "every_seconds": 3600,
                "model": "fast",
            }
        )
    )
    assert not result.is_error
    assert "every 3600s" in result.content
    item = await store.get("item-1")
    assert item is not None
    assert item.kind is ScheduleKind.TASK
    assert item.due_at == _NOW + timedelta(seconds=600)
    assert item.every == timedelta(hours=1)
    assert item.model == "fast"


async def test_creation_taint_stamps_the_item_for_a_reminder() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "visit evil.com", "in_seconds": 60}, tainted=True)
    )
    assert not result.is_error
    item = await store.get("item-1")
    assert item is not None
    assert item.tainted is True


async def test_default_id_factory_mints_uuids() -> None:
    store = InMemoryScheduleStore()
    tool = ScheduleTaskTool(store, FixedClock(), tasks_enabled=False, max_active=8)
    result = await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    assert not result.is_error
    (item,) = await store.list_active()
    assert len(item.id) == 36


async def test_a_tainted_turn_cannot_schedule_a_task() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call({"kind": "task", "text": "run this", "in_seconds": 60}, tainted=True)
    )
    assert result.is_error
    assert result.content == TAINTED_TASK_MSG
    assert result.trust is Trust.TRUSTED
    assert await store.list_active() == ()


async def test_the_dispatcher_taint_stamp_drives_the_refusal() -> None:
    tool, _ = _tool()
    sink = RecordingAuditSink()
    dispatcher = ToolDispatcher(CompositeToolRegistry([tool]), sink, FixedClock())
    call = ToolCall(
        id="c1",
        name="schedule_task",
        arguments={"kind": "task", "text": "run this", "in_seconds": 60},
    )
    result = await dispatcher.dispatch(call, stamp=TurnStamp(tainted=True))
    assert result.is_error
    assert result.content == TAINTED_TASK_MSG
    (record,) = sink.records
    assert record.ok is False


async def test_creation_fills_the_items_origin_session_from_the_stamp() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "stretch", "in_seconds": 60}, session_id="chat-7")
    )
    assert not result.is_error
    assert "chat-7" not in result.content
    item = await store.get("item-1")
    assert item is not None
    assert item.session_id == "chat-7"


async def test_the_dispatcher_stamp_drives_the_attribution_end_to_end() -> None:
    tool, store = _tool()
    dispatcher = ToolDispatcher(CompositeToolRegistry([tool]), RecordingAuditSink(), FixedClock())
    call = ToolCall(
        id="c1",
        name="schedule_task",
        arguments={"kind": "reminder", "text": "stretch", "in_seconds": 60},
        stamp=TurnStamp(session_id="forged"),
    )
    result = await dispatcher.dispatch(call, stamp=TurnStamp(session_id="chat-9"))
    assert not result.is_error
    (item,) = await store.list_active()
    assert item.session_id == "chat-9"


async def test_the_active_items_cap_bounds_creation() -> None:
    tool, _ = _tool(max_active=1)
    first = await tool.invoke(_call({"kind": "reminder", "text": "a", "in_seconds": 60}))
    assert not first.is_error
    second = await tool.invoke(_call({"kind": "reminder", "text": "b", "in_seconds": 60}))
    assert second.is_error
    assert "the schedule is full (1 active items)" in second.content


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"text": "x", "in_seconds": 60}, "'kind' must be"),
        ({"kind": "chore", "text": "x", "in_seconds": 60}, "'kind' must be"),
        ({"kind": "reminder", "in_seconds": 60}, "'text' must be"),
        ({"kind": "reminder", "text": "  ", "in_seconds": 60}, "'text' must be"),
        ({"kind": "reminder", "text": 3, "in_seconds": 60}, "'text' must be"),
        ({"kind": "reminder", "text": "x"}, "exactly one of 'at'"),
        (
            {"kind": "reminder", "text": "x", "at": "2026-07-12T18:00:00+00:00", "in_seconds": 9},
            "exactly one of 'at'",
        ),
        ({"kind": "reminder", "text": "x", "at": 5}, "'at' must be an ISO-8601"),
        ({"kind": "reminder", "text": "x", "at": "tomorrowish"}, "'at' must be an ISO-8601"),
        ({"kind": "reminder", "text": "x", "in_seconds": True}, "'in_seconds' must be"),
        ({"kind": "reminder", "text": "x", "in_seconds": "60"}, "'in_seconds' must be"),
        ({"kind": "reminder", "text": "x", "in_seconds": 0}, "'in_seconds' must be"),
        ({"kind": "reminder", "text": "x", "in_seconds": -5}, "'in_seconds' must be"),
        ({"kind": "reminder", "text": "x", "in_seconds": 10**400}, "'in_seconds' must be"),
        ({"kind": "reminder", "text": "x", "in_seconds": 10**12}, "'in_seconds' must be"),
        (
            {"kind": "reminder", "text": "x", "in_seconds": 60, "every_seconds": 59},
            "'every_seconds'",
        ),
        (
            {"kind": "reminder", "text": "x", "in_seconds": 60, "every_seconds": True},
            "'every_seconds'",
        ),
        (
            {"kind": "reminder", "text": "x", "in_seconds": 60, "every_seconds": 1e300},
            "'every_seconds'",
        ),
        (
            {"kind": "reminder", "text": "x", "in_seconds": 60, "model": "fast"},
            "'model' applies only",
        ),
        ({"kind": "task", "text": "x", "in_seconds": 60, "model": 3}, "'model' must be"),
    ],
)
async def test_bad_arguments_become_correctable_errors(
    arguments: dict[str, Any], expected: str
) -> None:
    tool, store = _tool()
    result = await tool.invoke(_call(arguments))
    assert result.is_error
    assert expected in result.content
    assert result.trust is Trust.TRUSTED
    assert await store.list_active() == ()


async def test_task_kind_is_rejected_when_delegation_is_not_wired() -> None:
    tool, _ = _tool(tasks_enabled=False)
    result = await tool.invoke(_call({"kind": "task", "text": "x", "in_seconds": 60}))
    assert result.is_error
    assert "reminders only" in result.content


async def test_store_errors_become_trusted_error_results() -> None:
    tool, _ = _tool(FailingStore())
    result = await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    assert result.is_error
    assert "schedule store is unavailable" in result.content
    assert result.trust is Trust.TRUSTED


async def test_list_and_cancel_wrap_a_down_store() -> None:
    failing = FailingStore()
    listing = await ListScheduledTool(failing).invoke(
        ToolCall(id="c", name="list_scheduled", arguments={})
    )
    assert listing.is_error
    assert "unavailable" in listing.content
    cancel = await CancelScheduledTool(failing).invoke(
        ToolCall(id="c", name="cancel_scheduled", arguments={"id": "x"})
    )
    assert cancel.is_error
    assert "unavailable" in cancel.content


async def test_empty_listing_is_trusted() -> None:
    result = await ListScheduledTool(InMemoryScheduleStore()).invoke(
        ToolCall(id="c", name="list_scheduled", arguments={})
    )
    assert result.content == "no scheduled items"
    assert result.trust is Trust.TRUSTED


async def test_listing_is_trusted_when_every_item_is_clean() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "stretch", "in_seconds": 60}))
    result = await ListScheduledTool(store).invoke(
        ToolCall(id="c", name="list_scheduled", arguments={})
    )
    assert result.trust is Trust.TRUSTED
    assert "[item-1] reminder due 2026-07-12T12:01:00+00:00: stretch" in result.content


async def test_listing_with_any_tainted_item_is_untrusted_and_marked() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "clean", "in_seconds": 60}))
    await tool.invoke(_call({"kind": "reminder", "text": "evil", "in_seconds": 90}, tainted=True))
    result = await ListScheduledTool(store).invoke(
        ToolCall(id="c", name="list_scheduled", arguments={})
    )
    assert result.trust is Trust.UNTRUSTED
    assert "from untrusted content" in result.content


async def test_listing_shows_recurrence_firing_delivery_and_outcome() -> None:
    store = InMemoryScheduleStore()
    tool, _ = _tool(store)
    await tool.invoke(
        _call({"kind": "task", "text": "sweep", "in_seconds": 60, "every_seconds": 3600})
    )
    (claim,) = await store.claim_due(
        _NOW + timedelta(seconds=60), lease=timedelta(seconds=300), limit=8
    )
    listing = await ListScheduledTool(store).invoke(
        ToolCall(id="c", name="list_scheduled", arguments={})
    )
    assert "every 3600s" in listing.content
    assert "firing now" in listing.content
    outcome = FireOutcome(
        fired_at=_NOW,
        next_due=_NOW + timedelta(hours=1),
        deliverable=True,
        outcome="[subagent 1] ok",
    )
    assert await store.finish(claim, outcome) is True
    listing = await ListScheduledTool(store).invoke(
        ToolCall(id="c", name="list_scheduled", arguments={})
    )
    assert "fired awaiting delivery" in listing.content
    assert "last outcome: [subagent 1] ok" in listing.content


async def test_cancel_round_trip() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    result = await CancelScheduledTool(store).invoke(
        ToolCall(id="c", name="cancel_scheduled", arguments={"id": "item-1"})
    )
    assert not result.is_error
    assert result.content == "cancelled item-1"
    assert await store.list_active() == ()


async def test_cancel_unknown_id_is_a_correctable_error() -> None:
    result = await CancelScheduledTool(InMemoryScheduleStore()).invoke(
        ToolCall(id="c", name="cancel_scheduled", arguments={"id": "ghost"})
    )
    assert result.is_error
    assert "no scheduled item ghost" in result.content


@pytest.mark.parametrize("bad_id", [None, 3, ""])
async def test_cancel_requires_a_string_id(bad_id: object) -> None:
    result = await CancelScheduledTool(InMemoryScheduleStore()).invoke(
        ToolCall(id="c", name="cancel_scheduled", arguments={"id": bad_id})
    )
    assert result.is_error
    assert "'id' must be" in result.content


def test_view_tool_specs_name_their_tools() -> None:
    assert ListScheduledTool(InMemoryScheduleStore()).spec.name == "list_scheduled"
    assert CancelScheduledTool(InMemoryScheduleStore()).spec.name == "cancel_scheduled"
    assert _snooze_tool(InMemoryScheduleStore()).spec.name == "snooze_scheduled"
    assert EditScheduledTool(InMemoryScheduleStore(), FixedClock()).spec.name == "edit_scheduled"


def _snooze_tool(store: InMemoryScheduleStore) -> SnoozeScheduledTool:
    return SnoozeScheduledTool(store, FixedClock())


def _snooze_call(arguments: dict[str, Any]) -> ToolCall:
    return ToolCall(id="c", name="snooze_scheduled", arguments=arguments)


async def test_snooze_round_trip_postpones_from_now() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "stretch", "in_seconds": 60}))
    result = await _snooze_tool(store).invoke(_snooze_call({"id": "item-1", "for_seconds": 600}))
    assert not result.is_error
    assert result.content == "snoozed item-1: now due 2026-07-12T12:10:00+00:00"
    assert result.trust is Trust.TRUSTED
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.due_at == _NOW + timedelta(minutes=10)
    assert "stretch" not in result.content


async def test_snooze_unknown_id_is_a_correctable_error() -> None:
    result = await _snooze_tool(InMemoryScheduleStore()).invoke(
        _snooze_call({"id": "ghost", "for_seconds": 600})
    )
    assert result.is_error
    assert "no scheduled item ghost" in result.content


async def test_snooze_moves_only_the_next_occurrence_of_a_recurring_item() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "water", "in_seconds": 60, "every_seconds": 3600})
    )
    result = await _snooze_tool(store).invoke(_snooze_call({"id": "item-1", "for_seconds": 600}))
    assert not result.is_error
    assert result.content == "snoozed item-1: now due 2026-07-12T12:10:00+00:00"
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.due_at == _NOW + timedelta(minutes=10)
    assert loaded.every == timedelta(hours=1)
    assert loaded.anchor == _NOW + timedelta(seconds=60)


async def test_snooze_refuses_a_firing_item() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    await store.claim_due(_NOW + timedelta(seconds=60), lease=timedelta(seconds=300), limit=8)
    result = await _snooze_tool(store).invoke(_snooze_call({"id": "item-1", "for_seconds": 600}))
    assert result.is_error
    assert "firing right now" in result.content


async def test_snooze_racing_a_change_reports_it_correctably() -> None:
    class RacingStore(InMemoryScheduleStore):
        async def snooze(self, item_id: str, *, until: datetime) -> bool:
            del item_id, until
            return False

    store = RacingStore()
    tool = ScheduleTaskTool(
        store, FixedClock(), tasks_enabled=False, max_active=8, item_id_factory=_ids()
    )
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    result = await _snooze_tool(store).invoke(_snooze_call({"id": "item-1", "for_seconds": 600}))
    assert result.is_error
    assert "changed underneath" in result.content


@pytest.mark.parametrize("bad_id", [None, 3, ""])
async def test_snooze_requires_a_string_id(bad_id: object) -> None:
    result = await _snooze_tool(InMemoryScheduleStore()).invoke(
        _snooze_call({"id": bad_id, "for_seconds": 600})
    )
    assert result.is_error
    assert "'id' must be" in result.content


@pytest.mark.parametrize("bad_delay", [None, "soon", True, 59, 315_360_001])
async def test_snooze_bounds_the_delay(bad_delay: object) -> None:
    result = await _snooze_tool(InMemoryScheduleStore()).invoke(
        _snooze_call({"id": "item-1", "for_seconds": bad_delay})
    )
    assert result.is_error
    assert "'for_seconds' must be a number between" in result.content


async def test_snooze_wraps_a_down_store() -> None:
    result = await _snooze_tool(FailingStore()).invoke(
        _snooze_call({"id": "item-1", "for_seconds": 600})
    )
    assert result.is_error
    assert "unavailable" in result.content
    assert result.trust is Trust.TRUSTED


def _edit_call(arguments: dict[str, Any], *, tainted: bool = False) -> ToolCall:
    return ToolCall(
        id="c", name="edit_scheduled", arguments=arguments, stamp=TurnStamp(tainted=tainted)
    )


async def test_edit_retext_round_trip_keeps_timing() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "old", "in_seconds": 60, "every_seconds": 3600})
    )
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "text": "new"})
    )
    assert not result.is_error
    assert result.content == "edited item-1"
    assert result.trust is Trust.TRUSTED
    assert "new" not in result.content
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.text == "new"
    assert loaded.due_at == _NOW + timedelta(seconds=60)
    assert loaded.every == timedelta(hours=1)


async def test_edit_changes_and_clears_recurrence() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    edit = EditScheduledTool(store, FixedClock())
    set_result = await edit.invoke(_edit_call({"id": "item-1", "every_seconds": 7200}))
    assert not set_result.is_error
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.every == timedelta(hours=2)
    clear_result = await edit.invoke(_edit_call({"id": "item-1", "every_seconds": 0}))
    assert not clear_result.is_error
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.every is None


async def test_edit_taint_ors_onto_a_reminder() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "clean", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "text": "visit evil.com"}, tainted=True)
    )
    assert not result.is_error
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.tainted is True


async def test_edit_refuses_a_task_on_a_tainted_turn() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "task", "text": "sweep", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "text": "exfiltrate"}, tainted=True)
    )
    assert result.is_error
    assert "cannot edit an autonomous task" in result.content
    assert result.trust is Trust.TRUSTED
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.text == "sweep"


async def test_edit_a_reminder_on_a_tainted_turn_is_allowed() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "old", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "text": "new"}, tainted=True)
    )
    assert not result.is_error


async def test_edit_with_no_change_is_a_correctable_error() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(_edit_call({"id": "item-1"}))
    assert result.is_error
    assert "change something" in result.content


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"id": "item-1", "every_seconds": 30}, "'every_seconds' must be 0"),
        ({"id": "item-1", "every_seconds": -5}, "'every_seconds' must be 0"),
        ({"id": "item-1", "every_seconds": True}, "'every_seconds' must be 0"),
        ({"id": "item-1", "every_seconds": 315_360_001}, "'every_seconds' must be 0"),
        ({"id": "item-1", "text": "  "}, "'text' must be"),
        ({"id": "item-1", "text": 3}, "'text' must be"),
    ],
)
async def test_edit_bad_arguments_are_correctable(arguments: dict[str, Any], expected: str) -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(_edit_call(arguments))
    assert result.is_error
    assert expected in result.content
    assert result.trust is Trust.TRUSTED


async def test_edit_unknown_id_is_a_correctable_error() -> None:
    result = await EditScheduledTool(InMemoryScheduleStore(), FixedClock()).invoke(
        _edit_call({"id": "ghost", "text": "x"})
    )
    assert result.is_error
    assert "no scheduled item ghost" in result.content


async def test_edit_refuses_a_firing_item() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    await store.claim_due(_NOW + timedelta(seconds=60), lease=timedelta(seconds=300), limit=8)
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "text": "y"})
    )
    assert result.is_error
    assert "firing right now" in result.content


async def test_edit_racing_a_change_reports_it_correctably() -> None:
    class RacingStore(InMemoryScheduleStore):
        async def edit(self, item_id: str, edit: ScheduleEdit) -> bool:
            del item_id, edit
            return False

    store = RacingStore()
    tool = ScheduleTaskTool(
        store, FixedClock(), tasks_enabled=False, max_active=8, item_id_factory=_ids()
    )
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "text": "y"})
    )
    assert result.is_error
    assert "changed underneath" in result.content


@pytest.mark.parametrize("bad_id", [None, 3, ""])
async def test_edit_requires_a_string_id(bad_id: object) -> None:
    result = await EditScheduledTool(InMemoryScheduleStore(), FixedClock()).invoke(
        _edit_call({"id": bad_id, "text": "x"})
    )
    assert result.is_error
    assert "'id' must be" in result.content


async def test_edit_wraps_a_down_store() -> None:
    tool = EditScheduledTool(FailingStore(), FixedClock())
    result = await tool.invoke(_edit_call({"id": "item-1", "text": "x"}))
    assert result.is_error
    assert "unavailable" in result.content
    assert result.trust is Trust.TRUSTED


def test_spec_advertises_the_wall_clock_form_with_the_zone_and_the_day_names() -> None:
    tool, _ = _tool()
    properties = tool.spec.parameters["properties"]
    assert "HH:MM in UTC" in properties["at_time"]["description"]
    assert properties["on_days"]["items"]["enum"] == list(DAY_NAMES)
    assert "at_time" in tool.spec.description


async def test_at_time_derives_the_first_fire_and_stores_the_rule() -> None:
    tool, store = _tool()
    result = await tool.invoke(_call({"kind": "reminder", "text": "stretch", "at_time": "09:00"}))
    assert not result.is_error
    item = (await store.list_active())[0]
    assert item.rule == CalendarRule(hour=9, minute=0)
    assert item.every is None
    # _NOW is 12:00, so today's 09:00 has passed and the first fire is tomorrow's.
    assert item.due_at == datetime(2026, 7, 13, 9, 0, tzinfo=UTC)
    assert "every day at 09:00" in result.content


async def test_on_days_restricts_the_rule_and_the_first_fire() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call(
            {"kind": "reminder", "text": "standup", "at_time": "09:30", "on_days": ["fri", "mon"]}
        )
    )
    assert not result.is_error
    item = (await store.list_active())[0]
    assert item.rule == CalendarRule(hour=9, minute=30, on=Weekdays(days=frozenset({0, 4})))
    assert item.due_at == datetime(2026, 7, 13, 9, 30, tzinfo=UTC)


async def test_a_listing_describes_a_calendar_item_in_wall_clock_terms() -> None:
    store = InMemoryScheduleStore()
    tool, _ = _tool(store)
    await tool.invoke(_call({"kind": "reminder", "text": "stretch", "at_time": "09:00"}))
    listing = await ListScheduledTool(store).invoke(
        ToolCall(id="c2", name="list_scheduled", arguments={})
    )
    assert "every day at 09:00" in listing.content
    assert "every 86400s" not in listing.content


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"at_time": "09:00", "at": "2026-07-12T18:00:00"}, "exactly one"),
        ({"at_time": "09:00", "in_seconds": 600}, "exactly one"),
        ({"at_time": "09:00", "every_seconds": 3600}, "already recurs"),
        ({"in_seconds": 600, "on_days": ["mon"]}, "only together with 'at_time'"),
        ({"at_time": 900}, "'at_time' must be"),
        ({"at_time": "9am"}, "'at_time' must be"),
        ({"at_time": "09:00:30"}, "'at_time' must be"),
        ({"at_time": "09:00+02:00"}, "'at_time' must be"),
        ({"at_time": "09:00", "on_days": "mon"}, "'on_days' must be"),
        ({"at_time": "09:00", "on_days": []}, "'on_days' must be"),
        ({"at_time": "09:00", "on_days": ["funday"]}, "'on_days' must be"),
        ({"at_time": "09:00", "on_days": [3]}, "'on_days' must be"),
    ],
)
async def test_a_bad_wall_clock_request_is_a_correction_not_an_exception(
    arguments: dict[str, Any], expected: str
) -> None:
    tool, store = _tool()
    result = await tool.invoke(_call({"kind": "reminder", "text": "x", **arguments}))
    assert result.is_error
    assert result.trust is Trust.TRUSTED
    assert expected in result.content
    assert not await store.list_active()


async def test_a_rule_with_no_schedulable_occurrence_is_a_correction() -> None:
    class EndOfTimeClock:
        def now(self) -> datetime:
            return datetime(9999, 12, 31, 23, 59, tzinfo=UTC)

    store = InMemoryScheduleStore()
    tool = ScheduleTaskTool(
        store, EndOfTimeClock(), tasks_enabled=True, max_active=32, item_id_factory=_ids()
    )
    result = await tool.invoke(_call({"kind": "reminder", "text": "x", "at_time": "23:30"}))
    assert result.is_error
    assert "no next occurrence" in result.content


def test_edit_spec_advertises_the_wall_clock_form_beside_the_interval() -> None:
    properties = EditScheduledTool(InMemoryScheduleStore(), FixedClock()).spec
    assert "at_time" in properties.description
    assert properties.parameters["properties"]["on_days"]["items"]["enum"] == list(DAY_NAMES)


async def test_edit_sets_a_rule_on_an_interval_item_and_moves_the_due_time() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "standup", "in_seconds": 60, "every_seconds": 3600})
    )
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "at_time": "09:00", "on_days": ["mon", "fri"]})
    )
    assert not result.is_error
    assert result.content == "edited item-1: now due 2026-07-13T09:00:00+00:00"
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule == CalendarRule(hour=9, minute=0, on=Weekdays(days=frozenset({0, 4})))
    assert loaded.every is None
    # _NOW is Sunday 2026-07-12 12:00, so the Monday occurrence is the first one.
    assert loaded.due_at == datetime(2026, 7, 13, 9, 0, tzinfo=UTC)


async def test_edit_retimes_an_existing_rule_rather_than_firing_the_old_one_once_more() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "standup", "at_time": "09:00"}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "at_time": "10:00"})
    )
    assert not result.is_error
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule == CalendarRule(hour=10, minute=0)
    assert loaded.due_at == datetime(2026, 7, 13, 10, 0, tzinfo=UTC)


async def test_edit_can_switch_a_rule_back_to_an_interval() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "standup", "at_time": "09:00"}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "every_seconds": 7200})
    )
    assert not result.is_error
    assert result.content == "edited item-1"
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule is None
    assert loaded.every == timedelta(hours=2)


async def test_edit_renders_the_new_due_time_in_the_configured_zone() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "standup", "in_seconds": 60}))
    zone = DisplayZone(name="Europe/Bucharest", tz=ZoneInfo("Europe/Bucharest"))
    result = await EditScheduledTool(store, FixedClock(), zones=ZoneContext(default=zone)).invoke(
        _edit_call({"id": "item-1", "at_time": "09:00"})
    )
    assert not result.is_error
    assert result.content == "edited item-1: now due 2026-07-13T09:00:00+03:00"


async def test_edit_retexts_and_reschedules_in_one_call() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "old", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "text": "new", "at_time": "09:00"})
    )
    assert not result.is_error
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.text == "new"
    assert loaded.rule == CalendarRule(hour=9, minute=0)


async def test_edit_refuses_a_task_rule_change_on_a_tainted_turn() -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "task", "text": "sweep", "in_seconds": 60}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "at_time": "03:00"}, tainted=True)
    )
    assert result.is_error
    assert "cannot edit an autonomous task" in result.content
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule is None


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"at_time": "09:00", "every_seconds": 3600}, "already recurs on the wall clock"),
        ({"on_days": ["mon"]}, "apply only together with 'at_time'"),
        ({"on_month_days": [1]}, "apply only together with 'at_time'"),
        ({"at_time": "09:00", "on_days": ["mon"], "on_month_days": [1]}, "never more than one"),
        ({"at_time": "09:00", "on_month_days": [0]}, "'on_month_days' must be"),
        ({"at_time": "9am"}, "'at_time' must be"),
        ({"at_time": "09:00:30"}, "'at_time' must be"),
        ({"at_time": "09:00", "on_days": []}, "'on_days' must be"),
        ({"at_time": "09:00", "on_days": ["funday"]}, "'on_days' must be"),
    ],
)
async def test_edit_bad_rule_arguments_are_correctable(
    arguments: dict[str, Any], expected: str
) -> None:
    tool, store = _tool()
    await tool.invoke(_call({"kind": "reminder", "text": "x", "at_time": "09:00"}))
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", **arguments})
    )
    assert result.is_error
    assert result.trust is Trust.TRUSTED
    assert expected in result.content
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule == CalendarRule(hour=9, minute=0)


async def test_edit_to_a_rule_with_no_schedulable_occurrence_is_a_correction() -> None:
    class EndOfTimeClock:
        def now(self) -> datetime:
            return datetime(9999, 12, 31, 23, 59, tzinfo=UTC)

    store = InMemoryScheduleStore()
    tool = ScheduleTaskTool(
        store, FixedClock(), tasks_enabled=True, max_active=32, item_id_factory=_ids()
    )
    await tool.invoke(_call({"kind": "reminder", "text": "x", "in_seconds": 60}))
    result = await EditScheduledTool(store, EndOfTimeClock()).invoke(
        _edit_call({"id": "item-1", "at_time": "23:30"})
    )
    assert result.is_error
    assert "no next occurrence" in result.content


def test_spec_advertises_the_month_day_selector_with_its_bounds() -> None:
    tool, _ = _tool()
    on_month_days = tool.spec.parameters["properties"]["on_month_days"]
    assert on_month_days["items"] == {"type": "integer", "minimum": 1, "maximum": MAX_MONTH_DAY}
    assert "last day of every month" in on_month_days["description"]
    assert "on_month_days" in tool.spec.description


async def test_on_month_days_stores_a_monthly_rule_and_derives_the_first_fire() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "rent", "at_time": "09:00", "on_month_days": [20]})
    )
    assert not result.is_error
    item = (await store.list_active())[0]
    assert item.rule == CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({20})))
    assert item.every is None
    assert item.due_at == datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
    assert "every month on the 20th at 09:00" in result.content


async def test_a_month_day_already_past_this_month_first_fires_next_month() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "rent", "at_time": "09:00", "on_month_days": [1]})
    )
    item = (await store.list_active())[0]
    assert item.due_at == datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


async def test_a_listing_describes_a_monthly_item_in_calendar_terms() -> None:
    store = InMemoryScheduleStore()
    tool, _ = _tool(store)
    await tool.invoke(
        _call({"kind": "reminder", "text": "rent", "at_time": "09:00", "on_month_days": [1, 15]})
    )
    listing = await ListScheduledTool(store).invoke(
        ToolCall(id="c2", name="list_scheduled", arguments={})
    )
    assert "every month on the 1st, 15th at 09:00" in listing.content


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"at_time": "09:00", "on_month_days": 1}, "'on_month_days' must be"),
        ({"at_time": "09:00", "on_month_days": []}, "'on_month_days' must be"),
        ({"at_time": "09:00", "on_month_days": ["1"]}, "'on_month_days' must be"),
        ({"at_time": "09:00", "on_month_days": [True]}, "'on_month_days' must be"),
        ({"at_time": "09:00", "on_month_days": [0]}, "'on_month_days' must be"),
        ({"at_time": "09:00", "on_month_days": [MAX_MONTH_DAY + 1]}, "'on_month_days' must be"),
        ({"in_seconds": 600, "on_month_days": [1]}, "only together with 'at_time'"),
        ({"at_time": "09:00", "on_days": ["mon"], "on_month_days": [1]}, "never more than one"),
    ],
)
async def test_a_bad_month_day_request_is_a_correction_not_an_exception(
    arguments: dict[str, Any], expected: str
) -> None:
    tool, store = _tool()
    result = await tool.invoke(_call({"kind": "reminder", "text": "x", **arguments}))
    assert result.is_error
    assert result.trust is Trust.TRUSTED
    assert expected in result.content
    assert not await store.list_active()


def test_edit_spec_advertises_the_month_day_selector_too() -> None:
    spec = EditScheduledTool(InMemoryScheduleStore(), FixedClock()).spec
    assert spec.parameters["properties"]["on_month_days"]["items"]["maximum"] == MAX_MONTH_DAY
    assert "on_month_days" in spec.description


async def test_edit_switches_a_weekly_rule_to_a_monthly_one() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "rent", "at_time": "09:00", "on_days": ["mon"]})
    )
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "at_time": "09:00", "on_month_days": [20]})
    )
    assert not result.is_error
    assert result.content == "edited item-1: now due 2026-07-20T09:00:00+00:00"
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule == CalendarRule(hour=9, minute=0, on=MonthDays(days=frozenset({20})))


def test_spec_advertises_the_year_date_selector_with_its_format() -> None:
    tool, _ = _tool()
    on_dates = tool.spec.parameters["properties"]["on_dates"]
    assert on_dates["items"] == {"type": "string", "pattern": "^[0-9]{1,2}-[0-9]{1,2}$"}
    assert "MM-DD" in on_dates["description"]
    assert "on_dates" in tool.spec.description


def test_both_verbs_advertise_one_shared_day_selector_vocabulary() -> None:
    create = _tool()[0].spec.parameters["properties"]
    edit = EditScheduledTool(InMemoryScheduleStore(), FixedClock()).spec.parameters["properties"]
    for key in ("on_days", "on_month_days", "on_dates"):
        assert create[key] == edit[key]


async def test_on_dates_stores_a_yearly_rule_and_derives_the_first_fire() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "gifts", "at_time": "09:00", "on_dates": ["12-25"]})
    )
    assert not result.is_error
    item = (await store.list_active())[0]
    assert item.rule == CalendarRule(
        hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)}))
    )
    assert item.every is None
    assert item.due_at == datetime(2026, 12, 25, 9, 0, tzinfo=UTC)
    assert "every year on 25 dec at 09:00" in result.content


async def test_a_date_already_past_this_year_first_fires_next_year() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "taxes", "at_time": "09:00", "on_dates": ["03-03"]})
    )
    item = (await store.list_active())[0]
    assert item.due_at == datetime(2027, 3, 3, 9, 0, tzinfo=UTC)


async def test_an_unpadded_date_is_accepted_since_it_is_not_ambiguous() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "x", "at_time": "09:00", "on_dates": ["1-5"]})
    )
    item = (await store.list_active())[0]
    assert item.rule == CalendarRule(
        hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(1, 5)}))
    )


async def test_a_listing_describes_a_yearly_item_in_calendar_terms() -> None:
    store = InMemoryScheduleStore()
    tool, _ = _tool(store)
    await tool.invoke(
        _call({"kind": "reminder", "text": "x", "at_time": "09:00", "on_dates": ["12-25", "01-01"]})
    )
    listing = await ListScheduledTool(store).invoke(
        ToolCall(id="c2", name="list_scheduled", arguments={})
    )
    assert "every year on 1 jan, 25 dec at 09:00" in listing.content


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"at_time": "09:00", "on_dates": "12-25"}, "'on_dates' must be"),
        ({"at_time": "09:00", "on_dates": []}, "'on_dates' must be"),
        ({"at_time": "09:00", "on_dates": [1225]}, "'on_dates' must be"),
        ({"at_time": "09:00", "on_dates": ["25 december"]}, "'on_dates' must be"),
        ({"at_time": "09:00", "on_dates": ["2026-12-25"]}, "'on_dates' must be"),
        ({"at_time": "09:00", "on_dates": ["13-01"]}, "'on_dates' must be"),
        ({"at_time": "09:00", "on_dates": ["02-30"]}, "'on_dates' must be"),
        ({"in_seconds": 600, "on_dates": ["12-25"]}, "only together with 'at_time'"),
        ({"at_time": "09:00", "on_days": ["mon"], "on_dates": ["12-25"]}, "never more than one"),
        (
            {"at_time": "09:00", "on_month_days": [1], "on_dates": ["12-25"]},
            "never more than one",
        ),
    ],
)
async def test_a_bad_year_date_request_is_a_correction_not_an_exception(
    arguments: dict[str, Any], expected: str
) -> None:
    tool, store = _tool()
    result = await tool.invoke(_call({"kind": "reminder", "text": "x", **arguments}))
    assert result.is_error
    assert result.trust is Trust.TRUSTED
    assert expected in result.content
    assert not await store.list_active()


async def test_the_leap_day_is_schedulable_and_clamps_in_a_common_year() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "x", "at_time": "09:00", "on_dates": ["02-29"]})
    )
    item = (await store.list_active())[0]
    assert item.due_at == datetime(2027, 2, 28, 9, 0, tzinfo=UTC)


def test_edit_spec_advertises_the_year_date_selector_too() -> None:
    spec = EditScheduledTool(InMemoryScheduleStore(), FixedClock()).spec
    assert spec.parameters["properties"]["on_dates"]["items"]["type"] == "string"
    assert "on_dates" in spec.description


async def test_edit_switches_a_monthly_rule_to_a_yearly_one() -> None:
    tool, store = _tool()
    await tool.invoke(
        _call({"kind": "reminder", "text": "rent", "at_time": "09:00", "on_month_days": [20]})
    )
    result = await EditScheduledTool(store, FixedClock()).invoke(
        _edit_call({"id": "item-1", "at_time": "09:00", "on_dates": ["12-25"]})
    )
    assert not result.is_error
    assert result.content == "edited item-1: now due 2026-12-25T09:00:00+00:00"
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule == CalendarRule(
        hour=9, minute=0, on=YearDays(days=frozenset({MonthDay(12, 25)}))
    )


_NEW_YORK = DisplayZone(name="America/New_York", tz=ZoneInfo("America/New_York"))


class _MapResolver:
    """A ZoneResolver over a fixed name to zone map, in place of the real zoneinfo lookup."""

    def __init__(self, zones: dict[str, DisplayZone]) -> None:
        self._zones = zones

    def resolve(self, name: str) -> DisplayZone | None:
        return self._zones.get(name)


_RESOLVER = _MapResolver({"America/New_York": _NEW_YORK})


def _zoned_tool() -> tuple[ScheduleTaskTool, InMemoryScheduleStore]:
    """A creation tool whose deployment zone is UTC and whose resolver knows New York."""
    store = InMemoryScheduleStore()
    tool = ScheduleTaskTool(
        store,
        FixedClock(),
        tasks_enabled=True,
        max_active=32,
        zones=ZoneContext(resolver=_RESOLVER),
        item_id_factory=_ids(),
    )
    return tool, store


def test_the_creation_spec_advertises_in_zone() -> None:
    tool, _ = _tool()
    properties = tool.spec.parameters["properties"]
    assert "in_zone" in properties
    assert "America/New_York" in properties["in_zone"]["description"]
    assert "in_zone" in tool.spec.description


async def test_creation_fires_persists_and_renders_a_per_rule_zone() -> None:
    tool, store = _zoned_tool()
    result = await tool.invoke(
        _call(
            {
                "kind": "reminder",
                "text": "standup",
                "at_time": "09:00",
                "in_zone": "America/New_York",
            }
        )
    )
    assert not result.is_error
    assert result.content == (
        "scheduled reminder item-1: due 2026-07-12T09:00:00-04:00, "
        "every day at 09:00 (America/New_York)"
    )
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.due_at == datetime(2026, 7, 12, 13, 0, 0, tzinfo=UTC)
    assert loaded.rule == CalendarRule(hour=9, minute=0, zone=_NEW_YORK)


async def test_listing_renders_a_per_rule_zone_in_its_own_zone() -> None:
    tool, store = _zoned_tool()
    await tool.invoke(
        _call(
            {
                "kind": "reminder",
                "text": "standup",
                "at_time": "09:00",
                "in_zone": "America/New_York",
            }
        )
    )
    listing = await ListScheduledTool(store).invoke(_call({}))
    assert not listing.is_error
    assert "due 2026-07-12T09:00:00-04:00, every day at 09:00 (America/New_York)" in listing.content


async def test_creation_rejects_an_unknown_in_zone() -> None:
    tool, store = _zoned_tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "x", "at_time": "09:00", "in_zone": "Mars/Olympus"})
    )
    assert result.is_error
    assert "no known timezone" in result.content
    assert not await store.list_active()


async def test_creation_rejects_a_non_string_in_zone() -> None:
    tool, _ = _zoned_tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "x", "at_time": "09:00", "in_zone": 5})
    )
    assert result.is_error
    assert "'in_zone' must be an IANA timezone name" in result.content


async def test_creation_rejects_in_zone_without_at_time() -> None:
    tool, _ = _zoned_tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "x", "in_seconds": 60, "in_zone": "America/New_York"})
    )
    assert result.is_error
    assert (
        result.content == "'in_zone' names the zone of an 'at_time' wall clock; give 'at_time' too"
    )


def test_the_edit_spec_advertises_in_zone() -> None:
    spec = EditScheduledTool(InMemoryScheduleStore(), FixedClock()).spec
    assert "in_zone" in spec.parameters["properties"]
    assert "in_zone" in spec.description


async def test_edit_sets_a_per_rule_zone_and_renders_it() -> None:
    tool, store = _zoned_tool()
    await tool.invoke(_call({"kind": "reminder", "text": "standup", "in_seconds": 60}))
    edit = EditScheduledTool(store, FixedClock(), zones=ZoneContext(resolver=_RESOLVER))
    result = await edit.invoke(
        _edit_call({"id": "item-1", "at_time": "09:00", "in_zone": "America/New_York"})
    )
    assert not result.is_error
    assert result.content == "edited item-1: now due 2026-07-12T09:00:00-04:00"
    loaded = await store.get("item-1")
    assert loaded is not None
    assert loaded.rule == CalendarRule(hour=9, minute=0, zone=_NEW_YORK)


async def test_edit_rejects_an_unknown_in_zone() -> None:
    tool, store = _zoned_tool()
    await tool.invoke(_call({"kind": "reminder", "text": "standup", "in_seconds": 60}))
    edit = EditScheduledTool(store, FixedClock(), zones=ZoneContext(resolver=_RESOLVER))
    result = await edit.invoke(
        _edit_call({"id": "item-1", "at_time": "09:00", "in_zone": "Mars/Olympus"})
    )
    assert result.is_error
    assert "no known timezone" in result.content
