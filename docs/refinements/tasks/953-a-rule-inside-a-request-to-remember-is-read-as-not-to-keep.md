# A rule inside a request to remember is read as a request not to keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-30

`asks_not_kept` (`memory_request.py`) reads a whole sentence, so a request to remember a rule
whose own words say "don't save", "never keep" or "forget" is read as a request not to keep, and
`memory_withheld` stores nothing of the turn. The rule the person asked to keep is lost.

Each of these returns True from `memory_withheld(caps, TaintLedger(), (), query=...)` with memory
on, where a request to remember should return False:

- `Remember: don't save files to the desktop.`
- `Please remember, never keep the milk out of the fridge.`
- `Remember my rule: never record calls without asking.`
- `Remember that people just forget their PINs.`

Two parts of the reader cause it. `_DONT_KEEP` matches "don't" or "never" before a keep verb at
any clause start, including the clause right after a "remember" opener, which is the content to
remember. `_FORGET` takes "just", "so" or "then" as an opener after any subject but the four
pronouns `_SUBJECT` lists, so "people just forget" reads as a request.

## What to do

1. Add the four messages above, and the existing `NOT_KEPT` and `KEPT` tables, as the unit rows
   the reader must pass in both directions before changing it.
2. Read a "don't keep" clause as a request only when its object is the message or a value in it
   ("it", "this", "that", "my ..."), or when no "remember" opener comes before it in the
   sentence; and read "just" or "then" before "forget" as an opener only at a clause start.

## History

- 2026-10-30: filed from the closing audit of the night's memory request readers.
