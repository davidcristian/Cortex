# The no-match forget result tells the model to say nothing was stored

**Status:** done 2026-11-12
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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

1. A text that drops the instruction about what to tell the user does not work: on 2026-11-12
   `nothing was forgotten, since no remembered exchange contains that exact text; do not ask the
   user for the value` made a second forget call that deleted the old phone row in 1 of 2 phone
   turns that reached it, and a false removal claim in 1 of 2 turns about a passport never stored
   ([readings](../../readings/forget-matched-nothing-note.md#the-no-match-result-reworded-what-was-drawn-2026-11-12)).
2. Next candidate, with rows and a rule written first on the same p1 and m1 rows: keep an
   instruction to report, but make it true, such as `tell the user that no remembered exchange
   contains that exact text`, with "do not ask the user for the value" and no next step. Count
   per build the replies saying the fact was never stored, forget calls after the no-match
   result, and removal claims.

## History

- 2026-11-10: filed from R-969 and R-1061, which the note closed; this is the result text the
  model reads, left unchanged by that fix.
- 2026-11-12: left open. The reworded text with no instruction to report failed its rule, a
  forget call after the no-match result deleting a row, so the result text is unchanged.
- 2026-11-12: done. `NONE_FOUND` now tells the model to say that no remembered exchange contains
  that exact text. Of 8 turns that read it, none said the fact was never stored, made another
  forget call or claimed a removal; all 7 turns that read the old text said the fact was not stored
  or had no record
  ([readings](../../readings/forget-matched-nothing-note.md#the-no-match-result-told-to-report-the-exact-text-what-was-drawn-2026-11-12)).
