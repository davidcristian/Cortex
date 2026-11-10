# A forget in capitals with one German list word reads as English

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

`_split` in `forget_unnamed.py` drops the function words of the language `message_language`
picks. A message with no lowercase letter is read by its words of four letters or more, and only
when two of them are in one language's list (`note_language.py`). `VERGISS DEN TÜRCODE 7319, ALLES
ANDERE BLEIBT.` has one such word, `VERGISS`, so it reads as English, its `DEN` names a fact, and a
unit call of `unnamed` over rows that each hold 7319 lists the row `the den alarm code is 7319`
beside the door row, a row the person asked to keep. With `BITTE` added the message reads as German
and the den row is kept ([the readings](../../readings/closing-note-language.md)). The destructive
card's safe direction is to keep rows.

## What to do

1. Write near misses as tests first: `FORGET THE DEN ALARM CODE 7319, KEEP THE REST.` and
   `FORGET MY SON'S CODE 7319, KEEP THE REST.` must still list the den and the son row.
2. Check whether the forget reader alone can read `DEN` beside `VERGISS` as German, without
   widening the note picker, whose three-letter words in capitals stay abbreviations.

## History

- 2026-11-10: filed when the note picker began reading messages in capitals, from a unit probe of
  the forget reader that task 1071 recorded (`probe2.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/58410d85-0aa8-4ebe-9853-99c9c16a6905/scratchpad/slot1/`).
