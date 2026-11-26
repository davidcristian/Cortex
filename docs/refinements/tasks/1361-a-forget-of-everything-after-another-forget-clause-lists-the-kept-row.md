# A forget of everything after another forget clause lists the kept row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`Forget the card. Forget everything the phone stays.` and `Forget my old card. Forget all of it
the phone stays.` delete the phone, which the message asks to keep, for the call texts `phone` and
`4242`. The head rule in `_head_run` (`forget_permit.py`) reads the forget of everything only in
the first clause holding a forget verb, and here that clause is `Forget the card.`. The same
heads in the first clause keep the phone
([readings](../../readings/forget-everything-unread-forms.md#heads-of-more-than-one-word-2026-11-26)).

## What to do

1. Add this form to the generator: a forget clause naming a row, then a forget of everything with
   no clause mark before a kept row, in five languages.
2. Find why `_beyond_every` or `_kept_later` leaves the phone listed, read the head of the clause
   `everything` reads rather than the first forget clause, and replay over every set: no row asked
   to keep newly listed, with the rows asked to delete newly kept as its cost.

## History

- 2026-11-26: filed from the head rule for a forget of everything, whose replay found the form.
