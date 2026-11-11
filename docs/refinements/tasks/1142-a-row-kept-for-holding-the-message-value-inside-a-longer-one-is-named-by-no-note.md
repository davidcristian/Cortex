# A row kept for holding the message value inside a longer one is named by no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-11

When a `forget_memories` call names a value the person's message lacks and a match holds every
value the message names only inside a longer value, the card keeps the match (`longer` in
`forget_longer.py`). With no card, the call returns `LONGER_ALL`, and the row goes into
`ToolResult.spared` but not `ToolResult.inside` or `ToolResult.kept`, so neither `inside_note`
nor `kept_note` names it after the reply. `inside_note` says the text a forget call searched for
is in each row only inside a longer value, which is false for such a row: it holds the call's text
whole.

Reproduction, the engine test
`test_a_turn_calling_a_longer_value_than_the_message_names_keeps_the_row` in
`test_forget_inside_note.py`: with only `Remember that my phone account is 015 123 456 7890.`
stored, `Forget my phone 015 123 456 789.` and a call of `015 123 456 7890` keep the row. A reply
`I've forgotten that number.` ends with `UNFORGOTTEN_CLAIM_NOTE`, while a reply `Nothing was
deleted.` ends with no note naming the row that stayed.

## What to do

1. Write a note true for such a row (it holds the value the message names only as part of a
   longer value), in the five languages the other forget notes use, and append it as `inside_note`
   is appended, unless a later call of the turn deleted the row or kept it as unnamed.
2. Engine tests: the note shows after `LONGER_ALL`, not after a later delete of the row, and once
   beside `inside_note` when both kinds were kept.

## History

- 2026-11-11: filed from the build of task 1115.
