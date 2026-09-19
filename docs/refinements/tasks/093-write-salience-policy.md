# Write-salience policy

**Status:** open, waiting for a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A memory-compaction or self-editing feature (R-087) needs a record-time salience
decision.
**Verified:** 2026-09-19

v1 records the raw exchange text on every turn. Deciding at record time what is worth remembering
is a later policy (ADR-0008). Its summarization half sits next to the tiered-memory entry
([R-087](087-tiered-self-editing-memory.md)).

The decision whether to record at all already lives in the caller. `record_exchange` in
`turn_output.py` is the only call site of `MemoryRecaller.record` in the brain, and it already
skips two kinds of write: an opaque turn always, and a tainted turn unless `record_tainted_memory`
is set. A salience filter is a third condition there, or a policy injected beside the two, rather
than a port change.

Naming note for whoever builds it: `SaliencePolicy` is already taken by the tool loop's port in
`tool_salience.py`, which decides whether a call is worth dispatching.

## History

- 2026-07-16: The delete verb this was bundled with shipped, so what remains is a policy with no
  consumer rather than a port change. The index groups it with update in place, tiered promote,
  demote and expire, and the per-scope retention policy.
- 2026-09-13: Checked again, and the alternative the entry named is already in place, as
  described above. `MemoryRecaller.record` does still return a non-optional `MemoryRecord`, but
  nothing has to widen for a write to be dropped. The trigger has not fired.
- 2026-09-19: Checked again; the trigger has not fired and the 2026-09-13 account holds.
  `record_exchange` is still the only caller, reached from both `TurnEngine` and `BrainPhase`.
  One fact bears on the remedy: the shipped recall default, `judge`, already drops at read time
  the notes the model says do not help, and the dedup reranker drops near-duplicates, so a
  record-time filter would repeat a decision the read side makes per recall, at the one point
  where it cannot be revised. What a drop at record time saves is the embedding call and the row
  itself, which is why the trigger waits for a feature that needs the store to hold less.
