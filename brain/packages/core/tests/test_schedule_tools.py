"""The three schedule built-ins: parsing, bounds, trust, and the tainted-task refusal
(ADR-0025)."""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from cortex_core import (
    TAINTED_TASK_MSG,
    CancelScheduledTool,
    CompositeToolRegistry,
    FireOutcome,
    InMemoryScheduleStore,
    ListScheduledTool,
    RecordingAuditSink,
    ScheduledItem,
    ScheduleKind,
    ScheduleStoreError,
    ScheduleTaskTool,
    ToolCall,
    ToolDispatcher,
    Trust,
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


def _call(arguments: dict[str, Any], *, tainted: bool = False) -> ToolCall:
    return ToolCall(id="c1", name="schedule_task", arguments=arguments, tainted=tainted)


class FailingStore(InMemoryScheduleStore):
    """Scripts a down store: the port methods the tools touch raise ScheduleStoreError."""

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


# --- the spec: clock-bearing, honest about task wiring -------------------------------------


def test_spec_carries_the_current_utc_time() -> None:
    tool, _ = _tool()
    assert "2026-07-12T12:00:00+00:00" in tool.spec.description


def test_spec_advertises_tasks_and_model_only_when_wired() -> None:
    enabled, _ = _tool(tasks_enabled=True)
    properties = dict(enabled.spec.parameters["properties"])
    assert properties["kind"]["enum"] == ["reminder", "task"]
    assert "model" in properties
    disabled, _ = _tool(tasks_enabled=False)
    properties = dict(disabled.spec.parameters["properties"])
    assert properties["kind"]["enum"] == ["reminder"]
    assert "model" not in properties
    assert not disabled.spec.gated  # ungated by default; CORTEX_TOOLS_GATED is the backstop


# --- creation: happy paths -------------------------------------------------------------------


async def test_schedules_a_one_shot_reminder_at_an_absolute_time() -> None:
    tool, store = _tool()
    result = await tool.invoke(
        _call({"kind": "reminder", "text": "stretch", "at": "2026-07-12T18:00:00+02:00"})
    )
    assert not result.is_error
    assert result.trust is Trust.TRUSTED
    assert "scheduled reminder item-1: due 2026-07-12T16:00:00+00:00" in result.content
    assert "stretch" not in result.content  # never echoes the stored text
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
    assert "recurring every 3600s" in result.content
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
    assert len(item.id) == 36  # a uuid4, from the default factory


# --- creation bounds ---------------------------------------------------------------------------


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
    """End to end: the dispatcher's stamp (not the model's forged flag) hits the refusal."""
    tool, _ = _tool()
    sink = RecordingAuditSink()
    dispatcher = ToolDispatcher(CompositeToolRegistry([tool]), sink, FixedClock())
    call = ToolCall(
        id="c1",
        name="schedule_task",
        arguments={"kind": "task", "text": "run this", "in_seconds": 60},
    )
    result = await dispatcher.dispatch(call, tainted=True)
    assert result.is_error
    assert result.content == TAINTED_TASK_MSG
    (record,) = sink.records  # the refusal is audited like any dispatch
    assert record.ok is False


async def test_the_active_items_cap_bounds_creation() -> None:
    tool, _ = _tool(max_active=1)
    first = await tool.invoke(_call({"kind": "reminder", "text": "a", "in_seconds": 60}))
    assert not first.is_error
    second = await tool.invoke(_call({"kind": "reminder", "text": "b", "in_seconds": 60}))
    assert second.is_error
    assert "the schedule is full (1 active items)" in second.content


# --- creation: validation matrix ---------------------------------------------------------------


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
        ({"kind": "reminder", "text": "x", "at": "2026-07-12T18:00:00"}, "UTC offset"),
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


# --- the store down ----------------------------------------------------------------------------


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


# --- listing: content and trust ---------------------------------------------------------------


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


# --- cancel ------------------------------------------------------------------------------------


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
