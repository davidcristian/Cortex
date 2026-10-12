"""How a scheduled item reads in a listing and on a confirmation card."""

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


def describe_item(item: ScheduledItem, zone: DisplayZone) -> str:
    """One listing line per item; the stored text comes last, with its provenance marked."""
    recurring = recurrence_phrase(item)
    fired = ", fired awaiting delivery" if item.deliverable_since is not None else ""
    firing = ", firing now" if item.status is ScheduleStatus.FIRING else ""
    tainted = ", from untrusted content" if item.tainted else ""
    marks = f"{recurring}{firing}{fired}{tainted}"
    due = effective_zone(item.rule, zone).render(item.due_at)
    line = f"[{item.id}] {item.kind.value} due {due}{marks}: {item.text}"
    if item.last_outcome is not None:
        line += f"\n    last outcome: {item.last_outcome}"
    return line
