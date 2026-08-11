# PGDATA directly on the Windows drive

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

**W, but no Tauri app and no overlay:** this needs only Docker on the Windows host. Explicitly a
nice to have, not a default.

Kept verbatim from [ADR-0008](../../adr/ADR-0008-memory-v1.md) decision 7:

> **Durable data placement: named volume + export, not a raw PGDATA bind mount.** The live
> Postgres data directory is a **named Docker volume** (avoids the ownership/latency pitfalls of a
> Postgres data dir over a Docker-Desktop Windows bind mount); a dump/sync job exports it to
> `D:\Software\AI\Database` to satisfy the plug-and-play requirement. Mounting PGDATA directly onto
> the Windows drive is validated on the host as a *nice to have*, not the default. The plug-and-play
> guarantee does not depend on it.

**What only this proves.** Whether Postgres can run its data directory over the Windows bind mount
at all. Nothing depends on the answer: the plug-and-play guarantee rides the dump sidecar either
way, which is why this sits at the bottom of the list.

**Do.** Point PGDATA at a Windows bind mount instead of the named volume and bring the memory
override up. [runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md) records the intent but
carries no procedure, so writing one is part of this if it is ever taken.

**Pass.** Postgres initializes and serves with acceptable latency.

**Fail.** Ownership errors on initdb, or latency bad enough to notice. Both are the documented
pitfalls and both mean the default stays the default, which is a perfectly good result to record.

**Record it.** A dated addendum to [ADR-0008](../../adr/ADR-0008-memory-v1.md) and a line in
[runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md).

## Notes

- The sitting doc heads this item "Optional, and a different bring-up", so it does not ride the
  sitting's shared `npm run tauri dev` bring-up at all.
- The host index's roll call repeats that nothing depends on the answer and that no procedure
  exists yet, so writing one is part of taking it. This item is also the reason that roll call
  exists: it was added 2026-07-19 after this check was found sitting on two of the three records
  the rule requires.

## Trail

- 2026-07-19: the host index filed the roll call this check founded naming a second example beside
  it, the resident VRAM figure with the projector loaded, and withdrew that example the same day on
  finding it was no host item at all. The index recorded that half of the roll call's founding
  evidence as withdrawn, which leaves this check as the half that stood.
