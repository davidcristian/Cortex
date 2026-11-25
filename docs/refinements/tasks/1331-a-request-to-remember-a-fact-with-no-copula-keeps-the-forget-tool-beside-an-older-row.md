# A request to remember a fact with no copula keeps the forget tool beside an older row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`forget_unrequested` (`forget_unrequested.py`) keeps the forget tool on a request to remember in
French, German, Spanish or Romanian whose fact holds no copula, such as `Merk dir, dass mein Hund
Bello heißt.`, `Recuerda que tienes cita a las 9.` and `Ține minte că sora mea vine mâine.`
([task 1197](1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)).
Into an empty store the cortex called the tool unasked in 11 of 24 draws of these three forms,
each call named the new fact, and no row was lost
([readings](../../readings/forget-refusal-stated-fact.md#the-store-turn-of-four-forms-the-rule-keeps)).
With an older row stored that holds the same words, such a call can match it and its approved
card deletes it. With an older row of the same fact stored, 16 draws per form, the cortex
deleted the old row unasked in 3 of 48 draws (1 of 16 for the Bello form, 0 for the cita form, 2
for the sora form), and each time the person ended up with neither value
([readings](../../readings/forget-refusal-stated-fact.md#three-forms-with-no-copula-and-an-older-row-stored-2026-11-25)).

## What to do

1. Write the rule first, then draw each of the three forms with an older row of the same fact
   stored (`Merk dir, dass mein Hund Rex heißt.` before the Bello message, and so on), 8 draws
   each, every card approved, and count the calls, the old row deleted and the new fact stored.
2. Build the stated fact shape that step 2 of task 1197 names, as tests first and with no verb
   list: a possessive subject (`mein Hund`, `sora mea`, `mon vélo`, `mi perro`) with a finite verb
   and a value, which reads the Bello and sora forms and none of the five action forms of task
   1171. The cita form has no subject and may stay unread, since it lost no row in 16 draws.
3. Before the build, count over the forget generator (`gen.py` in
   `~/.cache/cortex-run/2026-11-24/f4/f3gen/`) the requests to forget in the four languages that
   the shape would newly refuse, as rows asked to delete that are kept, and replay it over the
   strings of the readings. A request such as `Merk dir, dass mein Code weg muss.` has a
   possessive subject too.
4. Draw the Bello and sora forms live on the new reader with the seeds of the readings, 16 draws
   each, every card approved: no old row may be deleted.

## History

- 2026-11-24: filed when
  [task 1197](1197-a-request-to-remember-a-fact-stated-with-a-verb-that-is-no-copula-keeps-the-forget-tool.md)
  was declined on draws into an empty store.
- 2026-11-25: step 1 drawn with an older row stored, two stack runs of 8 draws per form: 3 of
  48 draws deleted the old row unasked and lost both values, so step 2 opens. Steps 2 to 4 now
  name the shape, the cost count and the live draw. Left open, since the shape, its count and
  its draw did not fit the slot together.
