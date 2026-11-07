# A one-time reminder in German is stored every day

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-07

`Erinnere mich um 17:30 Uhr an die Wäsche.` asks for one reminder. On 2026-11-07 the `cortexn15`
stack (gemma-4-12B at context 16,384, llama-server build `b12169-3ed7284f2`) called
`schedule_task` with `at_time` 17:30 and no day selector, which repeats every day, and the reply
said only `ich habe dich für 17:30 Uhr an die Wäsche erinnert`. The stored record has the rule
`{"hour": 17, "minute": 30, "days": [0..6]}`
([readings](../../readings/overlay-language-and-locale-flows.md)).

The result of such a call ends with `_DAILY_NOTE` (`schedule_tools.py`), a note the model reads:
it says the item repeats every day and asks for an `edit_scheduled` call with `every_seconds` 0
when the person asked for one time. The English `Remind me at 17h30 to take the bins out.` made
the same daily call in the same run and then followed the note with an `edit_scheduled` call; the
German turn did not. One row of each, so whether the language changes the rate is not known.

Reproduction: in a new chat send `Erinnere mich um 17:30 Uhr an die Wäsche.` and read the
`cortex:schedule:*` record for that chat.

## What to do

1. Write rows into a readings record before any draw: one-time requests with a time and no day in
   English, German, French, Spanish and Romanian, three draws each, with the stored rule and the
   reply read per draw. A draw passes when it stores one time, or stores a daily repeat and the
   reply says it repeats.
2. If the daily store without a word in the reply occurs, try the brain-appended form first: a
   ledger field set from a successful daily `schedule_task` result, read by `limit_notes` in
   `closing_notes.py`, which appends a note when the reply names no repeat. The reply reader is
   English-first, so its rows need replies in each language.

## History

- 2026-11-07: filed from the language and locale flows on the shared stack.
