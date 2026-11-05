# An edited repeat with a later first day fires before it

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-05

`schedule_task` with `starting` stores the rule's first match on or after that day as `due_at`,
and the record holds no separate start. `edit_scheduled` with `at_time` computes the rule's next
occurrence from now (`_parse_edit_rule` in `schedule_verb_args.py`) and takes no `starting`. So
"make the gas bill reminder 10:00" on 2026-11-05, for an item stored on 2026-11-05 with `starting`
2027-06-15 and `on_month_days` [15], moves its first fire to 2026-11-15.

## What to do

1. Accept `starting` on `edit_scheduled` with the same parsing as `schedule_task`
   (`_repeat_after` in `schedule_args.py`).
2. Decide whether an edit without `starting` keeps a later first day, which needs the record to
   hold the start (a stored form change that must still load records written without it), or
   whether the edit's result names the new first fire so the reply can say it.

## History

- 2026-11-05: filed when `schedule_task` gained `starting`
  ([readings](../../readings/schedule-start-dates.md)).
