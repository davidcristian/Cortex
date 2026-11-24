# A request to remember a fact stated with a verb that is no copula keeps the forget tool

**Status:** declined 2026-11-24
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`asks_kept_fact_other` (`fact_request.py`) reads a request to remember in French, German, Spanish
or Romanian as one stated fact only when the fact holds a copula and a value, so `forget_unrequested`
keeps the forget tool on `Merk dir, dass mein Hund Bello heißt.`, `Recuerda que tienes cita a las
9.`, `Ține minte că sora mea vine mâine.` and the other 18 such strings the
[replay](../../readings/forget-refusal-stated-fact.md#replay-through-the-start-build-and-the-fix)
names. Keeping the tool there costs the stated fact only when the model calls the forget tool
unasked; no call came in 4 draws of the Bello message on 2026-11-14, and all 4 stored the row.
The opposite case is refused: a copula with an action as its value, such as `Souviens-toi que tu
es censé jeter mon code.`, reads as a stated fact.

## What to do

1. Draw the store turn of three of these forms on the current build, 8 draws each, and count
   forget calls and rows stored, with the rule written first.
2. Only if a call withholds a row, design a stated fact shape for a subject, a finite verb and a
   value that the five action forms of
   [task 1171](1171-a-request-to-remember-an-action-stated-after-que-dass-or-ca-refuses-the-forget-tool.md)
   do not match, as tests first, and add no verb list.

## History

- 2026-11-14: filed when the forget refusal was read only on a fact stated with a copula.
- 2026-11-24: checked on HEAD with `forget_unrequested` alone: `Merk dir, dass mein Hund Bello
  heißt.`, `Recuerda que tienes cita a las 9.` and `Ține minte că sora mea vine mâine.` still keep
  the tool, the safe side. The draw of step 1 needs the card and stays for a count slot.
- 2026-11-24: declined. Step 1 drew the store turn of the Bello, cita and sora forms into an
  empty store, 8 draws each: the cortex called the forget tool unasked in 11 of 24 draws and all
  24 stored the fact row, so no call withheld a row and step 2 is not needed
  ([readings](../../readings/forget-refusal-stated-fact.md#the-store-turn-of-four-forms-the-rule-keeps)).
  The same forms with an older row stored are
  [task 1331](1331-a-request-to-remember-a-fact-with-no-copula-keeps-the-forget-tool-beside-an-older-row.md).
