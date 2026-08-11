# Why a memory was never a candidate

**Status:** landed 2026-08-10
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

That close draws the line between "was a candidate and was dropped" and "was not a
candidate" and stops there, which is the whole of what its own entry asked for. The next question
is why an id is in neither list, and three answers the line cannot separate: the memory ranked
below the pool cutoff, its scope was not read, or it was never written. Two thirds of that is
thinner than it looks, which is why this is filed small rather than as an observability gap. The
scopes are fully determined by `CORTEX_MEMORY_SCOPE` and the `session` the line already carries
(`GlobalMemoryScope` reads everything, `SessionMemoryScope` reads that one session), and the
requested width is `k` times `CORTEX_MEMORY_RECALL_POOL_FACTOR`, so a reader holding the
deployment's config derives both and logging them would be a convenience rather than new
information. **What no reader can derive is the third that matters:** `pool_size` says how many
candidates came back, never how many there were, so a pool filled to the requested width cannot
be told from a store that held exactly that many, and a memory missing from a full line was
either cut by the cutoff or absent from the store with nothing on the line saying which.
**Cost correction ahead of time:** that half is *not* behind the unchanged port.
`MemoryStore.search` returns the top rows and reports no total, so the number would have to come
out of the store, meaning the port, both adapters, the fake, the contract test, and a count
alongside the ranked select in the pgvector one. **Trigger:** the first investigation whose
memory is not in the pool at all, or a deployment that has widened its pool and wants to know
whether it is wide enough.
**Landed 2026-08-10, and the trigger did not fire**
([ADR-0038](../../adr/ADR-0038-ranked-recall.md) candidate-count addendum). Neither arm of it: no
investigation has run and no pool has been widened. It was taken because the user asked for the
backlog to be worked and this entry's only blocker was its trigger rather than a cost argument or
an undecided question, and because the same thing that gave the close above its urgency gives
this one its, the default having moved to `judge` and left the trail thinnest where most of the
pool now disappears. That is written here rather than dressed up, a deferral taken ahead of its
trigger being a decision like any other. **The cost correction was right and the shape survived
the tree unchanged:** `MemoryStore.count_candidates(*, scopes=None) -> int` is a new verb rather
than a widened `search`, so the one production caller of `search` is untouched and only the trail
pays; the pgvector adapter runs `SELECT count(*)` under the same `WHERE scope = ANY` a scoped
search applies, the in-memory twin counts the same filtered list it would have ranked, and
`RecallAudit` carries a required `available` the sink spells out as one more key. The reading is
a comparison rather than a number: equal to `pool_size` the pool WAS the whole readable store, so
an id on neither `hits` nor `dropped` was never written or was written outside the read scopes;
below it the pool was cut and an absent memory may only have ranked under the cutoff. **One of
this entry's own claims did not hold.** The scopes half is exact (`GlobalMemoryScope` reads
`None`, `SessionMemoryScope` the one session), but the requested width is *not* `k` times the
pool factor under `CORTEX_MEMORY_RECALL=raw`, whose `candidate_k(k)` is `k` with no over-fetch,
nor on a fallback line, whose emitted basis is the fallback's while the width was the judge's.
The correction costs no field, because `available` makes the width redundant rather than merely
inferable: where it would matter it equals `pool_size`, and where it would not, nothing was cut
and it explains nothing. **The count's price was measured rather than assumed, and the
measurement inverted the worry.** An exact `count(*)` is 2.0 ms against a 520 ms ranked search
over 100k rows, because `memories_scope_idx` serves it as an index-only scan with no heap fetches
while the search detoasts every row and computes a 768-dimension distance for it; on an
unvacuumed table it rises to 22 to 31 ms and is still under 6%. So a cap was declined for saving
nothing worth the weaker answer, and the shape that needs no second read was declined for costing
**2.85x the plain search**: `count(*) OVER ()` puts a `WindowAgg` under the `Limit` that
materializes all 100,000 rows, `embedding::text` included, before the top-20 heapsort can discard
them, and at 20k rows that is invisible, which is how it would have shipped looking free. The
count is issued only inside the `audit is not None` guard, so an unaudited recall runs no
counting query at all, and it runs next to the search rather than after the rank, two reads not
being one transaction with a second of model time available to sit between them. **Distrust
green:** eight mutations, six in CI and two against real Postgres, each reddening only what it
should, and the first of them had to be *fixed* rather than watched: the contract check was
written with three memories, which any count capped at three or more passes, and it caught a
cutoff-capped count only once it held more memories than the widest pool a shipped deployment
fetches. **It also closed a gate that was only half a gate**: `memory_contract.ALL_CHECKS` was
driven solely by the live pgvector run, so a check added to the shared file reached CI only if
someone wrote it a second time by hand, and a count faked as a length over rows is exactly what
that would have hidden; the fake now runs the same file in CI. Verified live in the
`cortex_contract` database (1 passed, 39 deselected), where the `len(rows)` mutation reddens the
count check on 20 against 25. **Opens nothing:** the two derivable causes are answered by not
building them rather than filed, and an exact count leaves no bound to revisit.

## Trail

- 2026-08-09: Opened by the dropped-candidate close, which draws the line between a candidate that
  was dropped and an id that was never a candidate and stops there.
- 2026-08-10: Landed ahead of its trigger, neither arm of which had fired, taking the area from 8 to
  7 with nothing opening in its place. `MemoryStore.count_candidates(*, scopes=None)` is a new verb
  beside `search` rather than a widened one, so the single production caller of `search` is
  untouched and only the trail pays. An exact count is the cheap design rather than the expensive
  one, an index-only `count(*)` costing 2.0 ms against a 520 ms ranked search where folding the
  total into that select would have cost 2.85 times it. One of the entry's own claims failed against
  the tree, the requested width not being `k` times the pool factor under `raw` or on a fallback
  line, which costs no field because the count makes the width redundant.
