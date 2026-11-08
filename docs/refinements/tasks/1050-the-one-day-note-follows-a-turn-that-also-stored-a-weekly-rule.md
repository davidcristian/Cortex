# The one day note follows a turn that also stored a weekly rule

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`run_round` in `dispatch_round.py` sets `TaintLedger.once_after_weekly` when a `schedule_task`
call stores a one-time item after the weekly reader refused a call, and the flag never clears, so
`limit_notes` closes the reply with `ONCE_STORED_NOTE` ("The reminder set in this turn is for one
day only") even when the same turn stored a weekly rule after the refusal. The weekly refusal is
sent once per turn, so a second `on_days` call runs. The note then says one day only while a
weekly rule is stored, which is false.

Reproduction, unit level (the `_taint` helper in `test_schedule_weekly_once.py`, message
`Remind me Tuesday at 8 to stretch, keep it going.`): calls `[weekly, weekly, once]` and
`[weekly, once, weekly]` both end with `once_after_weekly` True. The first form needs a second
reminder in the message, the second a retry that kept `on_days`; neither is counted in a draw yet.

## What to do

1. Count how often a retry after the weekly refusal keeps `on_days`, from the recorded draws in
   [the readings](../../readings/schedule-weekly-false-refusal.md).
2. Show the note only when no item stored after the refusal repeats. A ledger field that a
   repeating store after the refusal sets also crosses the handoff, so `HandoffRecord`, its
   snapshot and the codec each need the field, as `once_after_weekly` has.

## History

- 2026-11-08: filed by the second audit of the night's changes, from a unit probe.
