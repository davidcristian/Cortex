# A request to remember in a sentence asking not to keep gets no note

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-09

A message that asks to forget or not to keep one thing and, in the same sentence, to remember
another is withheld whole, and `unkept_note_due` in `memory_claim.py` reads it per sentence, so
the reply `Got it.` gets no `UNKEPT_CLAIM_NOTE`. Replayed 2026-11-09 over the readings strings:
`Forget my card number 4242 4242 4242 4242, and remember that my locker code is 7319.`, `Please
forget my card number, and note that I moved to Utrecht last week.`, `Erase the whiteboard photo
from my notes and remember the new layout` and `Merk es dir erst mal, ich sage dir später, ob du
es speichern sollst.` get none, though nothing they ask to keep is stored. A reply note's safe
direction is to show.

## What to do

1. Write near misses as tests first: `Remember: don't save this.`, `Remember that you should
   forget my locker code.` and `Remember not to save calls.` keep today's result.
2. Read the request per clause, then replay every recorded message through the old and new reader.

## History

- 2026-11-09: filed from the replay of the per sentence note rule
  ([readings](../../readings/chat-only-limit-words.md#a-request-to-remember-beside-a-request-not-to-keep-2026-11-09)).
