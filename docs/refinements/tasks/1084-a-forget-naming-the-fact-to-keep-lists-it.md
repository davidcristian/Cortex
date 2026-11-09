# A forget naming the fact to keep lists it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`unnamed` in `forget_unnamed.py` reads every word of the message as naming a fact to forget, so a
word in a clause that asks to keep or negates names that row too, and the card lists it. With a
bike lock row and a shed padlock row both holding 7319 and the call text 7319, `Forget my bike
lock code 7319, keep the shed padlock one.`, `Forget my bike lock code 7319 but not the shed one.`
and `Forget my bike lock code, not the shed one.` keep no row (unit calls, no turn drawn).

## What to do

1. Write near misses first: a keep clause with no label (`keep everything else`), a negation
   inside a label (`the not so old code`), and `Don't keep my bike lock code 7319`.
2. Leave a word of a clause that asks to keep or negates out of the words that name a fact, and
   replay the recorded forget draws through the old and new reader.

## History

- 2026-11-09: filed from the reshape of the keep reader
  ([readings](../../readings/forget-shared-number.md#the-keep-reader-reshaped-2026-11-09)).
