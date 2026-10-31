# A forget that did not run can be claimed in words the note does not read

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`unforgotten_claim` (`forget_claim.py`) reads English forms of "forgotten" and "removed". After a refused
`forget_memories` call, real replies said `Ich habe deinen Spindcode 8426 aus meinem Gedächtnis gelöscht.`
and `I've processed your request to forget the locker code.`. The row stayed and neither reply showed
`UNFORGOTTEN_CLAIM_NOTE`. Run logs `t1.jsonl` and `t3.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot7/`.

## What to do

A refused call is a fact the brain has, so try closing every reply on a turn with a refused
`forget_memories` call with a note, with no reading of the reply, as the unkept note does on a withheld
request to remember. Rows and a pass rule go in the readings before the baseline, with a request to
remember whose refused call the reply does not mention: that turn must not show a note saying something
the person never asked about.

## History

- 2026-10-31: filed from the night's closing audit.
