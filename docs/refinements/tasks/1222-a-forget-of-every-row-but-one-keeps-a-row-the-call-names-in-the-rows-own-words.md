# A forget of every row but one keeps a row the call names in the row's own words

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

On 2026-11-15 a side brain of the `cortexn23` stack put the gym code row in the first request of
`Forget everything but my card.` beside the card row. The cortex called `forget_memories` in 3 of 3
draws with the texts `gym code`, `gym`, `gym code is 4242` and `4242`, and every call returned
`KEPT_ALL` with no card, so the gym row stayed stored in 3 of 3. On
`Forget all 4242 except the card.` over a locker code, a card and a phone, the texts `locker code`,
`phone` and `0721 555 4242` each returned `KEPT_ALL`; only the text `4242` listed the locker and
phone rows and kept the card, in 1 of 3 draws
([readings](../../readings/forget-keep-no-call.md#rows-a-forget-request-holds-2026-11-15-what-was-drawn)).
With a keep clause, `_unnamed` (`forget_unnamed.py`) lists only a row a whole word or value of the
part asking to forget names. That part is `everything` or `all 4242` here, and the call names the
row in words only the row holds. `Forget all 4242 apart from the card.` has no keep clause, and
there the texts `locker code` and `phone` each listed their row in 2 of 2 draws.

## What to do

1. Write the near misses as tests first: a keep clause naming the row in other words
   (`Forget everything but my Visa.` over a card row) and one naming no stored row must keep every
   row, as today.
2. Read a part asking to forget that holds a word for all (`EVERY`) and no word naming a row as
   asking for each match the keep clause does not name, only when every content word of the keep
   clause names a stored row; with a value beside the word for all, only for a match holding that
   value.
3. Replay every recorded card case through the old and the new reader: each newly listed row must
   be one the message asks for.
4. Draw it with the rows of
   [task 1151](1151-recall-leaves-out-the-rows-a-forget-of-everything-but-one-fact-asks-to-delete.md)
   in the first request, since the default recall leaves them out.

## History

- 2026-11-15: filed from the draws of a build that put the rows a forget reaches in the first
  request.
