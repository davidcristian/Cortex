# Three bounds are registered as three values and the ordering they are stated in is checked by nothing

**Status:** declined 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`brain/packages/core/src/cortex_core/subagents.py` states that the delegated run's deadline sits
strictly between the two bounds either side of it, the pool's 600 s stall ceiling and its 3600 s
admission wait. All three numbers are registry entries, and each is compared with the places that
state it. The ordering itself was checked by nothing in the registry: `scripts/couplings.py` has a
`Relation.ORDERED` for this shape, but it orders the declarations of one entry, and these are three
entries in three modules.

## History

- 2026-08-23: declined. The premise is false on two counts and the proposed remedy wrong on a
  third, all checked against the tree. The second ordering is not unchecked: the close that added
  it three hours before this file was written added
  `_the_run_deadline_must_fit_inside_the_queue_for_it` beside the older ceiling validator, so
  `SubagentsConfig` raises on both wrong orderings, and every bare construction of that class reads
  all three declarations, which makes a retune inverting either one fail the orchestrator suite on
  the commit that types it. The zero-wait note this file read as an absence is the exception inside
  that validator. And `Relation.ORDERED` is non-decreasing, so the fourth entry proposed here would
  have passed with the three bounds set equal, which is the misordering both validators exist to
  catch. What is left of the observation, that the registry cannot express an ordering over
  decimals and cannot express a strict one at all, is
  [R-367](367-the-shipped-ordering-of-two-bounds-is-not-checked-in-the-repo.md), which records both halves and
  covers a pair no settings class validates. The stale sentence this file quoted is corrected in
  `cortex_core/subagents.py`. Recorded in ADR-0047 decision 7. Opens nothing.
