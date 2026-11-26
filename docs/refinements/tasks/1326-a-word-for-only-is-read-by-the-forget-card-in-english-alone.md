# A word for only is read by the forget card in English alone

**Status:** declined 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

The cells of the word for only in `FORMS` (`forget_forms.py`) hold `only` and `just` alone, so
`Oublie tous les 4242, seulement la carte.`, `Vergiss alle 4242, nur die Karte.`, `Olvida todas
las 4242, solo la tarjeta.` and `Uită toate 4242, doar cardul.` keep every row, where `Forget all
4242, only the card.` deletes the card. Each word filled alone lists no row asked to keep and
deletes 535 to 972 rows asked to delete, but lists 53 to 114 rows not asked for ([readings](../../readings/forget-form-cells.md#the-cells-replayed-one-at-a-time-2026-11-24)).
With the card keeping each row a word for only leaves out (`alone` in `forget_only.py`),
`seulement` and `nur` still list 56 and 22, each in a run that adds a row and holds the word for
only, which English lists too
([readings](../../readings/forget-form-cells.md#a-word-for-only-read-as-a-limit-beside-another-clause-2026-11-26)).
`solo` is an Italian word too, and filled, `doar` deletes the card on the Polish
`Zapomnij 4242, doar card.`.

## What to do

1. Once an adding run holding a word for only is read as a role no reader reads, replay each
   cell filled alone again, and fill `seulement` and `nur` when no row not
   asked for is listed.
2. Read `solo` and `doar` only in a message read as Spanish or Romanian (`readings` in
   `forget_languages.py`), not in a wider flat set, and replay each the same way.

## History

- 2026-11-24: filed from the survey of [task 1221](1221-the-forms-the-forget-card-reads-in-english-are-not-all-read-in-the-other-four-languages.md).
- 2026-11-26: the card now keeps each row a run holding a word for only and read as a limit does
  not name (`alone` in `forget_only.py`), so `Forget all 4242, the card too, only the phone.`
  keeps the card and the locker code; it costs 150 rows asked to delete over the generator.
  After it, `seulement` and `nur` filled alone still list 56 and 22 rows not asked for, all in a
  run that adds a row and holds the word for only, which English lists too; recorded with its count ([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26))
  ([readings](../../readings/forget-form-cells.md#a-word-for-only-read-as-a-limit-beside-another-clause-2026-11-26)).
- 2026-11-26: declined at the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): its remedy fills `FORMS` cells and its counts are over generated messages. 535 to 972 rows asked to delete stay kept per word over the generator ([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)).
