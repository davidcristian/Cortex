# The unkept note follows a forget reply that kept the fact asked to keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-09

A forget turn is withheld from memory, and `unkept_note_due` in `memory_claim.py` shows
`UNKEPT_CLAIM_NOTE` on any reply `claims_kept` reads. Since a forget message can now ask to keep a
fact, a correct reply such as `Done, I've forgotten your bike lock code and kept the shed one.` is
followed by `(Nothing in this message was kept in memory. ...)`, which reads as if the shed row
was not kept ([readings](../../readings/forget-count-note.md#second-audit-probes-2026-11-09)).

## What to do

Write the reply above and a reply that falsely says the forget message itself was saved as tests
first. Then skip the unkept note when the turn's forget kept rows and the reply's keep names one
of them, and replay the recorded forget replies.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
