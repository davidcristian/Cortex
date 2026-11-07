# A forget reports nothing of a value left without a word of its text

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

The `forget_memories` card lists the rows that contain the call's text and each other row that
holds a whole value of those rows (a phone number or code in full) beside a word of the text. A
row that holds the value with no word of the text, such as `User: What number did I give you?
Assistant: 7731.` after a forget of `code de mon casier à la piscine`, is not listed, so it stays.
`invoke` then searches only for the text, finds nothing, and says `no remembered exchange contains
that text now`, so the reply says the code is forgotten while a later chat can recall it
([readings](../../readings/forget-value-repeats.md)). A row holding a value that was written after
the card was shown is missed the same way.

## What to do

1. After the delete, search the remaining rows for each value of the deleted rows, and when one
   is found say in the result how many rows still hold a value of the forgotten ones, without the
   value. That changes the text the model reads, so write rows and a pass rule into the readings
   first, with a flow whose recall reply names only the value.
2. If the reply still says the fact is forgotten, compare that with a note the brain appends after
   a typed check of the reply, as `forget_claim.py` does for a forget that deleted nothing.

## History

- 2026-11-07: filed when the card began listing rows that repeat a value; the result part was
  left for a measured change.
- 2026-11-07: the flow and pass rule are written in the readings; three baseline draws did
  not show the form, because the recall turn did not name the code, and task 1005 was filed.
