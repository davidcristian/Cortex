"""The built-ins under a non-UTC display zone (ADR-0025 display addendum).

The default-zone behavior of every tool is covered in ``test_schedule_tools.py``; this module
asserts only what the knob changes: the two spec strings the model reads, the three rendered
outputs, and the offset-less ``at`` reading as zone-local end to end. Stored due times are
checked to stay UTC instants, since the knob is display-only.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from cortex_core import (
    DisplayZone,
    InMemoryScheduleStore,
    ListScheduledTool,
    ScheduledItem,
    ScheduleKind,
    ScheduleTaskTool,
    SnoozeScheduledTool,
    ToolCall,
    TurnStamp,
    ZoneContext,
)

# +03:00 in July; the transitions themselves are exercised in test_schedule_time.py.
_ZONE = DisplayZone(name="Europe/Bucharest", tz=ZoneInfo("Europe/Bucharest"))
_ZONES = ZoneContext(default=_ZONE)
_NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return _NOW


def _call(arguments: dict[str, Any]) -> ToolCall:
    return ToolCall(
        id="c1",
        name="schedule_task",
        arguments=arguments,
        stamp=TurnStamp(session_id="", tainted=False),
    )


def _schedule_tool(store: InMemoryScheduleStore) -> ScheduleTaskTool:
    return ScheduleTaskTool(
        store,
        FixedClock(),
        tasks_enabled=True,
        max_active=32,
        zones=_ZONES,
        item_id_factory=lambda: "item-1",
    )


def test_the_creation_spec_names_the_zone_and_renders_local() -> None:
    description = _schedule_tool(InMemoryScheduleStore()).spec.description
    assert "The current date-time is 2026-07-12T15:00:00+03:00 (Europe/Bucharest)." in description
    assert "UTC" not in description  # the label must not outlive the values it describes


def test_the_at_parameter_advertises_the_fold() -> None:
    spec = _schedule_tool(InMemoryScheduleStore()).spec
    assert (
        "read as Europe/Bucharest local time" in spec.parameters["properties"]["at"]["description"]
    )


def test_the_listing_spec_names_the_zone() -> None:
    description = ListScheduledTool(InMemoryScheduleStore(), zone=_ZONE).spec.description
    assert "due time (Europe/Bucharest)" in description


async def test_creation_confirms_in_local_time_but_stores_the_utc_instant() -> None:
    store = InMemoryScheduleStore()
    result = await _schedule_tool(store).invoke(
        _call({"kind": "reminder", "text": "tea", "in_seconds": 3600})
    )
    assert not result.is_error
    assert "due 2026-07-12T16:00:00+03:00" in result.content
    stored = (await store.list_active())[0]
    assert stored.due_at == datetime(2026, 7, 12, 13, 0, 0, tzinfo=UTC)


async def test_an_offset_less_at_reads_as_zone_local() -> None:
    """18:00 written bare means 18:00 in Bucharest (15:00 UTC), not 18:00 UTC."""
    store = InMemoryScheduleStore()
    result = await _schedule_tool(store).invoke(
        _call({"kind": "reminder", "text": "call", "at": "2026-07-12T18:00:00"})
    )
    assert not result.is_error
    assert "due 2026-07-12T18:00:00+03:00" in result.content
    assert (await store.list_active())[0].due_at == datetime(2026, 7, 12, 15, 0, 0, tzinfo=UTC)


async def test_an_explicit_offset_still_wins() -> None:
    """The model can always be unambiguous; an offset is honored, never re-read as local."""
    store = InMemoryScheduleStore()
    result = await _schedule_tool(store).invoke(
        _call({"kind": "reminder", "text": "call", "at": "2026-07-12T18:00:00+00:00"})
    )
    assert not result.is_error
    assert "due 2026-07-12T21:00:00+03:00" in result.content
    assert (await store.list_active())[0].due_at == datetime(2026, 7, 12, 18, 0, 0, tzinfo=UTC)


async def test_the_listing_renders_local() -> None:
    store = InMemoryScheduleStore()
    await store.add(
        ScheduledItem(
            id="item-1",
            kind=ScheduleKind.REMINDER,
            text="tea",
            session_id="",
            due_at=datetime(2026, 7, 12, 13, 0, 0, tzinfo=UTC),
            created_at=_NOW,
        )
    )
    result = await ListScheduledTool(store, zone=_ZONE).invoke(
        ToolCall(id="c2", name="list_scheduled", arguments={})
    )
    assert "due 2026-07-12T16:00:00+03:00" in result.content


async def test_the_snooze_confirmation_renders_local() -> None:
    store = InMemoryScheduleStore()
    await store.add(
        ScheduledItem(
            id="item-1",
            kind=ScheduleKind.REMINDER,
            text="tea",
            session_id="",
            due_at=_NOW + timedelta(minutes=5),
            created_at=_NOW,
        )
    )
    result = await SnoozeScheduledTool(store, FixedClock(), zone=_ZONE).invoke(
        ToolCall(id="c3", name="snooze_scheduled", arguments={"id": "item-1", "for_seconds": 3600})
    )
    assert not result.is_error
    assert "now due 2026-07-12T16:00:00+03:00" in result.content
