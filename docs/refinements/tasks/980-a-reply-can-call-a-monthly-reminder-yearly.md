# A reply can call a monthly reminder yearly

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-05

"My car insurance renews every year on 20 March; remind me the day before." made the cortex store
a reminder on the 19th of every month (`on_month_days` [19]) in two of five draws, and both
replies said it repeats yearly: "every year on March 19th at 9:00 AM" and "on March 19th of every
year at 9:00 AM" ([readings](../../readings/schedule-yearly-dates.md#baseline-2026-11-05)). The
person reads a yearly reminder and gets one every month.

## What to do

1. Write rows and a rule into the readings before any change: requests whose stored rule and reply
   can differ (a yearly date, a weekday, a month day), scored by comparing the stored record with
   the repeat the reply names.
2. Prefer a note the brain appends after a typed check of the reply, as `schedule_claim.py` does:
   when a successful `schedule_task` call in the turn stored `on_month_days` and the reply says
   "every year" or "each year", append the rule the tool stored. Write near misses as tests first,
   such as a reply naming both a monthly reminder and a yearly date.

## History

- 2026-11-05: filed from the baseline draws of R-951, whose fix removes these two records but not
  a reply that names another repeat than the one stored.
