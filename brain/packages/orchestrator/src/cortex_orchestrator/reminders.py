"""Reminder pull-delivery views: the ScheduleStore onto the wire, benign when off."""

from cortex_core import ScheduledItem, ScheduleKind, ScheduleStore, fire_stamp, stamp_instant
from cortex_seam import AckReminderReply, DueReminder, ListDueRemindersReply


def reminder_to_proto(item: ScheduledItem) -> DueReminder:
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
    )


async def list_due_reminders(schedules: ScheduleStore | None) -> ListDueRemindersReply:
    """Fired-but-undelivered reminders, oldest-fired-first; empty when scheduling is off."""
    if schedules is None:
        return ListDueRemindersReply()
    items = await schedules.deliverable()
    return ListDueRemindersReply(reminders=[reminder_to_proto(item) for item in items])


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
