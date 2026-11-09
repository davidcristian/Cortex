# A German negation after the keep verb reads as a keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

German puts `nicht` after the verb and its object, while `_split` in `forget_unnamed.py` reads a
negation only before a keep verb. `Vergiss 7319 und behalte den vom Schuppen auch nicht.`, which
asks to forget the shed row too, opens a keep clause at `behalte`, and the shed row is kept. The
reader fails toward keeping ([readings](../../readings/forget-keep-clause.md#second-audit-probes-2026-11-09)).

## What to do

1. Write the message above and a near miss (`behalte den vom Schuppen, nicht den vom Fahrrad`) as
   tests first.
2. Read a German keep clause that ends in `nicht` with no other clause mark as negated, then replay
   every recorded forget string through the old and new reader.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
