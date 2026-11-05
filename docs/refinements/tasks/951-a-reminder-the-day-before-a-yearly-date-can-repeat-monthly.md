# A reminder the day before a yearly date can repeat monthly

**Status:** done 2026-11-05
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

A request for a reminder before a yearly date can make the cortex call `schedule_task` with a
monthly rule (`at_time` with `on_month_days`) instead of a yearly one (`on_dates`). On 2026-11-05,
5 of 15 draws over a birthday, an anniversary and a renewal stored a monthly rule, 9 stored it
yearly and 1 stored a one-time reminder; the two requests that really are monthly stored a
monthly rule in all 4 draws ([readings](../../readings/schedule-yearly-dates.md#baseline-2026-11-05)).
The reply does not always show it: two of the five monthly draws replied "every year".

## What to do

The rows and the rule are in the readings, and item 1 of the rule fired, so the next step is the
typed check its item 2 describes, not a sentence in the tool description.

1. Write a typed reader of the person's message that finds a day of a named month ("12 May",
   "3 September", "20 March") and no monthly wording ("every month", "each month", "monthly",
   "of the month"). Write the near misses as tests before the code: "Remind me on the 11th of
   every month, starting in May, to pay rent", "Every month on the 25th, remind me to check my
   bank statement", "the 1st of each month from March on".
2. In a turn where the reader matches, refuse a `schedule_task` call with `on_month_days` once,
   beside the `UNASKED` refusal in `dispatch_round.py`, with a correction saying the person named
   a yearly date and that `on_dates` takes it as MM-DD. Any monthly wording keeps the call.
3. Replay every recorded message in the scheduling readings through the reader and list each
   match, then draw the same rows on a candidate and ship it only under item 2 of the rule.

## History

- 2026-10-30: filed from the candidate draws of the side-effect tools check (R-901).
- 2026-11-05: corrected with a baseline of 19 draws: 5 of 15 yearly-date requests stored a monthly
  rule, and the claim that the reply always names the stored rule failed twice. The typed check
  did not fit the slot's time box and is this task's next step.
- 2026-11-05: done. `names_yearly_date` (`schedule_yearly.py`) reads the message, and the first
  `schedule_task` call with `on_month_days` in a turn it matches is refused as `YEARLY_DATE`. On
  the same rows 0 of 15 Y draws stored a monthly rule, 13 of 15 stored a yearly one and all 4
  monthly draws kept theirs, so item 2 of the rule passed. A reply calling a stored monthly rule
  yearly now gets `MONTHLY_STORED_NOTE`. One refused draw stored the wrong month (R-981 filed).
