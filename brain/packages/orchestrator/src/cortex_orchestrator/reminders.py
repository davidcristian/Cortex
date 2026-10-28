"""Reminder pull-delivery views: the ScheduleStore onto the wire, benign when off."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from cortex_core import (
    UTC_DISPLAY,
    Clock,
    DisplayZone,
    ScheduledItem,
    ScheduleKind,
    ScheduleStore,
    SystemClock,
    due_phrase,
    fire_stamp,
    is_late_fire,
    stamp_instant,
)
from cortex_seam import AckReminderReply, DueReminder, ListDueRemindersReply


@dataclass(frozen=True, slots=True)
class ReminderView:
    """What a card's due label reads: the ticker's zone and poll, and the clock it is shown by."""

    zone: DisplayZone = UTC_DISPLAY
    poll: timedelta = timedelta(0)
    clock: Clock = field(default_factory=SystemClock)


def _due_label(item: ScheduledItem, fired_at: datetime, view: ReminderView) -> str:
    """'due 09:00' for a late reminder fire, with its day counted from now; else ''."""
    due_at = item.deliverable_due_at
    # A task's fire time is when its run ended, so a long run would read as a late fire.
    if item.kind is not ScheduleKind.REMINDER or due_at is None:
        return ""
    if not is_late_fire(due_at, fired_at, view.poll):
        return ""
    return due_phrase(item.rule, due_at, view.clock.now(), view.zone)


def reminder_to_proto(item: ScheduledItem, view: ReminderView) -> DueReminder:
    """Map a deliverable `ScheduledItem` to the wire `DueReminder`."""
    fired_at = item.deliverable_since if item.deliverable_since is not None else item.due_at
    body = item.text
    if item.kind is ScheduleKind.TASK and item.last_outcome is not None:
        body = item.last_outcome
    return DueReminder(
        reminder_id=item.id,
        text=body,
        fired_at_unix_ms=fire_stamp(fired_at),
        recurring=item.every is not None or item.rule is not None,
        tainted=item.tainted,
        session_id=item.session_id,
        due_label=_due_label(item, fired_at, view),
    )


async def list_due_reminders(
    schedules: ScheduleStore | None, view: ReminderView
) -> ListDueRemindersReply:
    """Fired-but-undelivered reminders, oldest-fired-first; empty when scheduling is off."""
    if schedules is None:
        return ListDueRemindersReply()
    items = await schedules.deliverable()
    return ListDueRemindersReply(reminders=[reminder_to_proto(item, view) for item in items])


async def ack_reminder(
    schedules: ScheduleStore | None, reminder_id: str, fired_at_unix_ms: int
) -> AckReminderReply:
    """Mark one fire delivered; `acked=false` for unknown/not-deliverable/scheduling-off."""
    if schedules is None:
        return AckReminderReply(acked=False)
    # 0 is the proto3 default a body built before the field sends, and acks whichever fire is
    # held, as that body always did.
    if fired_at_unix_ms == 0:
        return AckReminderReply(acked=await schedules.ack(reminder_id, fired_at=None))
    try:
        fired_at = stamp_instant(fired_at_unix_ms)
    except OverflowError:
        return AckReminderReply(acked=False)
    return AckReminderReply(acked=await schedules.ack(reminder_id, fired_at=fired_at))
