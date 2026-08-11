# Recall observability

**Status:** landed 2026-08-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

Answering "why did
recall return these?" today means writing a throwaway script against the store, which is exactly
what that close's live check had to do: the recall path emits nothing. The core has no logger at
all, and the only observability port of this shape is `ToolAuditSink` (ADR-0009), which memory has
no analog of, so this is a **new port plus a sink adapter**, not a field on `ScoredMemory`, and
that is why it is not a cheap follow-on to the close that named it. It is also the consumer that
would **reopen** the declined field: a sink recording a hit's rank key is the first code that
reads one, and it should then arrive as a `RecallPolicy.select` widening rather than a second
field on the store's own output type. **Fix when it bites:** the first time a real session recalls
something visibly wrong and the ranking cannot be inspected after the fact.

## Trail

- 2026-07-16: Opened by the blended-relevance close, which had to write a throwaway script against
  the store for its own live check.
- 2026-08-06: Landed as the `RecallAuditSink` port plus `LoggingRecallSink`
  (`cortex_memory/audit.py`), one structured line per recall behind `CORTEX_MEMORY_RECALL_AUDIT=1`,
  carrying the pool size, the basis and each kept hit's id, score, key and taint bit, and no text.
- 2026-08-06: The index's fix-when-it-bites bucket still described this as a thing nobody can
  inspect after the fact on the day the sink that inspects it shipped, and that line was struck
  rather than retriggered by the same pass that corrected the area's count from 7 to 9.
