# Context-preserving tainted-memory recording

**Status:** done 2026-07-06
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)

A tainted turn used to drop its exchange from memory. It can now be stored with a marker saying it
came from an untrusted source (`MemoryRecord.tainted`, a pgvector column) under
`CORTEX_MEMORY_ON_TAINTED=record`, with the old behaviour kept as the default `skip`.

Recall always fences a stored tainted memory (`wrap_untrusted` plus `TaintLedger.ingest_untrusted`)
and taints the turn again, so untrusted-derived content stays fenced and tainting across turns
rather than only within one. The `MemoryRecaller`, `MemoryStore` and `TaintLedger` ports are
unchanged. Covered end to end over the fakes, with the pgvector column checked on the host by the
live contract run.

Four things were left behind it: structured provenance beyond the bit, closed by
[R-076](076-turnstamp-structured-provenance.md); a fence-without-block recall mode
([R-073](073-fence-without-block-recall.md)); summarizing a tainted exchange before storing it
([R-075](075-summarizing-tainted-exchange.md)); and per-provenance eviction
([R-074](074-per-provenance-eviction.md)).
