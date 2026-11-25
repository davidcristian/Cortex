# The stored rows' words change no reading of a word for all

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`quantifies` (`forget_unnamed.py`) stops a word for all at a word of the stored rows or of the
message. Given no rows, so reading the message's words only, it reads every one of 61,992 pairs
of a message and its rows the same as given the rows: the forget generator, the forget of
everything family and both sets of mixed messages. No forget test fails either, so the rows' part
of the rule has no case that needs it.

## What to do

1. Look for a message whose word between a word for all and the value names a stored row only
   through a row's word, such as a plural or a compound the message writes and the row does not.
2. Write each one found as a test that fails with the message's words only; if none is found,
   read the message's words only and say so in the module doc.

## History

- 2026-11-25: filed by the audit of the night's forget commits; the script is `surv.py` in
  `~/.cache/cortex-run/2026-11-25/a1/`.
