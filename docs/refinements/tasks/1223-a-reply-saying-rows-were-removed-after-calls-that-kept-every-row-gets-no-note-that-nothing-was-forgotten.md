# A reply saying rows were removed after calls that kept every row gets no note that nothing was forgotten

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

On 2026-11-15 a side brain of the `cortexn23` stack answered `Forget all 4242 except the card.`
after four forget calls that each returned `KEPT_ALL` with "I have updated your memories. I've
removed the locker code and phone number, but I've kept your card number." Both rows were stored.
The reply ended with the note naming the rows still in memory and without
`UNFORGOTTEN_CLAIM_NOTE`: `claims_forgotten` (`forget_claim.py`) returns `False` for it, and for
"I've updated your memories and removed the locker code and phone number", since `removed` names
no memory in that sentence
([readings](../../readings/forget-keep-no-call.md#rows-a-forget-request-holds-2026-11-15-what-was-drawn)).

## What to do

1. Prefer a note that needs no reader of the reply: on a turn whose forget calls all kept every
   row and deleted none, "no forget call in it deleted a memory" is true whatever the reply says,
   as `UNMATCHED_FORGET_NOTE` is on a call that matched nothing.
2. Check the note order beside the note naming the kept rows, and that a turn in which a later call
   deleted a row gets neither.

## History

- 2026-11-15: filed from the draws of a build that put the rows a forget reaches in the first
  request.
