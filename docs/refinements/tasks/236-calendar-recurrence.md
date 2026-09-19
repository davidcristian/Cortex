# Calendar recurrence

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)

Decided in [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md) decision 2. This was the
recurrence half of the display-timezone entry, and it cost what that entry predicted: a new
recurrence shape, not a setting. A pure `CalendarRule(hour, minute, days)` in the new
`cortex_core/schedule_calendar.py` sits beside `ScheduledItem.every` (at most one of the two,
checked in `__post_init__`), `next_calendar_due` walks the rule's own weekdays resolving each
candidate through `DisplayZone.resolve`, and one new `next_occurrence(item, now, zone)` is the
single entry point the ticker calls. To the model that is `at_time: "09:00"` plus an optional
`on_days: ["mon", ...]`, mutually exclusive with `at`, `in_seconds` and `every_seconds`, with the
first fire derived from the rule, so the model is never asked to keep two fields consistent. Cron
was rejected: a parser dependency, and a syntax a small model gets subtly wrong in ways that still
validate.

The daylight-saving policy is inherited rather than invented: an occurrence inside a gap fires just
after the gap (late, never skipped) and a repeated hour fires once, exactly as a naive `at` already
resolved. Two corrections to what this entry originally said: `anchor` is not where the grid origin
belongs, because a rule is its own grid, so a snoozed calendar item needs no anchor and the snooze
code was untouched; and the store needed no change, only the codec (an additive `rule` key read
with `.get`, following the `anchor` precedent, no version bump, no migration). The ticker takes the
configured zone on `TickerSettings` rather than a seventh constructor argument.

Tested at 100% coverage with all seven new checks proven by mutation, and daylight-saving cases
against real `ZoneInfo` zones on both sides of UTC. The contract suite covers the new field on the
fake and on fakeredis, and because the codec changed, two real-stack runs back it: the live-Redis
contract run, and an end-to-end run inside `cortex-brain:latest` that created "every weekday at
09:00" in `Europe/Bucharest`, fired it, and rescheduled on the same wall-clock hour.

It also forced the `cortex_core/__init__.py` split (see [tools-mcp.md](../index.md#tools-mcp)) and
split `schedule_verb_args.py` out of `schedule_args.py` at the line cap. The day-of-month, yearly
and per-rule-timezone halves each have their own entry. Remaining: cron expressions, if a rule this
shape cannot express ever turns up.

## History

- 2026-07-14: Recorded under ADR-0065 decision 2. The backlog index warns that an entry's own cost
  estimate is a hypothesis rather than a finding, and cites the display-timezone entry this
  recurrence half was bundled into as one of four whose estimate misled planning, the recurrence
  change being the part no existing field could express. That warning has no date of its own, so
  this line records the date of the change.
