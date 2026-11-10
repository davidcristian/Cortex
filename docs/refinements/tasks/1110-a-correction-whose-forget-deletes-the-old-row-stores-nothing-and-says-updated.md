# A correction whose forget deletes the old row stores nothing and says updated

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

In 2 of 18 correction draws ([the readings](../../readings/correction-keeps-old-value.md)), `My bike lock code is 4862, not 4826.` and `My gym locker number
is 5512, not 5521.` called `forget_memories` with the old value. The approved card deleted the seed
row and the turn stayed out of memory, so no row held either value, and a new chat found no code.
The reply said "I've updated that" and ended with the forget count note alone. `UNKEPT_CLAIM_NOTE`
shows on such a turn only when `asks_kept` reads the message as a request to remember (task 967),
and `claims_kept` does not read "I've updated that".

## What to do

1. Write near misses for an update claim reader first: a question, a negation, a condition and an
   offer (`I can update it if you want.`), then replay every recorded reply in `docs/readings/`.
2. Weigh showing `UNKEPT_CLAIM_NOTE` on a turn whose forget deleted a row while the reply claims an
   update. The note states that nothing of the message is stored and invites no further forget.

## History

- 2026-11-10: filed from the c1 and c2 draws in [the readings](../../readings/correction-keeps-old-value.md), beside task 1062.
