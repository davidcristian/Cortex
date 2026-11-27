# A refused forget call made before a handoff gives no refused held note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-27

A reply on a turn whose refused forget call named a whole value a stored row still holds ends with
`REFUSED_HELD_NOTE` (`forget_refused_held.py`). `hold_refused_value` reads the call texts from
`TaintLedger.forget_refused_texts`, and the handoff record (`handoff.py`) keeps
`forget_refused` but not those texts. So when the cortex makes the refused call and then hands
the turn to the deep phase, the deep phase's reply gets no note, and the person is not told that
a remembered exchange still holds the value.

## What to do

1. Keep the refused call texts in the handoff record beside `forget_refused`, so the deep phase
   reads the cortex's refused calls the way it reads `forget_calls` and `forget_unmatched`.
2. Test a turn whose cortex call was refused before a handoff: the deep reply ends with the note
   in the message's language, and a record written before the field existed still loads.

## History

- 2026-11-27: filed from the close of [task 1199](1199-a-request-to-remember-that-a-value-is-outdated-refuses-the-forget-tool-outside-english.md), whose History names this gap.
