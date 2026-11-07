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

1. Build the note the brain appends after a typed check of the reply, as `forget_claim.py` does
   for a forget that deleted nothing. Apply the count of the patch the [readings](../../readings/forget-value-repeats.md#the-draws-of-both-results-2026-11-07) name; set
   a `TaintLedger` field in `dispatch_round.py` from each `forget_memories` result (true after a
   result with a count, false after any other result of that tool, as `daily_after` sets
   `daily_stored`), keep it in the handoff record as `forget_unmatched` is, and in
   `closing_notes.py` append the note when the field is true and `claims_forgotten` reads the
   reply.
2. Draw the `fr-v` and `yr-v` flows of the readings with the note until four draws show the form,
   under the rule there.

## History

- 2026-11-07: filed when the card began listing rows that repeat a value; the result part was
  left for a measured change.
- 2026-11-07: the flow and pass rule are written in the readings; three baseline draws did
  not show the form, because the recall turn did not name the code, and task 1005 was filed.
- 2026-11-07: the form occurred in a French replay draw whose text `casier à la piscine` shares
  no word with an English recall row; its reply said the code was forgotten while the row stayed
  ([readings](../../readings/forget-value-repeats.md#the-whole-value-reader-replayed-2026-11-07)).
- 2026-11-07: a result counting the remaining rows that hold a number of the deleted rows was
  built and drawn: two of four draws showing the form still said the code was forgotten, so it
  does not ship ([readings](../../readings/forget-value-repeats.md#the-draws-of-both-results-2026-11-07)).
