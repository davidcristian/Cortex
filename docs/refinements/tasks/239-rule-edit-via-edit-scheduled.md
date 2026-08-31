# Setting and retiming a rule via edit_scheduled

**Status:** landed 2026-07-14
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded in the [ADR-0025 rule-edit addendum](../../adr/ADR-0025-scheduling-reminders.md).
`at_time`/`on_days` join the edit verb, so a rule can be authored on any item and retimed in place
instead of cancelled and recreated; the reverse direction (rule to interval, or `0` to stop) already
shipped. Behind the unchanged `ScheduleStore` port with no codec, record, or migration change. Three
corrections to this entry's own framing, each found by reading the code rather than the entry: (1)
it is **not** just "a `ScheduleEdit` that carries the third case", because a rule is its own grid,
so setting one must **re-derive `due_at`**, bending the edit verb's deliberate "the next due time is
never moved" rule for the one shape whose invariant requires it (an interval, anchored on `due_at`,
is untouched). (2) The derivation needs a clock and a zone that `apply_edit` and both stores
deliberately lack, so the rule and its first occurrence ride the edit as one frozen `RuleChange`,
derived at the verb the way creation already derives its own first fire; binding the pair is also
what keeps `due_at` from becoming the general knob this verb refused. (3) A naive `ZADD` of the
moved due time would have been a **live defect**: a fired-but-undelivered reminder is `DONE`, `DONE`
items are never on the due index today, and `ack` leans on that by deleting a `DONE` record without
a `zrem`, so the item would have re-entered the claim path (whose staleness re-check only guards
`PENDING`) and fired twice. `apply_snooze` already answered exactly this, so the rule branch borrows
its behavior and its write set rather than inventing one. `schedule.py` hit the 300-line cap and
split, keeping the value types and the recurrence math while `schedule_transitions.py` took the pure
transitions both stores apply. CI-gated at 100% with all ten new guards mutation-proven (each
reverted individually makes the new tests fail), across the pure transitions, the verb's parse
matrix, and the store contract suite on fake and fakeredis alike. No codec change, so no live-Redis
run is owed beyond the contract suite's own leg.
