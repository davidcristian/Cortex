# A Dutch forget of every value except one row deletes that row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, with the call text `4242`, the Dutch
messages `Verwijder alle 4242 behalve de kaart.` and `Verwijder alle 4242 maar de kaart.` delete
all three rows. The card reads English, French, German, Spanish and Romanian: `alle` is a German
word of `EVERY` (`forget_clauses.py`), no Dutch word opens a keep clause, and no word of the
message names a row, so `unnamed` (`forget_unnamed.py`) reads a request for every row. The card
lists the rows before the person approves, but the misread deletes a row the message asks to
keep. The Italian `Dimentica tutti i 4242 ma la carta.` and the Polish `Usuń wszystkie 4242 ale
kartę.` keep all three rows.

## What to do

1. Write tests first: both Dutch messages keep the card row; `Vergiss alle 4242.` deletes all
   three rows.
2. Find a shape that needs no Dutch word list, such as reading a word for all only in a message
   that holds a forget verb of a language the card reads, and replay it on Italian, Portuguese,
   Dutch and Polish messages.
3. Replay every string literal of the brain's forget tests through the card before and after:
   each row newly deleted must be one the message asks to delete.

## History

- 2026-11-15: filed from a probe of the card on languages it does not read, made with the change
  that keeps the rows a word for but may ask to keep
  ([readings](../../readings/forget-keep-except.md#a-word-for-but-after-the-forget-verb-2026-11-15)).
