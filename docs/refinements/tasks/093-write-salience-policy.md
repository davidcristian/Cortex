# Write-salience policy

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A memory-compaction or self-editing feature (R-087) needs a record-time salience
decision.
**Verified:** 2026-09-19

v1 records the raw exchange text every turn; deciding what
*deserves* remembering (salience filtering at record time) is a later policy (ADR-0008 risks).
Its summarization half is adjacent to the
[tiered-memory entry](087-tiered-self-editing-memory.md). **Cost correction:** a
policy that can decline to record does not fit the current shape, because
`MemoryRecaller.record` returns a **non-optional** `MemoryRecord`; the return has to widen
(or the decision move to the caller) before anything can drop a write.

## Trail

- 2026-07-16: The delete/forget verb this was bundled with landed, so what remains is policy with no
  consumer rather than a port change, and the index groups it with self-editing update in place,
  tiered promote/demote/expire and the per-scope retention policy.
- 2026-09-13: Re-derived, and the cost correction's own alternative is already in place.
  `MemoryRecaller.record` does still return a non-optional `MemoryRecord`, but the decision
  whether to record at all lives in the caller today: `record_exchange` in `turn_output.py` is
  the only call site of it in the brain, and it already declines two classes of write, an opaque
  turn always and a tainted turn unless `record_tainted_memory` is set. So a salience filter that
  drops a write needs no widening of that return. It is a third condition at that call site, or a
  policy injected there beside the two conditions already in it, which makes this entry policy
  and a consumer rather than a port change. The trigger has not fired. One naming note for
  whoever lands it: `SaliencePolicy` is taken, by the tool loop's port deciding whether a call is
  worth dispatching, so a record-time policy needs a name of its own.
- 2026-09-19: Re-derived; the trigger has not fired and the 2026-09-13 account holds.
  `record_exchange` in `turn_output.py` is still the only caller of `MemoryRecaller.record`, it is
  reached from both `TurnEngine` and `BrainPhase`, and it still returns early on an opaque turn and
  skips a tainted one unless `record_tainted_memory` is set. `SaliencePolicy` is still the tool
  loop's port in `tool_salience.py`. One fact bears on the remedy: the shipped recall default,
  `judge`, already drops at read time the notes the model says do not help, and the dedup
  reranker drops near-duplicates, so a record-time filter would repeat a decision the read side
  makes per recall, at the one point where it cannot be revised. What a drop at record time saves
  that the read side cannot is the embedding call and the row itself, which is why the trigger
  waits for a feature that needs the store to hold less. The trigger now names that feature's
  entry.
