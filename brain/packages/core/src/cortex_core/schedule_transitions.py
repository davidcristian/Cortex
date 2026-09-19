"""The pure in-place schedule transitions both stores apply."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from cortex_core.schedule import ScheduledItem, ScheduleStatus, require_aware
from cortex_core.schedule_calendar import CalendarRule


@dataclass(frozen=True, slots=True)
class RuleChange:
    """A calendar rule an edit sets, together with the first occurrence it implies."""

    rule: CalendarRule
    due_at: datetime

    def __post_init__(self) -> None:
        require_aware("RuleChange.due_at", self.due_at)


@dataclass(frozen=True, slots=True)
class ScheduleEdit:
    """A validated in-place change to a stored schedule: new text and/or recurrence (decision 9)."""

    text: str | None = None
    every: timedelta | None = None
    set_every: bool = False
    rule: RuleChange | None = None
    tainted: bool = False

    def __post_init__(self) -> None:
        if self.every is not None and self.every <= timedelta(0):
            msg = "ScheduleEdit.every must be a positive interval"
            raise ValueError(msg)
        if self.rule is not None and self.set_every:
            msg = "ScheduleEdit takes an interval change or a calendar rule, never both"
            raise ValueError(msg)


def apply_edit(item: ScheduledItem, edit: ScheduleEdit) -> ScheduledItem:
    """Return ``item`` with ``edit`` applied: new text and/or recurrence, taint OR'd."""
    text = edit.text if edit.text is not None else item.text
    if edit.rule is not None:
        return replace(
            item,
            text=text,
            every=None,
            rule=edit.rule.rule,
            due_at=edit.rule.due_at,
            anchor=None,
            status=ScheduleStatus.PENDING,
            deliverable_since=None,
            tainted=item.tainted or edit.tainted,
        )
    return replace(
        item,
        text=text,
        every=edit.every if edit.set_every else item.every,
        rule=None if edit.set_every else item.rule,
        tainted=item.tainted or edit.tainted,
    )


def apply_snooze(item: ScheduledItem, until: datetime) -> ScheduledItem:
    """Return ``item`` postponed to ``until``: PENDING, off the deliverable index, grid kept."""
    anchor = item.anchor
    if item.every is not None and anchor is None:
        anchor = item.due_at
    return replace(
        item,
        status=ScheduleStatus.PENDING,
        due_at=until,
        deliverable_since=None,
        anchor=anchor,
    )


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MILLISECOND = timedelta(milliseconds=1)


def fire_stamp(moment: datetime) -> int:
    """``moment`` as whole unix-milliseconds, the grain the pull wire names a fire at."""
    # Integer arithmetic rather than ``timestamp() * 1000``, whose float product can come out a
    # millisecond low: the overlay echoes this stamp back and the two must compare equal.
    return (moment - _EPOCH) // _MILLISECOND


def stamp_instant(stamp: int) -> datetime:
    """The instant a ``fire_stamp`` names, exactly (``fire_stamp(stamp_instant(n)) == n``)."""
    return _EPOCH + stamp * _MILLISECOND


def acks_fire(item: ScheduledItem, fired_at: datetime | None) -> bool:
    """Whether an ack naming the fire at ``fired_at`` clears ``item``'s delivery slot."""
    since = item.deliverable_since
    if since is None:
        return False
    return fired_at is None or fire_stamp(since) == fire_stamp(fired_at)
