# A duration after réglé pour reads as the stored time of day

**Status:** done 2026-11-08
**Area:** cross-cutting
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

`names_time_of_day` in `schedule_claim.py` reads an h hour after `réglé pour`, `programmé pour`,
`prévu pour`, `noté pour` and the like as a clock time. French also writes a duration that way:
"réglé pour 2h" can mean two hours from now. A reply that names only such a duration is then read
as naming the stored time, so `STORED_TIME_NOTE` is left out and the person never sees the clock
time the reminder holds. This is the direction that matters: the note is missing.

Reproduction, unit level (`SCRATCH/slot21/probe_regle.py`), `names_time_of_day(reply)` is `True`
for each:

- "Le minuteur est réglé pour 2h."
- "C'est réglé pour 2h : je te préviens quand elles sont passées."
- "Le rappel est programmé pour 2h à partir de maintenant."
- "Le minuteur est réglé pour 2 h 30."
- "C'est noté pour 1h."

It is also `True` for the clock times it should read: "Le rappel est réglé pour 17h30." and "Le
rappel est réglé pour 2h du matin."

## What to do

1. Count the recorded French schedule replies in
   `docs/readings/overlay-language-and-locale-flows.md` that write `pour` before an h hour, and
   how many of them mean a duration.
2. Write the five replies above as near misses first. Then read an h hour after the `pour` words
   only when it cannot be a duration: an hour from 13 to 23, or a word that names a part of the
   day (`du matin`, `de l'après-midi`, `du soir`) after it. Leave `2h`, `2 h 30` and `pour 2h à
   partir de maintenant` unread, so a reply naming only one of them gets the note, which repeats
   at worst a time the reply wrote.

## History

- 2026-11-07: filed from the third audit of the night's changes, reproduced at unit level.
- 2026-11-08: Done. The premise held: all five replies read as a clock time. After the `pour`
  words `names_time_of_day` now reads an h hour only from 13 to 23 or before `du matin`,
  `du soir` or `de l'après-midi`, so the five get the note. No recorded French schedule reply
  writes a `pour` word before an h hour, and the replay changed 0 of 16,186 distinct texts
  ([readings](../../readings/schedule-day-only-times.md)).
