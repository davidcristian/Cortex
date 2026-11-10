# A reply saying it kept a row the forget never matched gets the unkept note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-10

`unkept_note_due` (`memory_claim.py`) skips a reply whose keep claim names a row the turn's forget
kept (`names_spared`), but a row the forget never matched is not in `TaintLedger.forget_spared`.
In flow k of [the readings](../../readings/forget-value-short-groups.md), draw 2 on 2026-11-10,
`Forget my phone number but keep Anna's phone.` deleted the person's row and left Anna's, which no
call matched, and the reply `OK. I've forgotten your phone number and kept Anna's.` ended with
`UNKEPT_CLAIM_NOTE` (`Nothing in this message was kept in memory. ...`). Draw 1 replied without a
keep claim and got no note. The note is on its reader's safe side, since it shows, but it reads as
contradicting a true reply.

## What to do

1. Write near-miss replies as tests first (a keep claim naming a fact of the message, one naming a
   row still stored, a question), then decide whether a keep claim naming a stored row the message
   asks to keep can skip the note without letting a false keep claim through.

## History

- 2026-11-10: filed from the flow k draws after the note naming a row kept for a longer value.
