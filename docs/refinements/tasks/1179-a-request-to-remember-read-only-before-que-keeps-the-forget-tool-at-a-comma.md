# A request to remember read only before que keeps the forget tool at a comma

**Status:** done 2026-11-14
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unrequested` refuses the forget tool on a request to remember in French, German, Spanish
or Romanian that a comma or colon follows, then one statement of a fact
([readings](../../readings/forget-refusal-statement-other-languages.md)). `asks_kept_fact_other`
(`memory_request.py`) finds the request with
`_REMEMBER_OTHER`, which reads `recuerda`, `retiens` and `reține` only before `que`, `că`, a
demonstrative or, for the first two, a colon. So `Recuerda, mi código es 4242.`,
`Retiens, mon code est 4242.` and `Reține, codul meu e 4242.` keep the tool, as the German comma
form did before the change, while `Recuerda: mi código es 4242.` and `Retiens : mon code est
4242.` refuse it. No draw of the three was taken.

`_REMEMBER_OTHER` also decides `asks_kept`, `asks_kept_other`, `asks_kept_alone` and the request
position `_asks_not_kept` reads, so a wider verb form there changes which tools a turn withholds
(`set_volume`, `schedule_task`) as well as this refusal.

## What to do

1. Write the three forms and their near misses (`Recuerda, borra mi código.`, `Retiens, ne garde
   pas mon code.`) as tests.
2. Read the comma form only where it opens one statement (the `_FACT_AFTER` lookahead), not in
   `_REMEMBER_OTHER`, unless a replay of every recorded string through the four readers above
   shows no other change.
3. Replay the recorded strings and draw the Spanish store turn and its forget.

## History

- 2026-11-13: filed when the four language statement was read at a comma or colon.
- 2026-11-14: done. `asks_kept_fact_other` (now `fact_request.py`) also reads `recuerda`,
  `retiens` and `reține` alone before a comma when one fact stated with a copula follows,
  without widening `REMEMBER_OTHER`, so the readers that share it are unchanged. `Retiens, oublie
  mon code.` and `Recuerda, borra mi código.` keep the tool. The Spanish store turn stored the row
  in 4 of 4 draws with no forget call ([readings](../../readings/forget-refusal-stated-fact.md)).
