# A request to remember a fact with no copula keeps the forget tool beside an older row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

`forget_unrequested` (`forget_unrequested.py`) keeps the forget tool on a request to remember in
French, German, Spanish or Romanian whose fact holds no copula, such as `Merk dir, dass mein Hund
Bello heißt.`, `Recuerda que tienes cita a las 9.` and `Ține minte că sora mea vine mâine.`
([task 1197](1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)).
Into an empty store the cortex called the tool unasked in 11 of 24 draws of these three forms,
each call named the new fact, and no row was lost
([readings](../../readings/forget-refusal-stated-fact.md#the-store-turn-of-four-forms-the-rule-keeps)).
With an older row stored that holds the same words, such a call can match it and its approved
card deletes it. On a new value of one lowercase word, which the tree refuses, a rule that kept
the tool let an unasked call delete the old row in 3 of 32 draws
([readings](../../readings/forget-refusal-stated-fact.md#a-new-value-with-the-old-one-already-stored)).
These three forms have not been drawn with an older row stored.

## What to do

1. Write the rule first, then draw each of the three forms with an older row of the same fact
   stored (`Merk dir, dass mein Hund Rex heißt.` before the Bello message, and so on), 8 draws
   each, every card approved, and count the calls, the old row deleted and the new fact stored.
2. Only if an old row is deleted unasked, build the stated fact shape that step 2 of task 1197
   names, as tests first and with no verb list, and replay it over the strings of the readings.

## History

- 2026-11-24: filed when
  [task 1197](1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)
  was declined on draws into an empty store.
