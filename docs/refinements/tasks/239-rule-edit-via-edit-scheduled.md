# Setting and retiming a rule via edit_scheduled

**Status:** done 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Decided in [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 9. `at_time` and
`on_days` join the edit verb, so a rule can be written on any item and retimed in place instead of
being cancelled and recreated. The reverse direction (rule to interval, or `0` to stop) already
worked. Behind the unchanged `ScheduleStore` port, with no codec, record or migration change.

Three corrections to what this entry originally said, each found by reading the code:

- It is not just a `ScheduleEdit` with a third case. A rule is its own grid, so setting one must
  recompute `due_at`, which bends the edit verb's rule that the next due time is never moved. An
  interval, which is anchored on `due_at`, is untouched.
- The computation needs a clock and a zone that `apply_edit` and both stores deliberately lack, so
  the rule and its first occurrence are passed together as one frozen `RuleChange`, computed at the
  verb the way creation already computes its own first fire. Keeping the pair together is also what
  stops `due_at` from becoming the general setting this verb refused to offer.
- A plain `ZADD` of the moved due time would have been a live defect. A fired but undelivered
  reminder is `DONE`, `DONE` items are never on the due index, and `ack` relies on that by deleting
  a `DONE` record without a `zrem`, so the item would have re-entered the claim path, whose
  staleness re-check only covers `PENDING`, and fired twice. `apply_snooze` already solved this, so
  the rule branch reuses its behavior and its write set.

`schedule.py` hit the 300-line cap and split, keeping the value types and the recurrence math while
`schedule_transitions.py` took the pure transitions both stores apply. Tested at 100% coverage with
all ten new checks proven by mutation (each reverted on its own makes the new tests fail), across
the pure transitions, the verb's parse matrix and the store contract suite on the fake and on
fakeredis. No codec change, so no live-Redis run is owed beyond the contract suite's own.
