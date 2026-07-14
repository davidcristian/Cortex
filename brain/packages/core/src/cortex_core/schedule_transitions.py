"""The pure in-place schedule transitions both stores apply (ADR-0025 edit/snooze addenda).

Split from ``schedule.py`` at the 300-line cap, along the line that module's own docstring
already draws: it holds the durable value types and the recurrence math the ticker reads,
while a *transition* is what a user-facing verb does to a stored item. Each function here is
total, pure, and shared: the in-memory fake and the Redis adapter both route their ``edit`` and
``snooze`` through these, so the two stores mutate an item identically and the fenced-versus-
plain difference between them is only the concurrency wrapper (the ports-before-adapters
guarantee). Nothing here reads a clock or a zone, which is why a rule change arrives with its
occurrence already derived rather than computed on the spot.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from cortex_core.schedule import ScheduledItem, ScheduleStatus, require_aware
from cortex_core.schedule_calendar import CalendarRule


@dataclass(frozen=True, slots=True)
class RuleChange:
    """A calendar rule an edit sets, together with the first occurrence it implies.

    The two travel as one value because the second is *derived from* the first: a calendar
    item's ``due_at`` is an occurrence of its own rule by construction, so a rule change that
    left ``due_at`` behind would name a fire the rule does not. Deriving it needs a clock and a
    zone, which the pure ``apply_edit`` and both stores deliberately lack, so the derivation
    happens once at the tool boundary (creation's own calendar branch already works this way).
    Binding the pair also keeps ``due_at`` from becoming a general "set the due time" knob,
    which the edit verb refused: it is reachable only as some rule's own next occurrence
    (ADR-0025 rule-edit addendum).
    """

    rule: CalendarRule
    due_at: datetime

    def __post_init__(self) -> None:
        require_aware("RuleChange.due_at", self.due_at)


@dataclass(frozen=True, slots=True)
class ScheduleEdit:
    """A validated in-place change to a stored schedule: new text and/or recurrence (edit addendum).

    ``text=None`` leaves the text unchanged; ``every`` is applied only when ``set_every`` is
    True (``every=None`` then clears recurrence, making the item a one-shot), so the three
    cases unchanged / set / clear are all expressible without a sentinel interval. ``rule`` is
    the fourth case, switching the item onto a wall-clock grid; it is **mutually exclusive with
    ``set_every``**, which keeps the item's one-shape invariant true at the boundary rather than
    re-checked downstream. ``tainted``
    is the editing turn's taint, OR'd onto the item and never clearing it, because a retext can
    carry untrusted content forward. At least one change is present by construction (the verb
    refuses a no-op edit); ``due_at`` is editable *only* as a rule's derived occurrence, so an
    interval re-recur still leaves the next fire anchored where it was.
    """

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
    """Return ``item`` with ``edit`` applied: new text and/or recurrence, taint OR'd.

    Both store implementations apply an edit through this one pure function, so the fake and
    the Redis adapter change an item identically (the ports-before-adapters guarantee), and
    taint is monotone: OR'd, never cleared (ADR-0025 edit addendum).

    Setting an interval **clears any calendar rule**, because the item holds at most one
    recurrence shape: an edit that set ``every`` on a calendar item would otherwise have to
    fail, and silently keeping the rule while reporting the new interval would be worse. The
    ``0`` sentinel therefore stops repeating whichever shape the item had. On that branch
    ``due_at`` stays put, so re-recur changes the cadence of future re-arms and never the fire
    already armed.

    Setting a **rule** is the one branch that moves the timing, and it re-arms the item exactly
    as ``apply_snooze`` re-arms a fired reminder: PENDING at the rule's next occurrence with
    ``deliverable_since`` cleared, so a fired-but-undelivered reminder fires fresh instead of
    re-delivering stale, and (decisively) a DONE item never lands on the due index, where the
    claim path would fire it a second time. ``anchor`` is dropped with it: it pins an *interval*
    grid, and a rule is its own grid (ADR-0025 rule-edit addendum).
    """
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
