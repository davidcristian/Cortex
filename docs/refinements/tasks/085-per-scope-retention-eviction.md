# Per-scope retention and eviction

**Status:** open, waiting for a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A memory-compaction or self-editing feature (R-087) needs a retention scheduler.
**Verified:** 2026-09-19

A policy that decides which memories to drop and when. The eviction verb exists; the policy and
whatever would run it do not.

It was one of three refinements left behind the `MemoryScope` port when per-session scoping
shipped ([R-083](083-namespaced-memory-scoping.md)), and the tiered and self-editing memory entry
([R-087](087-tiered-self-editing-memory.md)) names it again.

Per-provenance eviction is a different entry and needs a different filter: a memory record stores
only the `tainted` flag, not the ADR-0027 structured provenance, so `delete_scope` does not serve
it.

## History

- 2026-07-06: Named as one of three refinements left behind the `MemoryScope` port.
- 2026-07-16: The delete verb shipped as `MemoryStore.delete_scope(scope) -> int`, with per-scope
  eviction one of the two consumers already waiting on it. What is left here is the retention
  policy rather than a missing verb.
- 2026-09-13: Checked again, and two claims had moved. `MemoryStore` now has
  `count_candidates(scopes=...)`, which gives the size of a namespace, the reading a retention
  policy needs besides the record timestamps it already gets. The brain also runs a recurring
  pass of its own, the `ScheduleTicker` loop over the `ScheduleStore`, so what is missing is a
  retention driver rather than any periodic pass to hang one on. The trigger has not fired:
  nothing here compacts memory or edits it in place.
- 2026-09-19: Checked again; the trigger has not fired. The only caller of `delete_scope` is
  still `SessionMemoryCascade`, and the only caller of `count_candidates` is still
  `MemoryRecaller`, which asks only when a recall audit sink is wired. `ScheduleTicker` in
  `cortex_orchestrator/ticker.py` is still the brain's only recurring pass. The 2026-09-13 note
  overstated the verbs: `delete_scope` removes a whole namespace, and the port's docstring
  forbids passing it `GLOBAL_SCOPE`. Under the default `CORTEX_MEMORY_SCOPE=global` every memory
  is in that one scope, so a retention policy there has no verb at all, since evicting past a cap
  or an age means deleting some records of a scope and keeping the rest, which needs a delete by
  id or by timestamp the port does not have. Only under `session` scoping do the current verbs
  serve, and there a policy can drop whole conversations, sized by `count_candidates`, but never
  part of one. The port also lists no scopes, so such a policy would take its candidates from the
  session store. ADR-0008's consequences now state this.
