# A request to remember beside a put off decision gets no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-09

A message that puts off the decision to save one thing is withheld whole, so a request in it to
remember another thing is not stored either. `unkept_note_due` in `memory_claim.py` then shows
`UNKEPT_CLAIM_NOTE` only when the reply claims a keep, since `asks_kept` counts only when
`asks_not_kept` does not. Unit calls on 2026-11-09: for `Remember that my gym code is 4417. I'll
tell you later whether to save the dentist's address.` and its German form, the replies `Got
it.` and `Okay, let me know about the address.` get no note, so the person is not told the
gym code was not kept. A reply note's safe direction is to show.

## What to do

1. Write near misses as tests first: `Don't save this.` alone and `I'll tell you later whether to
   save it.` alone still get no note on a bare acknowledgment.
2. Show the note when a sentence other than the one asking not to keep asks to remember, then
   replay every recorded draw message through the old and new reader.

## History

- 2026-11-09: filed from unit calls in the third audit of the night (`probe5.py` in
  `/tmp/claude-1000/-home-david-Files-Git-Cortex/504fd3d2-8740-44f5-b388-49c61671fb23/scratchpad/slot18/`).
