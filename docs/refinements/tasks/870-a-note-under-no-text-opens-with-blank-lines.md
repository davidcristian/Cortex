# A note under no text opens with blank lines

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)
**Verified:** 2026-10-15

When a turn ends with `CONTEXT_OVERFLOW_NOTE` before the model wrote any text, the reply is the
note alone, and the note starts with `"\n\n"`. On the Linux shell on 2026-10-15 each such bubble
opened with two empty lines, and its text then says "The text above is everything I produced"
with no text above it
([readings](../../readings/overlay-long-and-unusual-input.md#a-pasted-log-near-the-context)).
`overflow_note`, `unreadable_call_note`, `cap_note` and `rounds_note` in `turn_output.py` all
append their constant whole, while `repeat_note` already adds only the line breaks one blank line
needs.

## What to do

Give the four notes one helper that drops the leading line breaks when the parts so far hold no
text, and name the empty case in the overflow and unreadable call notes, whose "text above" then
does not exist. Update `test_engine_overflow.py` and the converse test that expect the constant
whole, and check one overflow on the shell.

## History

- 2026-10-15: filed from the long-input flows on the Linux shell.
