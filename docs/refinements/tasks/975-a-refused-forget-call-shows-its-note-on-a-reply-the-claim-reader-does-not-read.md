# A refused forget call shows its note on a reply the claim reader does not read

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`limit_notes` (`closing_notes.py`) shows `UNFORGOTTEN_CLAIM_NOTE` after a call refused as unasked when
`claims_kept` does not read the reply. `claims_kept` returns false on
`Understood. I'll make sure to keep your vegetarian preference in mind for any recipes.` and on
`Got it, your locker code is 8426.`, so a person who only asked to remember a fact would read about
forgetting. The first wording is in 3 of the 259 recorded replies to R and P rows with no forget card
(`slot2/pair.jsonl`, `slot4/draw961b.jsonl`, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/`), all
on R13, a row that has also drawn a refused call. No recorded draw has both yet. The note is true, so
the cost is a confusing line.

## What to do

Read `I'll make sure to keep` in `claims_kept`, with near-miss tests first, since `unkept_note_due`
reads it too. `Got it` alone says nothing kept, so `OK.` and `Got it.` keep showing the note.

## History

- 2026-10-31: filed from the [note on a refused call](../../readings/forget-refused-stated-fact.md#a-reply-saying-it-kept-and-removed-2026-10-31).
