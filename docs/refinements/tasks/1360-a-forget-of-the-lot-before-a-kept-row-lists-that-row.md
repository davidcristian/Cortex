# A forget of the lot before a kept row lists that row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`Forget the lot the card stays.` deletes the card for the call texts `card` and `4242`. `lot` is
no word for all, so `everything` (`forget_permit.py`) reads no forget of everything in the
message, and the head rule that keeps a row named after the word for all of such a forget reads
nothing there. The message reads as `Forget the old card.` does, with the keep verb `stays`
unread. Over the probe of nearby heads these are the 2 of 30 cases still listing a row asked to
keep
([readings](../../readings/forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26)).

## What to do

1. Count how many forget messages naming a row before an unread keep verb, as `stays` or
   `bleibt`, in a clause with no word for all, ask to keep that row, over the generator and the
   pairs, against those asking to delete it, as `Forget the card that stays in my wallet.`.
2. Build a rule that keeps such a row only when that count shows its cost, as rows asked to
   delete newly kept; a word for all is not added to `forms.ALL`.

## History

- 2026-11-26: filed from the head rule for a forget of everything, which keeps the row after
  every other head of the probe.
