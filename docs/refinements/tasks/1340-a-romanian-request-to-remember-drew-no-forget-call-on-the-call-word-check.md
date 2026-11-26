# A Romanian request to remember drew no forget call on the call word check

**Status:** done 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unsaid` (`forget_unsaid.py`) refuses a forget call naming a word that a request to
remember in another language lacks. With the old row seeded, the 16 draws of `Ține minte că sora
mea vine mâine.` after `Ține minte că sora mea vine vineri.` wrote no forget call, against 4 of 16
on the tree earlier the same night, so the check met no call on this form live. The two losing
calls recorded on it (`sora mea vine vineri`, `sora ta vine vineri`) are refused in the replay
([readings](../../readings/forget-refusal-call-words.md)).

## What to do

1. Write the pass rule first: no old row deleted, and at least 4 draws with a forget call.
2. Draw the form again on the check with the same seed, every card approved, 32 draws, and count
   calls, refused calls, old rows deleted and new facts stored.

## History

- 2026-11-25: filed when
  [task 1331](1331-a-request-to-remember-a-fact-with-no-copula-keeps-the-forget-tool-beside-an-older-row.md)
  was closed on draws where this form wrote no forget call.
- 2026-11-26: done. 32 draws on the call word check with the old row seeded: 6 with a forget
  call, the 4 calls naming the old value refused, no card shown, the old row kept and the new fact
  stored in all 32
  ([readings](../../readings/forget-refusal-call-words.md#the-romanian-remember-drawn-again-2026-11-26)).
