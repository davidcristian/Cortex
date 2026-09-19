# PGDATA directly on the Windows drive

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

**W, but no Tauri app and no overlay:** this needs only Docker on the Windows host, and it is
explicitly a nice to have rather than a default.

[ADR-0008](../../adr/ADR-0008-memory-v1.md) decision 7 keeps the live Postgres data directory in a
named Docker volume, which avoids the ownership and latency problems of a Postgres data directory
over a Docker Desktop Windows bind mount, and exports it with a dump job to
`D:\Software\AI\Database` for the plug-and-play requirement. Mounting PGDATA directly onto the
Windows drive is validated on the host as a nice to have; the plug-and-play guarantee does not
depend on it.

**What only this proves.** Whether Postgres can run its data directory over the Windows bind mount
at all. Nothing depends on the answer, which is why this sits at the bottom of the list.

**Do.** Point PGDATA at a Windows bind mount instead of the named volume and bring the memory
override up. [runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md) records the intent but
has no procedure, so writing one is part of this if it is ever taken.

**Pass.** Postgres initializes and serves with acceptable latency.

**Fail.** Ownership errors on initdb, or latency bad enough to notice. Both are the documented
problems and both mean the default stays the default, which is a good result to record.

**Record it.** Put the reading in the readings record under
[docs/readings/](../../readings/README.md) that [ADR-0008](../../adr/ADR-0008-memory-v1.md) rests
on, edit that ADR in place where the run changes what it states, and add a line in
[runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md).

## Notes

- The session doc heads this item "Optional, and a different bring-up", so it does not use the
  session's shared `npm run tauri dev` bring-up at all.
- This item is the reason the host index's per-item list exists: it was added 2026-07-19 after this
  check was found recorded in two of the three places the rule requires.

## History

- 2026-07-19: the host index created that list naming a second example beside this one, the
  resident VRAM figure with the projector loaded, and withdrew that example the same day on finding
  it was no host item at all. This check is the half that stood.
