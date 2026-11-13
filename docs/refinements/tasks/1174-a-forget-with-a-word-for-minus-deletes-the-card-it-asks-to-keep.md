# A forget with a word for minus deletes the card it asks to keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

Over `User: Remember that my card is 4111 1111 1111 4242.` and `User: Remember that my gym code
is 4242.`, `Uită codul 4242 mai puțin cel de pe card.` (forget the code 4242 less the one on the
card) with call text `4242` deletes the card and keeps the gym code, from the calling chat and a
new one, at the start build `cec7c748f` and at HEAD. Over the French or German card the start
build deleted both rows and HEAD deletes the card alone
([readings](../../readings/forget-group-holder-unnamed.md#the-start-builds-kind-word-replay-read-again)).
No word for minus opens a keep clause (`EXCEPT` in `forget_clauses.py` holds no word that can
also mean minus or less), so `card`, the Romanian message's own word and the English row's, reads
as the row to forget, and the code word `codul` names no row.

## What to do

1. Write the case as tests, with near misses of the same verbs and no word for minus whose
   listing must not change.
2. Read a row named only by words after a word for minus as unclear and keep it (the card's safe
   direction), without adding words to `EXCEPT`, then replay the recorded forget strings.

## History

- 2026-11-13: filed from the review of the kind word replay, task
  [1158](1158-a-forget-in-one-language-keeps-a-row-stored-in-another.md).
