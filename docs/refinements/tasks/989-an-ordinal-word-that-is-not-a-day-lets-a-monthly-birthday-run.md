# An ordinal word that is not a day lets a monthly birthday run

**Status:** done 2026-11-06
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

`bare_days` in `schedule_yearly.py` reads an ordinal word after "the" or "every" as a month day,
also when a noun follows it. When that number equals the day of the named date, a monthly call on
that day is not refused. Against the code of 2026-11-05, `monthly_for_yearly` returns `False` for
each of these with `on_month_days` set to the date's day:

| Message | `bare_days` | Day |
| --- | --- | --- |
| Remind me of Leo's birthday on 1 July, it's the first one he has at school | {1} | 1 |
| Remind me of Tom's birthday on 2 March, every second year we throw a party | {2} | 2 |
| Remind me of our anniversary on 3 June, the third reminder is the one I need | {3} | 3 |

The digit-only reader refused all three. The miss needs the ordinal's number to equal the date's
day, and a reply that calls the stored rule yearly still gets the monthly note.

## What to do

1. Write near-miss rows first: these three, plus "pay rent on the first" and "on the second, pay
   the gym" beside a birthday, whose monthly calls must keep running.
2. Read an ordinal word as a day only when no noun follows it, and replay every message in
   [schedule-yearly-dates](../../readings/schedule-yearly-dates.md) through both readers, listing
   each change. Keep the reader failing toward running the call.

## History

- 2026-11-05: filed by the third audit of the ordinal word reader, with the table above as its
  reproduction.
- 2026-11-06: done. `bare_days` reads an ordinal word after "the" or "every" as a day only when the
  end of the message, a punctuation mark or a closed-class word follows it, so the three messages
  above are refused and the two near misses run; the rows, the replay and the stack draws are in
  [schedule-yearly-ordinals](../../readings/schedule-yearly-ordinals.md).
