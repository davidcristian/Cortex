# A reply that names a bare hour such as 18h gets the stored time note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-07

`names_time_of_day` (`schedule_claim.py`) reads `17h30`, `9 h 15` and `9 Uhr`, and not a bare hour
with `h` and no minutes. On 2026-11-07 the `cortexn15` stack answered
`Souviens-toi que ma sœur s'appelle Claire et rappelle-moi demain à 18h de l'appeler.` with a
`schedule_task` call stored at 18:00 and the reply `J'ai bien programmé un rappel pour demain à
18h`, and `limit_notes` appended `STORED_TIME_NOTE` under it, although the reply names the stored
time ([readings](../../readings/overlay-language-and-locale-flows.md#8-requests-to-remember-in-four-more-languages)).

Reproduction: send the message above in a new chat with every card approved.

## What to do

1. Write near-miss replies first as tests: a duration (`dans 2h`, `pendant 2h`, `en 2 h`,
   `j'ai dormi 2h`, `in 2h`), and the forms to read (`à 18h`, `vers 9h`, `um 18h`, `a las 18h`).
   A reply read wrongly as naming a time loses the note, so the reader fails toward showing it.
2. Replay every recorded reply of the night through the old and new reader and list each change.

## History

- 2026-11-07: filed from the requests to remember in four more languages on the shared stack.
