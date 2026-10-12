"""How a scheduled item reads in a listing and on a confirmation card."""

from datetime import date, datetime

from cortex_core.schedule import ScheduledItem, ScheduleStatus
from cortex_core.schedule_calendar import CalendarRule
from cortex_core.schedule_time import DisplayZone


def effective_zone(rule: CalendarRule | None, default_zone: DisplayZone) -> DisplayZone:
    """The zone a calendar item's due time renders in: the rule's own if it has one, else the
    deployment default.
    """
    return rule.zone if rule is not None and rule.zone is not None else default_zone


def recurrence_phrase(item: ScheduledItem) -> str:
    """How the item repeats, as a leading-comma phrase; empty for a one-shot."""
    if item.rule is not None:
        return f", {item.rule.describe()}"
    if item.every is not None:
        return f", every {int(item.every.total_seconds())}s"
    return ""


def now_sentence(zone: DisplayZone, now: datetime) -> str:
    """The sentence that tells the model the current date-time and the zone it is written in."""
    return f"The current date-time is {zone.render(now)} ({zone.name})."


def _local_day(moment: datetime, zone: DisplayZone) -> date:
    return moment.astimezone(zone.tz).date()


def relative_day(due: datetime, now: datetime, zone: DisplayZone) -> str:
    """The due time's calendar day counted from now's, both in ``zone``, such as 'tomorrow'."""
    days = (_local_day(due, zone) - _local_day(now, zone)).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    return f"in {days} days" if days > 1 else f"{-days} days ago"


def describe_item(item: ScheduledItem, zone: DisplayZone, now: datetime | None = None) -> str:
    """One listing line per item; the stored text comes last, with its provenance marked.

    With ``now``, the due time also names its day counted from today.
    """
    recurring = recurrence_phrase(item)
    fired = ", fired awaiting delivery" if item.deliverable_since is not None else ""
    firing = ", firing now" if item.status is ScheduleStatus.FIRING else ""
    tainted = ", from untrusted content" if item.tainted else ""
    marks = f"{recurring}{firing}{fired}{tainted}"
    shown = effective_zone(item.rule, zone)
    due = shown.render(item.due_at)
    if now is not None:
        due += f" ({relative_day(item.due_at, now, shown)})"
    line = f"[{item.id}] {item.kind.value} due {due}{marks}: {item.text}"
    if item.last_outcome is not None:
        line += f"\n    last outcome: {item.last_outcome}"
    return line
