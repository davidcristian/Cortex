# Per-scope retention and eviction

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A memory-compaction or self-editing feature needs a retention scheduler.
**Verified:** 2026-09-13

Recorded inside two landed entries rather than as a bullet of its own. The per-session and
namespaced scoping entry named it among what stayed behind the same seams:

> Remaining behind the same
> seams: a **session+global union** read policy (dead until something writes durable global facts
> under scoping), **per-scope retention/eviction**, and **cross-scope recall ranking**.

The tiered and self-editing memory entry named it again, first against the verbs the port did not
have:

> Per-scope retention and per-provenance eviction
> are blocked on the same missing verbs.

and then, once the delete verb landed, against the consumer it does not have:

> **Still deferred, each for want of
> a consumer and not a missing verb now:** self-editing (**update** in place), **tiered**
> promote/demote/expire, **write-salience** (its own entry below), and the **per-scope retention
> _policy_** (the eviction verb exists; a retention scheduler deciding what to evict when does not,
> and nothing drives one). **Per-provenance eviction** ([untrusted-content.md](../index.md#untrusted-content))
> wants a different filter, since a memory record stores only the `tainted` bit, not the ADR-0027
> structured provenance, so `delete_scope` does not serve it and it stays fix-when-it-bites.

## Trail

- 2026-07-06: Named as one of three refinements left behind the `MemoryScope` seam when per-session
  and namespaced scoping landed.
- 2026-07-16: The delete/forget verb landed as `MemoryStore.delete_scope(scope) -> int`, with
  per-scope eviction one of the two consumers already recorded as waiting on it, so the index's
  "Memory verbs" line moved from actionable-with-a-port-change to dead until a consumer and what is
  left is the retention policy rather than the missing verb. Per-provenance eviction is not this
  entry: it wants a different filter, since a record stores only the taint bit and not the ADR-0027
  structured provenance, and it stays fix when it bites in another area.
- 2026-09-13: Re-derived, and two of the quoted claims have moved. `MemoryStore` now answers
  `count_candidates(scopes=...)` with the store's own size of a namespace, which is the reading
  a retention policy needs besides the record timestamps it already gets, so a policy that
  evicts a scope once it grows past a cap is now writable over verbs the port has rather than
  over verbs it lacks. The brain also runs a recurring pass of its own now, the `ScheduleTicker`
  loop over the `ScheduleStore`, so "nothing drives one" is a statement about this repo having
  no retention driver and not about the process having no periodic pass to hang one on. What is
  missing is still the policy and the decision of what drives it. The trigger has not fired:
  nothing here compacts memory or edits it in place.
