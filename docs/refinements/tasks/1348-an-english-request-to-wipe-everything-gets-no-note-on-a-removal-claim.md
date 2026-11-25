# An English request to wipe everything gets no note on a removal claim

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

`uncalled_note_due` (`forget_uncalled.py`) adds the note that no forget call ran when
`asks_to_forget` or `asks_to_forget_keeping` reads the message, or a delete verb opens a clause
beside a request to remember. None of them reads `Wipe everything, the card stays, don't delete
the phone.`, `Wipe everything, the card stays.` or `Delete everything, the card stays.`, while
`Forget everything, the card stays.` and `Lösch alles, die Karte bleibt.` are read. In the seeded
draw of 2026-11-25 ([readings](../../readings/forget-readers-seeded-draw.md)) the first message
made no forget call in 8 of 8 draws, and 3 replies said the other information was cleared or
removed with no note, as `I've kept your card and phone number in my memory as requested and
cleared any other information.`, while the locker row the message asks to delete stayed stored.
`claims_forgotten` (`forget_claim.py`) read `I have kept your card information and removed any
other memories.` on the second message, but no claim whose object is `information` with no
memory word after the verb.

## What to do

1. Count over the replay sets (the forget generator, the forget of everything family and the
   backticked strings of docs and tests) the messages that open a clause with an English delete
   verb before a word for all, and how many `uncalled_note_due` reads now.
2. Read such a clause opening as asking to forget in `uncalled_note_due` alone, since the note is
   true on every turn it reaches; replay the strings through the old and new trigger, then draw
   the first message 8 times with the three rows seeded.

## History

- 2026-11-25: filed from the seeded draw of the night's forget card readers.
