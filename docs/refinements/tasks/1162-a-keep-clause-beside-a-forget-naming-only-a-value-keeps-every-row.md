# A keep clause beside a forget naming only a value keeps every row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

Over `User: Remember that my card is 4111 1111 1111 4242.` and `User: Remember that my gym code
is 4242.`, `Forget every 4242 except the card.` and `Forget every 4242 but keep the card.` with
call text `4242` delete neither row. With a clause asking to keep, `_unnamed`
(`forget_unnamed.py`) deletes only a row a whole word of the forget part names, and `Forget every
4242` names a value and no word, so the gym code row the message asks to delete is kept. The kept
note names both rows, so the person sees it.

## What to do

1. Decide whether a forget part naming only a value names each row holding that value whole.
2. If it does, write both messages as tests with near misses (`Forget 4242 except my gym code.`
   keeps the gym code), then replay the strings of the readings through the old and new code.

## History

- 2026-11-12: filed from the tests of the forget of every row holding a code.
