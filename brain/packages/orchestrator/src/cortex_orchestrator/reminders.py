"""Reminder pull-delivery views (ADR-0025): the ScheduleStore onto the wire, benign when off."""

from datetime import datetime

from cortex_core import ScheduledItem, ScheduleKind, ScheduleStore
from cortex_seam import AckReminderReply, DueReminder, ListDueRemindersReply


def _unix_ms(moment: datetime) -> int:
    """A tz-aware instant as unix-milliseconds (the seam's timestamp form, ADR-0021)."""
    return int(moment.timestamp() * 1000)


def reminder_to_proto(item: ScheduledItem) -> DueReminder:
    """Map a deliverable `ScheduledItem` to the wire `DueReminder` (ADR-0025)."""
    fired_at = item.deliverable_since if item.deliverable_since is not None else item.due_at
    body = item.text
    if item.kind is ScheduleKind.TASK and item.last_outcome is not None:
        body = item.last_outcome
    return DueReminder(
        reminder_id=item.id,
        text=body,
        fired_at_unix_ms=_unix_ms(fired_at),
        recurring=item.every is not None,
        tainted=item.tainted,
        session_id=item.session_id,
    )


async def list_due_reminders(schedules: ScheduleStore | None) -> ListDueRemindersReply:
    """Fired-but-undelivered reminders, oldest-fired-first; empty when scheduling is off."""
    if schedules is None:
        return ListDueRemindersReply()
    items = await schedules.deliverable()
    return ListDueRemindersReply(reminders=[reminder_to_proto(item) for item in items])


async def ack_reminder(schedules: ScheduleStore | None, reminder_id: str) -> AckReminderReply:
    """Mark one reminder delivered; `acked=false` for unknown/not-deliverable/scheduling-off.

    Idempotent by construction (the store's `ack` no-ops `False` on a cleared slot), so a
    retried ack is harmless, which is why this narrow write may ride the read-heavy seam.
    """
    if schedules is None:
        return AckReminderReply(acked=False)
    return AckReminderReply(acked=await schedules.ack(reminder_id))
