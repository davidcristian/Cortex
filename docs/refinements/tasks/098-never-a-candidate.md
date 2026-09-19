# Why a memory was never a candidate

**Status:** done 2026-08-10
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The recall trail could say that a memory was a candidate and was dropped, or that it was neither,
but not why an id was in neither list. Three causes were indistinguishable: the memory ranked
below the pool cutoff, its scope was not read, or it was never written.

Two of the three are derivable from configuration. The scopes are set by `CORTEX_MEMORY_SCOPE`
and the `session` the line already records (`GlobalMemoryScope` reads everything,
`SessionMemoryScope` reads that one session). The third was not derivable: `pool_size` says how
many candidates came back, never how many there were, so a pool filled to the requested width
cannot be told from a store that held exactly that many.

**Shipped 2026-08-10** ([ADR-0038](../../adr/ADR-0038-ranked-recall.md) decision 14), ahead of
its trigger, since neither an investigation nor a widened pool had happened. It was taken because
the only thing blocking it was that trigger, and because the default had moved to `judge` and
left the trail thinnest where most of the pool now disappears.

`MemoryStore.count_candidates(*, scopes=None) -> int` is a new verb rather than a widened
`search`, so the one production caller of `search` is untouched. The pgvector adapter runs
`SELECT count(*)` under the same `WHERE scope = ANY` a scoped search applies, the in-memory twin
counts the same filtered list, and `RecallAudit` gained a required `available` field that the
sink writes as one more key. The reading is a comparison: when `available` equals `pool_size` the
pool was the whole readable store, so an id on neither `hits` nor `dropped` was never written or
was written outside the read scopes; when it is larger the pool was cut and an absent memory may
only have ranked below the cutoff.

One of the entry's own claims failed: the requested width is not `k` times the pool factor under
`CORTEX_MEMORY_RECALL=raw`, whose `candidate_k(k)` is `k` with no over-fetch, nor on a fallback
line, whose emitted basis is the fallback's while the width was the judge's. That costs no field,
because `available` makes the width redundant.

The count's price was measured. An exact `count(*)` is 2.0 ms against a 520 ms ranked search over
100k rows, because `memories_scope_idx` serves it as an index-only scan with no heap fetches
while the search detoasts every row and computes a 768-dimension distance for it. On an
unvacuumed table it rises to 22 to 31 ms, still under 6%. So a capped count was declined for
saving nothing, and the single-read shape was declined for costing 2.85 times the plain search:
`count(*) OVER ()` puts a `WindowAgg` under the `Limit` that materializes all 100,000 rows,
`embedding::text` included, before the top-20 heapsort can discard them, and at 20k rows that is
invisible. The count is issued only inside the `audit is not None` guard, and it runs next to the
search rather than after the rank.

Eight mutations were run, six in CI and two against real Postgres, each failing only what it
should. The first had to be fixed rather than watched: the contract check was written with three
memories, which any count capped at three or more passes, and it caught a cutoff-capped count
only once it held more memories than the widest pool a shipped deployment fetches. The pass also
fixed a check that ran in only one place: `memory_contract.ALL_CHECKS` was driven solely by the
live pgvector run, so a check added to the shared file reached CI only if someone wrote it a
second time by hand. The fake now runs the same file in CI. Confirmed live in the
`cortex_contract` database (1 passed, 39 deselected), where the `len(rows)` mutation makes the
count check fail on 20 against 25.

## History

- 2026-08-09: Opened by the dropped-candidate close, which distinguishes a candidate that was
  dropped from an id that was never a candidate and stops there.
- 2026-08-10: Shipped ahead of its trigger, taking the area from 8 to 7 with nothing opening in
  its place.
