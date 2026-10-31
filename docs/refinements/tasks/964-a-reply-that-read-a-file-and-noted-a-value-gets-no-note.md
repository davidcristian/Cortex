# A reply that read a file and noted a value gets no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-10-31

`claims_kept` (`memory_claim.py`) returns false for "I have read your lease and noted the address:
Birkenweg 14, 3521 Utrecht." and "I've found your contract and noted the phone number: 555 0142.",
and true for "I've noted the address from your lease". A file tool's result keeps the turn out of
memory, so the first reply told the person a value was noted and nothing was stored, with no
`UNKEPT_CLAIM_NOTE` beside it
([readings](../../readings/sidecar-tools-on-remember.md#a-value-named-by-a-record-the-draws-2026-10-31)).
Any turn that reads a file and asks to remember can draw this form, so it does not depend on the
reader of [R-962](962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md).

## What to do

1. Read "and noted", "and saved" and their kin after an earlier verb as a claim. Near misses come
   first: a reply reporting what the person noted, or a file's own text, must stay unread. Replay
   every recorded reply through the old and new reader.
2. Add both replies above as tests.
3. The same run drew a reply saying it has no "long-term memory" for facts, beside a real memory.
   Check how often that appears before writing anything for it.

## History

- 2026-10-31: filed from the rows of
  [R-962](962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md).
