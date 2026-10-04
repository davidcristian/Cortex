# Cross-scope recall ranking

**Status:** open, waiting for a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** One recall's pool can draw from more than one non-empty scope: the union read of
R-084 ships, or a store already holding per-session scopes is read under
`CORTEX_MEMORY_SCOPE=global`, whose unfiltered search mixes them.
**Verified:** 2026-10-04

Weighting a recall hit by the scope it came from. It was one of three refinements left behind the
`MemoryScope` port when per-session scoping shipped
([R-083](083-namespaced-memory-scoping.md)), but that is the wrong port for it.

## History

- 2026-07-06: Named as one of three refinements left behind the `MemoryScope` port. The index's
  pickup order pairs it with the session and global union read policy, because nothing writes
  durable global facts under scoping yet.
- 2026-09-13: Checked again, and the port this was filed behind is the wrong one. A `MemoryScope`
  policy only chooses which namespaces recall reads; the weighting happens after the store has
  returned them. The port for that is `RecallPolicy`, which shipped a week after this entry was
  recorded ([ADR-0008](../../adr/ADR-0008-memory-v1.md) decision 10). It hands a policy the whole
  candidate pool as `ScoredMemory` values, each holding `record.scope`, and takes back a `Ranking`
  naming the key it ordered by. So the work is a new policy beside the ones that ship plus one
  member in the `RankBasis` family, with no change to the port or the store.
- 2026-09-19: Checked again; no consumer has appeared. `RecallPolicy.select` still receives
  `ScoredMemory` values holding `record.scope`, `RankBasis` still has the six members `ECHO`,
  `EMBER`, `SPREAD`, `SWEEP`, `VERDICT` and `DEMUR`, and the one commit to `rerank.py` since then
  only restated which policies may return fewer than `k`. The 2026-09-13 note was wrong that an
  unfiltered recall reads one namespace: each row is stamped with its scope when written, so a
  store that ran under `session` and is then set to `global` holds one scope per earlier
  conversation plus `global`, and `GlobalMemoryScope` reads all of them into one pool. That pool
  has scopes to weigh without anything writing durable global facts, so the trigger now fires
  when a single pool can mix scopes, either by the union of R-084 or by that switch. ADR-0008
  decision 9 now states this.
- 2026-09-30: Checked again; the trigger has not fired. `RecallPolicy.select` (`rerank.py:11`)
  still receives `ScoredMemory` values holding `record.scope`, `RankBasis` (`ranking.py:11`) still
  has its six members, and the commits to the recall code since 2026-09-19 added the turn id to
  the recall trail and reworded names and log text. The union read of R-084 has not shipped, and
  no store has been seen switched from `session` to `global`.
- 2026-10-04: Checked again; the trigger has not fired. `RecallPolicy` (`rerank.py:11`) and the
  six members of `RankBasis` (`ranking.py:11`) are unchanged, `memory_scope_from_name` builds no
  union policy, and the host store, read this time from the `cortex_cortex-pgdata` volume, holds
  two rows, both in `global`, so a recall under the default scope mixes no scopes there.
