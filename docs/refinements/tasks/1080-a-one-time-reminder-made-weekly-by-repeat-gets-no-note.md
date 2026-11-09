# A one-time reminder made weekly by repeat gets no note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-09

`once_kept` in `schedule_edit_at.py` refuses `at_time` on a one-time item unless `repeat` is true,
and its result says to call again with `repeat` set to true if the person asked for a repeat. An
edit with `at_time`, a day selector and `repeat: true` makes the item a weekly rule, and
`daily_after` in `schedule_daily.py` drops the id on a day selector, so no closing note says the
item now repeats; only the daily form gets `DAILY_STORED_NOTE`
([readings](../../readings/overlay-corrections-flows.md#audit-probes-of-the-move-and-the-refusal-2026-11-09)).
No draw has measured how often the model sets `repeat` unasked.

## What to do

1. Draw `Move my dentist reminder to Tuesday at 15:00.` over a one-time item, with the count of
   calls that set `repeat` unasked written as the row before the first draw.
2. Add a brain-appended note over an edit that turns a one-time item into a weekly rule, the way
   `DAILY_STORED_NOTE` closes the daily form; its wording in the other four languages is a
   proposal for the maintainer.

## History

- 2026-11-09: filed from the audit probes of the one-time refusal.
