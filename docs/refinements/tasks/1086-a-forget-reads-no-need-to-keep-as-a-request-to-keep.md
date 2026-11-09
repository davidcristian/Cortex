# A forget reads no need to keep as a request to keep

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_opens_keep` in `forget_unnamed.py` opens a keep clause at a negation that starts a clause unless
a keep verb comes right after it. In `Forget 7319, no need to keep the shed one.` the keep verb
comes three words later, so the shed row is kept and only the bike row is deleted, while the person
asked to forget both. The reader fails toward keeping, and the card lists the shed row as kept
([readings](../../readings/forget-keep-clause.md#second-audit-probes-2026-11-09)).

## What to do

1. Write near misses as tests first: `no need to keep`, `no reason to keep`, `not going to keep`,
   and `but not the one I keep in the shed`, where a keep verb after the negation is part of the
   fact's own text and the clause still asks to keep.
2. Read a keep verb within a few words after the negation as a negated keep, then replay every
   recorded forget string through the old and new reader (`slot9/replay.py` in the night's
   scratchpad is the shape).

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
