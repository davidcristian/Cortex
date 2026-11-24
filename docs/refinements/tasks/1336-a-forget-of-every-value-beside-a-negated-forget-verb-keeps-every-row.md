# A forget of every value beside a negated forget verb keeps every row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-24

A forget of every value followed by a clause that negates a forget verb keeps every row, the rows
it asks to delete too: `Vergiss alle 4242, lösch nicht die Karte.`, `Oublie tous les 4242,
n'efface pas le casier.`, `Oublie tous les 4242, ne supprime pas le casier.` and `Forget all
4242, don't delete the locker.` delete nothing, while `Vergiss alle 4242, nicht die Karte.`
deletes the locker code and keeps the card. The keep clause holds the forget verb it negates;
that the readers of a forget of every value then read no role from it is an assumption, not
yet checked.

Over the audit's 8,376 negated messages ([readings](../../readings/forget-keep-any-reading.md#a-negation-inside-a-clause-with-a-forget-verb-2026-11-24)),
212 rows asked to delete are kept this way (German 180, French 32). One message each of the
French `ne supprime pas` and English `don't delete` forms, which the card read before, keeps
every row the same way.

## What to do

1. Count the rows asked to delete that every negated tail keeps after a forget of every value,
   in the five languages, beside the tail with no forget verb (`nicht die Karte`).
2. Read the forget verb inside a keep clause as part of that keep clause's opening words, so the
   clause names its row as `nicht die Karte` does, with no new word in a list.
3. Replay the generator, the audit's negated messages and the a1 word pairs: no row asked to keep
   listed, and state the rows asked to delete that are newly deleted.

## History

- 2026-11-24: filed when a negation inside a clause holding a forget verb began to open a keep
  clause, which made these forms keep every row as the forms already read did.
