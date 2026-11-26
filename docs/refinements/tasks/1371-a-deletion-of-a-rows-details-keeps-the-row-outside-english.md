# A deletion of a row's details keeps the row outside English

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`Delete all of my card details from memory.` deletes the card: a placing word right after the word
for all that leads to the one row the clause names reads the clause as the forget's scope
(`_head_run` in `forget_permit.py`). The same request in the other four languages keeps the row:
`Efface tous les détails de ma carte de la mémoire.`, `Lösche alle Angaben zu meiner Karte aus dem
Speicher.`, `Borra todos los datos de mi tarjeta de la memoria.` and `Șterge toate detaliile despre
cardul meu din memorie.` keep the card for the call text `4242` in all 24 cases of the mixed
messages of the third audit of 2026-11-26, at the second audit's commit `1c7c329cf` and at the
tree after it
([readings](../../readings/forget-form-cells.md#mixed-messages-of-the-third-audit-2026-11-26)).
In French and German the word after the word for all is no placing word (`les`, `Angaben`), so the
words after it are read as one more run. After `todos` and `toate`, `everything` reads no forget of
everything, and the words after that unread first word are read as a head in the same way. A run
naming the row keeps it. Each misread keeps the row, so no row is deleted against the message.

## What to do

1. Write the four messages above as tests first, beside near misses that ask to keep a row
   (`Lösche alles, die Karte bleibt.`).
2. Count over the generator and every other set how many forgets of everything with a noun before a
   placing word ask to delete the row the run names, against those asking to keep it, and build
   the scope rule for them only when no row asked to keep is newly listed.

## History

- 2026-11-26: filed from the mixed messages of the third audit.
