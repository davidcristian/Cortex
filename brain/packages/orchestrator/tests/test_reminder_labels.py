from datetime import UTC, datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from grpc import aio

from cortex_core import (
    CalendarRule,
    DisplayZone,
    EchoInferenceBackend,
    FireOutcome,
    InMemoryScheduleStore,
    InMemorySessionStore,
    ScheduledItem,
    ScheduleKind,
    SystemClock,
    TurnEngine,
)
from cortex_orchestrator import RpcPorts, RpcServerConfig, ScheduleConfig, create_server
from cortex_orchestrator.reminders import ReminderView, reminder_to_proto
from cortex_orchestrator.schedule_builders import build_reminder_view
from cortex_seam import BrainServiceStub, ListDueRemindersReply, ListDueRemindersRequest

_DUE = datetime(2026, 10, 26, 7, 0, 0, tzinfo=UTC)
_BERLIN = DisplayZone(name="Europe/Berlin", tz=ZoneInfo("Europe/Berlin"))
_POLL = timedelta(seconds=5)


class _Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def _view(now: datetime, poll: timedelta = _POLL) -> ReminderView:
    return ReminderView(zone=_BERLIN, poll=poll, clock=_Clock(now))


async def _fired(
    fired_at: datetime,
    *,
    kind: ScheduleKind = ScheduleKind.REMINDER,
    every: timedelta | None = None,
    rule: CalendarRule | None = None,
    started_at: datetime | None = None,
) -> tuple[InMemoryScheduleStore, ScheduledItem]:
    """One item due at ``_DUE``, claimed and fired at ``fired_at`` the way the ticker does."""
    store = InMemoryScheduleStore()
    item = ScheduledItem(
        id="r1",
        kind=kind,
        text="check the oven",
        session_id="chat-1",
        due_at=_DUE,
        created_at=_DUE - timedelta(hours=1),
        every=every,
        rule=rule,
    )
    await store.add(item)
    (claim,) = await store.claim_due(fired_at, lease=timedelta(minutes=5), limit=8)
    next_due = _DUE + every if every is not None else None
    outcome = FireOutcome(
        fired_at=fired_at,
        next_due=next_due,
        deliverable=True,
        outcome="done",
        started_at=started_at,
    )
    assert await store.finish(claim, outcome) is True
    (held,) = await store.deliverable()
    return store, held


async def test_a_late_fire_lists_its_due_time_over_the_wire() -> None:
    fired_at = _DUE + timedelta(hours=5)
    schedules, _ = await _fired(fired_at)
    session_store = InMemorySessionStore()
    engine = TurnEngine(session_store, EchoInferenceBackend(), SystemClock())
    ports = RpcPorts(schedules=schedules, reminder_view=_view(fired_at + timedelta(minutes=2)))
    server, port = create_server(
        RpcServerConfig(host="127.0.0.1", port=0),
        lambda _confirmer, _progress: engine,
        session_store,
        ports,
    )
    await server.start()
    try:
        async with aio.insecure_channel(f"127.0.0.1:{port}") as channel:
            method = BrainServiceStub(channel).ListDueReminders  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            reply = cast("ListDueRemindersReply", await method(ListDueRemindersRequest()))
    finally:
        await server.stop(grace=None)
    (reminder,) = reply.reminders
    assert reminder.due_label == "due 08:00"


async def test_the_day_is_counted_from_the_list_and_not_the_fire() -> None:
    fired_at = _DUE + timedelta(hours=5)
    _, held = await _fired(fired_at)
    assert reminder_to_proto(held, _view(fired_at)).due_label == "due 08:00"
    tomorrow = fired_at + timedelta(days=1)
    assert reminder_to_proto(held, _view(tomorrow)).due_label == "due 08:00 yesterday"


async def test_a_fire_within_the_margin_has_no_label() -> None:
    fired_at = _DUE + timedelta(seconds=40)
    _, held = await _fired(fired_at)
    assert reminder_to_proto(held, _view(fired_at)).due_label == ""


async def test_the_margin_widens_with_the_ticker_poll() -> None:
    fired_at = _DUE + timedelta(minutes=4)
    _, held = await _fired(fired_at)
    slow = timedelta(minutes=2)
    assert reminder_to_proto(held, _view(fired_at, slow)).due_label == ""
    assert reminder_to_proto(held, _view(fired_at)).due_label == "due 08:00"


async def test_a_recurring_fire_names_the_occurrence_that_fired() -> None:
    fired_at = _DUE + timedelta(hours=5)
    _, held = await _fired(fired_at, every=timedelta(hours=1))
    assert held.due_at == _DUE + timedelta(hours=1)
    assert reminder_to_proto(held, _view(fired_at)).due_label == "due 08:00"


async def test_a_calendar_rule_names_the_time_in_its_own_zone() -> None:
    tokyo = DisplayZone(name="Asia/Tokyo", tz=ZoneInfo("Asia/Tokyo"))
    fired_at = _DUE + timedelta(hours=2)
    _, held = await _fired(fired_at, rule=CalendarRule(hour=16, minute=0, zone=tokyo))
    assert reminder_to_proto(held, _view(fired_at)).due_label == "due 16:00"


async def test_a_task_that_started_late_is_labelled_from_its_start() -> None:
    started_at = _DUE + timedelta(hours=5)
    fired_at = started_at + timedelta(minutes=3)
    _, held = await _fired(fired_at, kind=ScheduleKind.TASK, started_at=started_at)
    assert reminder_to_proto(held, _view(fired_at)).due_label == "due 08:00"


async def test_a_long_task_run_that_started_on_time_has_no_label() -> None:
    fired_at = _DUE + timedelta(minutes=30)
    _, held = await _fired(fired_at, kind=ScheduleKind.TASK, started_at=_DUE)
    assert reminder_to_proto(held, _view(fired_at)).due_label == ""


async def test_a_task_outcome_stored_without_its_start_has_no_label() -> None:
    fired_at = _DUE + timedelta(hours=5)
    _, held = await _fired(fired_at, kind=ScheduleKind.TASK)
    assert reminder_to_proto(held, _view(fired_at)).due_label == ""


def test_a_fire_stored_without_its_due_time_has_no_label() -> None:
    fired_at = _DUE + timedelta(hours=5)
    held = ScheduledItem(
        id="r1",
        kind=ScheduleKind.REMINDER,
        text="check the oven",
        session_id="chat-1",
        due_at=_DUE,
        created_at=_DUE,
        deliverable_since=fired_at,
    )
    assert reminder_to_proto(held, _view(fired_at)).due_label == ""


def test_the_view_reads_the_zone_and_poll_the_ticker_fires_by() -> None:
    clock = _Clock(_DUE)
    view = build_reminder_view(ScheduleConfig(tz="Europe/Berlin", poll_s=90.0), clock)
    assert view.zone.name == "Europe/Berlin"
    assert view.poll == timedelta(seconds=90)
    assert view.clock is clock
