# The no-match forget result tells the model to say nothing was stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

`_NONE_FOUND` (`forget_results.py`), the result of a `forget_memories` call whose text no row
contains, tells the model to "tell the user that nothing about it was stored". That is false when a
row states the same fact in other words, as in
[R-969](969-a-forget-of-the-old-value-can-match-nothing-and-say-none-is-stored.md) and
[R-1061](1061-a-forget-of-what-was-just-said-can-match-nothing-and-say-it-was-never-stored.md).
Since 2026-11-10 `UNMATCHED_FORGET_NOTE` follows every such reply and states what is true
([readings](../../readings/forget-matched-nothing-note.md)), so the person is told; the reply above
the note still says the fact was never stored, and the note then says an exchange in other words
is still stored.

## What to do

1. Write rows and a rule first, with the shipped note as the base: a result text that says only
   that no remembered exchange contains that exact text and keeps "do not ask the user for the
   value". The text must not suggest a next forget, since a model-read result that named a next
   step made the model delete a second fact unasked. Count, per build, replies saying the fact was
   never stored and calls the model makes after the no-match result.

## History

- 2026-11-10: filed from R-969 and R-1061, which the note closed; this is the result text the
  model reads, left unchanged by that fix.
