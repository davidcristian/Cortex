# A daily item stored for tomorrow first fires today

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0065](../../adr/ADR-0065-wall-clock-schedule-times.md)
**Verified:** 2026-11-10

A message asking for one time tomorrow, sent together with a second request, was stored three
times through `at_time` alone: a daily item whose first fire is today. On 2026-11-10, at about
04:50 local, `Read notes.txt and remind me tomorrow at 9 of the first item in it.`, `Remember that
I park on level 3 and remind me tomorrow at 9 to move the car.` and the French `Souviens-toi que le
code de mon casier est 4417 et rappelle-moi demain à 9h de vider le casier.` each stored
`at_time: "09:00"`, due 09:00 the same day and every day after. Each reply said "tomorrow at 9:00
AM" or `demain à 9h00`, and `DAILY_STORED_NOTE` showed, which is true but names no first day, so
the person is not told that the first reminder comes at 09:00 the same day
([readings](../../readings/overlay-compound-request-flows.md)).

Counts from that night: 3 of 10 compound turns asking for tomorrow at 9 that made a call stored a
daily item, and 0 of 2 single requests (`Remind me tomorrow at 9 to move the car.`). Two compound
turns asking for `at 18:00` with no day were also stored daily, 2 of 2, and both replies or notes
said so.

## What to do

1. Write the pass rule before any draw: a reply over a daily item whose first fire is earlier
   than the day the person's message names ends with a note naming that first fire.
2. Compare two remedies. A brain-appended note naming the first fire's date and time when it is
   today and the message names `tomorrow` or a later day, read by the existing day readers; or a
   change to `DAILY_STORED_NOTE` that always names the first fire. Other-language wording stays a
   proposal here.
3. Draw the three recorded messages at least five times each on the chosen build, with a single
   request control, and count stored shapes and notes.

## History

- 2026-11-10: filed from the compound request flows on the shared stack.
