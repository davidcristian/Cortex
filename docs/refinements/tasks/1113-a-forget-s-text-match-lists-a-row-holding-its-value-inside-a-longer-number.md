# A forget's text match lists a row holding its value inside a longer number

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

`_found` in `memory_forget_chosen.py` lists every row whose text contains the call's text
(`find_text`). When that text is itself a whole value, a row holding it only inside a longer value
matches too. In both draws of flow j in [the readings](../../readings/forget-value-short-groups.md),
`Forget what I just said.` called `forget_memories` with `015 123 456 789`, and the approved card
listed and deleted the row `Remember that my phone account is 015 123 456 7890.`, which holds
another number. The value search for the other rows already drops such a row (`_repeats`); the text
match does not. Unit reproduction: rows `my phone is 015 123 456 789` and `my phone account is 015
123 456 7890`, call text `015 123 456 789`: the card lists both.

## What to do

1. Write near misses first: a call naming a whole value with rows holding it inside a longer
   number, beside a longer code (`789b`), and as the last four digits of a card the person names
   (`4242` for `4242 4242 4242 4242`), since a person may ask to forget a value by its end.
2. When the call's text is a whole value, keep a text match whose whole values do not include it,
   the destructive card's safe side, and show it under the kept line so the person sees it stayed.
3. Draw the neighbouring flows after the change: a value named alone, forget what was just said, a
   keep clause.

## History

- 2026-11-10: filed from the flow j draws of the short group change (task 1042), 2 of 2 draws.
