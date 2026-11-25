# The forget card readers changed by the audited commits have no seeded live draw

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-25

Five readers of the forget card changed on 2026-11-25 and were checked by replays of strings
only: `_held` (`forget_clauses.py`), `quantifies` (`forget_unnamed.py`), `_kept_later` and
`_forgets` (`forget_permit.py`) and the keep clause words of `_split` (`forget_unnamed.py`). A
replay of strings alone missed a loss of both values in 3 of 32 draws on 2026-11-24, so a change
to what a reader lets the card list is drawn live with the rows seeded.

## What to do

1. Write the pass rule first: no row the message asks to keep is listed by an approved card.
2. Seed three rows holding `4242` (card, phone, locker; one language per run), then draw, every
   card approved: `Wipe everything, the card stays, don't delete the phone.`, `Forget my
   phones 1234, the phone stays.`, `Forget all cupboards 4242.`, `Vergiss alle 4242, lösch nicht
   die Karte.` and `Wipe everything, the card stays.`, 8 draws each, counting calls, cards, rows
   listed and rows left.

## History

- 2026-11-25: filed by the audit of the night's forget commits.
