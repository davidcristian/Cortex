# A forget worded as a note shows the unkept note

**Status:** declined 2026-11-05
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

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
- 2026-11-05: declined. The premise held, and the remedy fails: on a turn with a forget call, the
  refusal's stated fact reading would hide the note on 181 of 384 recorded requests to keep, and the
  subject reading alone on 98, including `Note that the new PIN is 8426, the old one can go.` and
  `Remember the code 7319 and wipe the PIN.`, where the new value is lost. The note is true, and its
  cost on a forget request is one unneeded line. Recorded in the
  [readings](../../readings/forget-refused-stated-fact.md#the-unkept-note-on-a-forget-worded-as-a-note-2026-11-05).
