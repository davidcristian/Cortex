"""Schedule value types + the pure recurrence math (ADR-0025): durable, swap-safe time.

Pure data and pure arithmetic, no I/O and no ``ports`` import. That lets ``ports.py`` depend on
these without a cycle, exactly as ``subagents.py`` is depended on. A schedule *outlives every
model swap and restart* (the one hard rule), so every ``ScheduledItem`` lives behind the
``ScheduleStore`` port and every timestamp is timezone-aware (a naive time on a durable record
is ambiguous). ``ScheduleClaim``/``FireOutcome`` carry the fenced claim→finish protocol: a
claim's ``token`` is minted per claim, and a ``finish``/``release`` presenting a stale token is
a no-op, so a fire that outran its lease cannot clobber the re-claim's newer state (ADR-0025
decision 1). Named ``schedule``/``ScheduleTicker`` throughout, never "Scheduler", because that word
means resource *admission* here (``SubagentScheduler``).
"""

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
    """The store-side lifecycle: armed, claimed by a fire pass, or terminally fired.

    There is no CANCELLED state. ``cancel`` deletes the record outright (it can never
    surface again), and DONE persists only while a fired one-shot reminder awaits delivery
    (terminal records never accumulate, per ADR-0025 decision 1).
    """

    PENDING = "pending"
    FIRING = "firing"
    DONE = "done"


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        msg = f"{name} must be timezone-aware"
        raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ScheduledItem:
    """One durable schedule: what to do, when (and how often), and its provenance.

    ``text`` is the reminder text or the task instruction; ``session_id`` is the origin chat
    (``""`` until a turn-context stamp exists, per the ADR-0025 deferral). ``every`` makes the
    item recurring (a positive interval, enforced here; the 60 s floor is tool-boundary
    policy). ``rule`` is the *other* recurrence shape, a wall-clock calendar rule that follows
    daylight saving where an interval would drift against it (ADR-0025 calendar addendum);
    **at most one of the two is set**, so "how does this item recur?" always has one answer
    and ``next_occurrence`` never has to reconcile a conflict. ``anchor`` pins the *interval*
    grid origin separately from ``due_at`` (the next fire): it is ``None`` until an occurrence
    snooze moves one fire off the grid, after which ``recurrence_base`` reads it so the series
    resumes its original cadence instead of drifting (ADR-0025 occurrence-snooze addendum). A
    calendar item needs no anchor, because its rule *is* the grid. ``model`` is the task's
    roster hint (``""`` = the
    default; ADR-0017 resolution still rules at fire time). ``tainted`` starts as the creating
    turn's taint (the dispatcher's stamp, ADR-0018) and is OR'd with each fire's outcome taint
    at ``finish``, and it decides listing trust and rides both delivery wire paths.
    ``deliverable_since`` marks a fired reminder awaiting delivery/ack; ``last_outcome`` is the
    last task fire's result.
    """

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
    """What one fire did, for ``ScheduleStore.finish`` to persist atomically.

    ``next_due=None`` is terminal (DONE and deleted unless deliverable); otherwise the item
    re-arms PENDING at ``next_due``. ``deliverable`` stamps ``deliverable_since=fired_at``
    (a reminder awaiting delivery). ``tainted`` is fire-time taint, meaning the fire consumed
    untrusted content, OR'd onto the item so a clean-created task cannot launder what its
    subagent read into a trusted listing (ADR-0025 decision 1).
    """

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

    ``text=None`` leaves the text unchanged; ``every`` is applied only when ``set_every`` is
    True (``every=None`` then clears recurrence, making the item a one-shot), so the three
    cases unchanged / set / clear are all expressible without a sentinel interval. ``tainted``
    is the editing turn's taint, OR'd onto the item and never clearing it, because a retext can
    carry untrusted content forward. At least one of a text or a recurrence change is present
    by construction (the verb refuses a no-op edit); ``due_at`` is deliberately not editable, so
    the next occurrence stays anchored and only future re-arms take a new cadence.
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
    """Return ``item`` with ``edit`` applied: new text/recurrence, taint OR'd, timing kept.

    Both store implementations apply an edit through this one pure function, so the fake and
    the Redis adapter change an item identically (the ports-before-adapters guarantee). ``due_at``
    stays put on purpose (re-recur changes the cadence of future re-arms, not the next fire), and
    taint is monotone: OR'd, never cleared (ADR-0025 edit addendum).

    Setting an interval **clears any calendar rule**, because the item holds at most one
    recurrence shape: an edit that set ``every`` on a calendar item would otherwise have to
    fail, and silently keeping the rule while reporting the new interval would be worse. The
    ``0`` sentinel therefore stops repeating whichever shape the item had.
    """
    return replace(
        item,
        text=edit.text if edit.text is not None else item.text,
        every=edit.every if edit.set_every else item.every,
        rule=None if edit.set_every else item.rule,
        tainted=item.tainted or edit.tainted,
    )


