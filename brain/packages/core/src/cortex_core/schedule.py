"""Schedule value types + the pure recurrence math (ADR-0025): durable, swap-safe time."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum

from cortex_core.schedule_calendar import CalendarRule, next_calendar_due
from cortex_core.schedule_time import DisplayZone


class ScheduleKind(Enum):
    """What firing an item does: deliver text to the user, or run an autonomous subagent."""

    REMINDER = "reminder"
    TASK = "task"


class ScheduleStatus(Enum):
    """The store-side lifecycle: armed, claimed by a fire pass, or terminally fired."""

    PENDING = "pending"
    FIRING = "firing"
    DONE = "done"


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        msg = f"{name} must be timezone-aware"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScheduledItem:
    """One durable schedule: what to do, when (and how often), and its provenance."""

    id: str
    kind: ScheduleKind
    text: str
    session_id: str
    due_at: datetime
    created_at: datetime
    every: timedelta | None = None
    rule: CalendarRule | None = None
    anchor: datetime | None = None
    model: str = ""
    tainted: bool = False
    status: ScheduleStatus = ScheduleStatus.PENDING
    deliverable_since: datetime | None = None
    last_outcome: str | None = None

    def __post_init__(self) -> None:
        _require_aware("ScheduledItem.due_at", self.due_at)
        _require_aware("ScheduledItem.created_at", self.created_at)
        if self.deliverable_since is not None:
            _require_aware("ScheduledItem.deliverable_since", self.deliverable_since)
        if self.anchor is not None:
            _require_aware("ScheduledItem.anchor", self.anchor)
        if self.every is not None and self.every <= timedelta(0):
            msg = "ScheduledItem.every must be a positive interval"
            raise ValueError(msg)
        if self.every is not None and self.rule is not None:
            msg = "ScheduledItem takes an interval or a calendar rule, never both"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScheduleClaim:
    """One claimed fire: the item as of the claim (status FIRING) plus the fencing token.

    ``finish``/``release`` apply only under the token the store minted for the *current*
    claim; a stale claimant's call is a no-op ``False`` (ADR-0025 decision 1).
    """

    item: ScheduledItem
    token: str


@dataclass(frozen=True, slots=True)
class FireOutcome:
    """What one fire did, for ``ScheduleStore.finish`` to persist atomically."""

    fired_at: datetime
    next_due: datetime | None
    deliverable: bool
    outcome: str | None = None
    tainted: bool = False

    def __post_init__(self) -> None:
        _require_aware("FireOutcome.fired_at", self.fired_at)
        if self.next_due is not None:
            _require_aware("FireOutcome.next_due", self.next_due)


@dataclass(frozen=True, slots=True)
class ScheduleEdit:
    """A validated in-place change to a stored schedule: new text and/or recurrence (edit addendum).
    """

    text: str | None = None
    every: timedelta | None = None
    set_every: bool = False
    tainted: bool = False

    def __post_init__(self) -> None:
        if self.every is not None and self.every <= timedelta(0):
            msg = "ScheduleEdit.every must be a positive interval"
            raise ValueError(msg)


def apply_edit(item: ScheduledItem, edit: ScheduleEdit) -> ScheduledItem:
    """Return ``item`` with ``edit`` applied: new text/recurrence, taint OR'd, timing kept."""
    return replace(
        item,
        text=edit.text if edit.text is not None else item.text,
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


def recurrence_base(item: ScheduledItem) -> datetime:
    """The recurrence grid origin the ticker re-arms from: the ``anchor`` if set, else ``due_at``.
    """
    return item.anchor if item.anchor is not None else item.due_at


def next_occurrence(item: ScheduledItem, now: datetime, zone: DisplayZone) -> datetime | None:
    """Where ``item`` re-arms after firing at ``now``, or ``None`` when it is terminal."""
    if item.rule is not None:
        return next_calendar_due(item.rule, now, zone)
    return next_due(recurrence_base(item), item.every, now)


def next_due(due_at: datetime, every: timedelta | None, now: datetime) -> datetime | None:
    """The next anchored occurrence strictly after ``now``, or None for a one-shot."""
    if every is None:
        return None
    if every <= timedelta(0):
        msg = "next_due requires a positive 'every' interval"
        raise ValueError(msg)
    try:
        behind = now - due_at
        if behind < timedelta(0):
            return due_at + every
        return due_at + (behind // every + 1) * every
    except OverflowError:
        return None
