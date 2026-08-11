# Session and global union read policy

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** Something writes durable global facts under scoping.

Recorded inside the per-session and namespaced scoping entry, which named it in the sentence listing
what stayed behind the same seams when that scoping landed:

> Remaining behind the same
> seams: a **session+global union** read policy (dead until something writes durable global facts
> under scoping), **per-scope retention/eviction**, and **cross-scope recall ranking**.

## Trail

- 2026-07-06: Named as one of three refinements left behind the `MemoryScope` seam when per-session
  and namespaced scoping landed. The index's pickup order pairs it with cross-scope recall ranking,
  on the reason that nothing writes durable global facts under scoping yet.
