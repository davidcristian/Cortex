# A forget worded as a note shows the unkept note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`unkept_note_due` (`memory_claim.py`) shows `UNKEPT_CLAIM_NOTE` when `asks_kept` reads the message and
`asks_not_kept` does not. `Note that I mean the locker code.` and `Note that 8426 should be zapped.` now
reach the card and delete the row, and each reply ends with `Nothing in this message was kept in memory.
Send anything you want remembered again in a message of its own.` That is true and the person asked to
keep nothing. Run log `d971.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot8/`.

## What to do

Read whether the message states a fact before showing the note, with
`Remember that my new locker code is 8426, and forget the old code.` still showing it, since its new
code is lost.

## History

- 2026-10-31: filed from the draws of the [stated fact reader](../../readings/forget-refused-stated-fact.md#refusing-a-stated-fact-only-2026-10-31).
