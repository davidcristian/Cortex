# The field's ceiling assumes the shipped id factory

**Status:** open, fix when it bites
**Area:** memory
**Trigger:** a deployment that injects a `MemoryRecaller` `id_factory` minting anything other than
a 36-character uuid4, or a `MemoryStore` that mints ids of its own
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-26 by the close of
[R-358](358-the-widest-value-was-never-a-real-line.md), whose strongest result is an arithmetic
ceiling rather than a sample, and the ceiling rests on one assumption worth writing down.

The recall trail's `dropped` field at the shipped pool of twenty renders as 1,101 characters of
syntax and id plus twenty float reprs, and no Python float renders in more than 24 characters, so
the field cannot pass 1,581 however the cosines fall. The 1,101 is where the assumption lives: it
is twenty ids at 36 characters each plus the JSON around them, and 36 is what `str(uuid4())` spells.

`MemoryRecaller` takes `id_factory` as a constructor argument precisely so it can be swapped, and
the composition root passes none, so the shipped brain mints uuid4 and the ceiling holds. A
deployment that injects a longer factory moves the field's width by twenty characters for every
character it adds to an id, and nothing anywhere compares the result to `VALUE_CHARS`. At the
shipped bound the slack is 467 characters, which buys 23 characters of id: at 60 characters the
worst case passes 2,048 and at 65 the measured reprs do, and a cut trail line is the failure the
bound was sized to avoid.

**What would close it.** Either a bound on the id at the port, which is a real constraint on a
field the store round-trips and would want an argument of its own, or a line in
`docs/modules/brain-memory.md` naming 60 as the id width at which the trail starts losing
candidates, so the next person to inject a factory meets the number rather than discovering it. The
second is the cheap one and probably the right one: the id is the store's identity, and narrowing it
to buy log headroom would let a logging bound dictate a storage identity.
