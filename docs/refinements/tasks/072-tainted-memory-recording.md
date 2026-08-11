# Context-preserving tainted-memory recording

**Status:** landed 2026-07-06
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)

A tainted turn dropped its exchange
from memory (fail-closed); it can now be recorded instead with an untrusted-provenance marker
(`MemoryRecord.tainted`, a pgvector column) under `CORTEX_MEMORY_ON_TAINTED=record` (default
`skip` = the old behavior). Recall **always** fences a stored tainted memory (`wrap_untrusted` +
`TaintLedger.ingest_untrusted`) and re-taints the turn, so untrusted-derived content is
fenced-and-tainting across turns, not just within one, with the invariant extended behind the
unchanged `MemoryRecaller`/`MemoryStore`/`TaintLedger` seams. CI-gated end to end over the fakes;
the pgvector column host-validated by the live contract check. Remaining behind the same seams
(ADR-0019 deferred): **structured provenance** beyond the bit (source URI/sender, joining the
ADR-0013 deferral; the `TurnStamp` these fields join landed 2026-07-13,
[ADR-0027](../../adr/ADR-0027-turn-provenance.md)), a **fence-without-block** recall mode if
taint-spread on tangential recall is
too blunt, **summarizing** a tainted exchange before recording, and **per-provenance eviction**.
