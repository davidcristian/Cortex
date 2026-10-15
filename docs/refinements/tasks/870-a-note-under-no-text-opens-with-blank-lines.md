# A note under no text opens with blank lines

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)
**Verified:** 2026-10-15

When a turn ends with a note before the model wrote any text, the reply is the note alone, and
the note starts with `"\n\n"`. On the Linux shell on 2026-10-15 each overflow bubble opened with
two empty lines
([readings](../../readings/overlay-long-and-unusual-input.md#a-pasted-log-near-the-context)).
`MESSAGE_OVERFLOW_NOTE`, for a message too long alone, comes only before any text. After a tool
round that wrote none, `CONTEXT_OVERFLOW_NOTE` and `UNREADABLE_CALL_NOTE` still say "The text above
is everything I produced" with no text above them.
`overflow_note`, `unreadable_call_note`, `cap_note` and `rounds_note` in `turn_output.py` all
append their constant whole, while `repeat_note` already adds only the line breaks one blank line
needs.

## What to do

Give the notes one helper that drops the leading line breaks when the parts so far hold no text,
and name the empty case in the context overflow and unreadable call notes, whose "text above" then
does not exist. Update `test_engine_overflow.py` and the converse test that expect the constant
whole, and check one overflow on the shell.

## History

- 2026-10-15: filed from the long-input flows on the Linux shell.
