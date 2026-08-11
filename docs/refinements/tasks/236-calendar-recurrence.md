# Calendar recurrence

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 calendar
addendum](../../adr/ADR-0025-scheduling-reminders.md). The recurrence half of the original
entry, and the cost this entry predicted was right: a new recurrence *shape*, not a knob.
A pure `CalendarRule(hour, minute, days)` in the new `cortex_core/schedule_calendar.py`
sits **beside** `ScheduledItem.every` (at most one of the two, enforced in `__post_init__`),
`next_calendar_due` walks the rule's own weekdays resolving each candidate through the
existing `DisplayZone.resolve`, and one new `next_occurrence(item, now, zone)` is the single
entry point the ticker calls. Model-facing, that is `at_time: "09:00"` plus optional
`on_days: ["mon", ...]`, mutually exclusive with `at`/`in_seconds`/`every_seconds`, with the
first fire **derived from the rule** so no two-field consistency invariant reaches the model.
Cron was rejected (a parser dependency, and a syntax a small model gets subtly wrong in ways
that still validate). The DST policy the entry asked for is **inherited rather than
invented**: a gap occurrence fires just past the gap (late, never skipped) and a fall-back
repeat fires once, exactly as a naive `at` already resolved. Two corrections to this entry's
own framing: the `anchor` field is **not** the home for the grid origin, because a rule *is*
its own grid, so a snoozed calendar item needs no anchor and the snooze machinery was
untouched; and the store needed no change at all, only the codec (an additive `rule` key read
with `.get`, the `anchor` precedent, no version bump, no migration). The ticker takes the
configured zone on `TickerSettings` rather than a seventh constructor argument. CI-gated at
100% with all seven new guards mutation-proven, DST cases against real `ZoneInfo` zones on
both sides of UTC; the contract suite covers the new field on fake and fakeredis alike, and
because the codec changed, two real-stack runs back it: the live-Redis contract leg (itself
mutation-proven to exercise the new key) and an end-to-end pass inside `cortex-brain:latest`
that created "every weekday at 09:00" in `Europe/Bucharest`, fired it, and re-armed on the
same wall-clock hour.
It also forced the `cortex_core/__init__.py` barrel split (see [tools-mcp.md](../index.md#tools-mcp)) and split
`schedule_verb_args.py` out of `schedule_args.py` at the cap. The day-of-month and yearly
halves both landed, in their own entries below; the **per-rule timezone** landed 2026-07-15
(its own entry below). Remaining: **cron expressions** if a rule this shape cannot express
ever turns up.

## Trail

- 2026-07-14: Recorded under the ADR-0025 calendar addendum. The backlog index's opening warning,
  that an entry's own cost estimate is a hypothesis rather than a finding, cites the
  display-timezone entry this recurrence half was bundled into as one of the four whose estimate
  misled planning, the recurrence change being the part no existing field could express. That
  warning carries no date of its own in the index, so the date on this line is the addendum's
  rather than the audit's.
