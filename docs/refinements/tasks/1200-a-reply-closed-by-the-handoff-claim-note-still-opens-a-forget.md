# A reply closed by the handoff claim note still opens a forget

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-14

`claim_corrected` (`reply_notes.py`) reads only `UNFORGOTTEN_CLAIM_NOTE` in its five languages.
`unforgotten_note` (`forget_claim.py`) writes `HANDED_CLAIM_NOTE` instead for the same false claim
when the reply's calls hand off to the deep model, so `forget_open` still reads the claiming words
of such a reply as an open forget, and the next plain fact keeps the forget tool. The test
`test_a_reply_with_no_claim_note_at_its_end_is_not_corrected` asserts this for `I deleted your
code.` closed by `HANDED_CLAIM_NOTE`, and no document gives the reason.

## What to do

1. Check the premise first: read how a handoff turn is stored in the working session, and whether
   the cortex's claiming text and the handoff note end up in the last assistant message that
   `_exchange` (`tool_loop.py`) reads.
2. If they do, write the test first: an earlier exchange closed by `HANDED_CLAIM_NOTE` opens no
   forget, while one whose turn ran a forget still opens one. Then read both notes in
   `claim_corrected`.
3. If they do not, write the reason beside the test's case and close this task as satisfied.

## History

- 2026-11-14: filed by the audit of the night's forget refusal changes.
