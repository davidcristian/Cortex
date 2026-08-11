# Write-salience policy

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A memory-compaction or self-editing feature needs a record-time salience decision.

v1 records the raw exchange text every turn; deciding what
*deserves* remembering (salience filtering at record time) is a later policy (ADR-0008 risks).
Its summarization half is adjacent to the tiered-memory entry above. **Cost correction:** a
policy that can decline to record does not fit the current shape, because
`MemoryRecaller.record` returns a **non-optional** `MemoryRecord`; the return has to widen
(or the decision move to the caller) before anything can drop a write.

## Trail

- 2026-07-16: The delete/forget verb this was bundled with landed, so what remains is policy with no
  consumer rather than a port change, and the index groups it with self-editing update in place,
  tiered promote/demote/expire and the per-scope retention policy.
