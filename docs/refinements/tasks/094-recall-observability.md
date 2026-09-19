# Recall observability

**Status:** done 2026-08-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

Answering "why did recall return these?" used to mean writing a throwaway script against the
store, because the recall path emitted nothing. The core had no logger at all, and the only
observability port of this shape was `ToolAuditSink` (ADR-0009), which memory had no equivalent
of, so this was a new port plus a sink adapter rather than a field on `ScoredMemory`.

It shipped 2026-08-06 as the `RecallAuditSink` port plus `LoggingRecallSink` in
`cortex_memory/audit.py`: one structured line per recall behind `CORTEX_MEMORY_RECALL_AUDIT=1`,
with the pool size, the basis, and each kept hit's id, score, key and taint flag, and no text.

## History

- 2026-07-16: Opened by the blended-relevance close
  ([R-091](091-blended-relevance-field.md)), which had to write a throwaway script against the
  store for its own live check. It was also the consumer that would reopen that declined field,
  since a sink recording a hit's rank key is the first code to read one.
- 2026-08-06: Shipped as `RecallAuditSink` and `LoggingRecallSink`.
- 2026-08-06: The index still described this as something nobody can inspect after the fact on
  the day the sink shipped. That line was removed by the same pass that corrected the area's
  count from 7 to 9.
