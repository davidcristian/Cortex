# A store request whose turn stores nothing shows no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

`unkept_note_due` (`memory_claim.py`) shows `UNKEPT_CLAIM_NOTE` on a turn that stores nothing when
the reply claims a memory (`claims_kept`) or the message asks to remember (`asks_kept`).
`Save my phone number 0721 555 019.` is read by neither: `asks_kept` reads no store verb, and
`claims_kept` reads `I've saved` only before `in memory`, since a file write says `saved` too. In 3
of 12 start build draws on 2026-11-15 the model called `list_allowed_directories`, the turn stored
nothing, the reply was `I've saved your phone number: 0721 555 019.` and no note followed
([readings](../../readings/store-request-unasked-tools.md)). The file tools are now refused on that
message, so this form needs another tool to keep the turn out of memory: a screen capture, or a
file call on a store request the tool readers keep the tools on (`Save my locker 42.`).

## What to do

1. Write tests first: the message above with that reply on a turn that stores nothing shows the
   note; `Save the report to my notes folder.` with `I've saved the report.` shows none.
2. Read `stores_fact` (`fact_request.py`) beside `asks_kept` in `unkept_note_due`. The note's text
   is true on every turn that stores nothing, so the wide reader is the safe one here.
3. Replay every test string and recorded message through both builds and name each newly due one.

## History

- 2026-11-15: filed from step 3 of
  [task 1196](1196-a-request-to-save-a-fact-in-english-keeps-the-file-tools.md).
