# A word for only is read by the forget card in English alone

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

The cells of the word for only in `FORMS` (`forget_forms.py`) hold `only` and `just` alone, so
`Oublie tous les 4242, seulement la carte.`, `Vergiss alle 4242, nur die Karte.`, `Olvida todas
las 4242, solo la tarjeta.` and `Uită toate 4242, doar cardul.` keep every row, where `Forget all
4242, only the card.` deletes the card. Each word filled alone lists no row asked to keep and
deletes 535 to 972 rows asked to delete, but lists 53 to 114 rows not asked for ([readings](../../readings/forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24)).
Each of those is in a message where another clause adds, keeps, excepts or negates a row, or
names a row by a word another stored row shares, which HEAD already lists without the word for
only. English does the same today: `Forget all 4242, the card too, only the phone.` deletes the
card and the locker code. `solo` is an Italian word too, and filled, `doar` deletes the card on
the Polish `Zapomnij 4242, doar card.`.

## What to do

1. Write near misses first, then a reading of a word for only beside a clause that adds, keeps
   or excepts a row, in English, that keeps the rows of the other clause rather than listing
   them. Count over the generator the rows asked to delete that it keeps.
2. Replay each cell filled alone after it, and fill `seulement` and `nur` when no row not
   asked for is listed.
3. Read `solo` and `doar` only in a message read as Spanish or Romanian (`readings` in
   `forget_languages.py`), not in a wider flat set.

## History

- 2026-11-24: filed from the survey of [task 1221](1221-the-forms-the-forget-card-reads-in-english-are-not-all-read-in-the-other-four-languages.md).