def apply_snooze(item: ScheduledItem, until: datetime) -> ScheduledItem:
    """Return ``item`` postponed to ``until``: PENDING, off the deliverable index, grid kept.

    Both stores snooze through this one pure function (the ``apply_edit`` precedent), so the
    fake and the Redis adapter move an item identically. A recurring item keeps its original
    cadence: only the single next occurrence moves to ``until``, while ``anchor`` pins the grid
    origin (its existing anchor, or the pre-snooze ``due_at`` when this is the first snooze) so
    the fire after the snooze re-arms on ``origin + k*every`` rather than ``until + every``. A
    one-shot has no grid, so its anchor stays ``None`` (ADR-0025 occurrence-snooze addendum).

    A **calendar** item needs no anchor and gets none: its rule is the grid, so
    ``next_occurrence`` reads the rule rather than ``due_at`` and the series returns to its
    wall-clock cadence after the snoozed fire for free (ADR-0025 calendar addendum).
    """
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

    An unsnoozed item's ``due_at`` is always on its own grid, so ``anchor is None`` reduces to
    the previous behavior; a snoozed recurring item carries the original origin here so
    ``next_due`` returns the item to its cadence rather than drifting by the snooze offset.
    """
    return item.anchor if item.anchor is not None else item.due_at


def next_occurrence(item: ScheduledItem, now: datetime, zone: DisplayZone) -> datetime | None:
    """Where ``item`` re-arms after firing at ``now``, or ``None`` when it is terminal.

    The one entry point the ticker calls, so which recurrence shape an item carries is decided
    in the pure core rather than at the firing edge. A calendar rule answers from the wall
    clock in ``zone`` (drift-free across daylight saving, and self-anchoring: the rule is its
    own grid, so a snoozed calendar item returns to its cadence without an ``anchor``); an
    interval keeps the anchored ``next_due`` arithmetic, snooze grid and coalescing included.
    A one-shot has neither and is terminal.
    """
    if item.rule is not None:
        return next_calendar_due(item.rule, now, zone)
    return next_due(recurrence_base(item), item.every, now)


def next_due(due_at: datetime, every: timedelta | None, now: datetime) -> datetime | None:
    """The next anchored occurrence strictly after ``now``, or None for a one-shot.

    Occurrences are ``due_at + k * every`` (integer ``k >= 1``): missed occurrences while
    the brain was down **coalesce** into the single fire that just happened. The next
    re-arm is in the future, one catch-up fire instead of a flood (ADR-0025 decision 2).
    ``every`` must be positive (the ``ScheduledItem`` invariant; enforced here too so the
    pure function is total on its own terms). An occurrence past ``datetime.max`` cannot
    be scheduled, so the recurrence **ends** (None, since terminal beats a fire that can never
    persist its re-arm and lease-cycles forever; post-review hardening).
    """
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
