# A refused monthly call can be stored on the wrong month

**Status:** done 2026-11-06
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

After the `YEARLY_DATE` refusal (`schedule_yearly.py`), the cortex makes the call again with
`on_dates`. For "Our wedding anniversary is on 3 September. Remind me a week before." one of
seven refused draws stored `on_dates` ["09-27"]: the day of the refused monthly call (27) in the
anniversary's month (September), where a week before 3 September is 08-27. The reminder then
fires once a year on the wrong day. No baseline yearly draw stored a wrong date
([readings](../../readings/schedule-yearly-dates.md#the-yearly-date-refusal-2026-11-05)).

## What to do

1. Done: the rows (three month-before requests and a same-month near miss) and the rule are in
   [schedule-yearly-month-before.md](../../readings/schedule-yearly-month-before.md), with the
   baseline drawn on 2026-11-06.
2. Done: `schedule_offset.py` reads the yearly date and the offset before it from the message and
   refuses, once per turn, a `schedule_task` call whose `on_dates` entry is another date, naming
   the wanted MM-DD; drawn on the same rows on 2026-11-06.

## History

- 2026-11-05: filed from the candidate draws of R-951.
- 2026-11-05: checked the refused draw's two calls in the brain log. The refused call held
  `on_month_days` [27] and no month, and the retry took September from the anniversary. The
  refusal text names only "a day of a named month" and its example maps a date to itself
  ('05-11' for 11 May), so it gives the model no month for a reminder day in the month before.
  Whether a rewording changes 1 in 7 needs this task's rows; not drawn yet, so the task stays open.
- 2026-11-06: checked the code again: a retry runs when its `on_month_days` equal the refused
  call's (`same_month_days`), and nothing typed reads an `on_dates` entry against the message.
  Wrote the month-before rows (B01 to B03, near miss N01) and the rule, then drew the baseline
  on the stack brain: 11 of 12 B draws stored the wanted date, 0 of 12 the wrong month, 1 a
  one-time reminder; 3 B draws were refused first, each retry storing the right month. A null
  result under the rule, so the behaviour is left alone; the next row is eight draws per request.
- 2026-11-06: drew the next row (eight per request, 29 draws): 2 of 22 B draws stored the wrong
  month (both B03, 01-31, both refused first), so item 2 of the rule applies and the typed check of
  the retry's `on_dates` entry is the next step, not drawn tonight. Two B03 draws stored the
  birthday itself, another wrong date the same check reads; its rows are in the readings.
- 2026-11-06: built the typed check (`schedule_offset.py`): the wanted MM-DD is computed from the
  named date and the offset, a `schedule_task` call whose `on_dates` holds another date is refused
  once per turn with the wanted date named, and the next call runs. Near misses (no offset, "a week
  after", no yearly date, two dates, two offsets, a one-time request) are tests. On the candidate,
  0 of 12 B draws stored a wrong month, 11 of 12 the right date, all 4 N01 draws 05-13, and 0 of 12
  day-before draws the date itself; the check fired once, on a 02-26 retry whose next call stored
  02-28. Shipped; closed.
