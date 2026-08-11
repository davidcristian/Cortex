# ANN index for memory search

**Status:** open, fix when it bites
**Area:** memory
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** A score-delta calibration over a corpus with realistic topic spread.

Exact cosine now; an approximate index would need a migration, per
[ADR-0004](../../adr/ADR-0004-model-lineup.md).
**Measured 2026-08-11 and re-triggered rather than closed** ([ADR-0004](../../adr/ADR-0004-model-lineup.md)
ANN-index addendum). The measurement was run because this entry's reason for existing, repeated
in `docker/postgres/init.sql` and `docs/modules/brain-memory.md`, was that an exact scan is fine
at personal scale, and nobody had put a number on personal scale. **Half of that claim is false.**
Against the real `pgvector/pgvector:pg16` image, in a scratch database of its own, driving
`PgVectorMemoryStore.search` rather than hand-written SQL and at the width that actually ships
(`LIMIT 20`, no scope filter, since `DEFAULT_RECALL_K` is 5, the judge's `recall_pool_factor` is
4, and `GlobalMemoryScope.read_scopes` returns `None`), the search costs 21 ms at a thousand rows
and **1,478 ms at the median at 220,000** (n=8, 1,458 to 1,521). That is about three times the
0.515 s of time to first token this area measured for a whole recalling turn, so the scan is the
turn at that size. At one memory per turn, which is what the v1 write policy records, the shape
is: fine for a few months, noticeable within a year or two, dominant after several. The cost is
per candidate and not per returned row, k=5 and k=20 measuring the same, and it is mostly
detoasting, `vector` carrying an `attstorage` of `e` so every candidate is fetched out of line at
about nine buffers a row. A session-scoped read never had the problem at all, 40 rows answering in
1.3 ms at the same table size, so this is a fact about the default global space.
**The other half held, and it is why nothing shipped.** `hnsw` at the defaults answers the same
search in 5.5 ms, a factor of 268, and costs two things. It costs the dimension: both index types
need a typmod, so the column becomes `vector(768)` and stops being the dimension-agnostic thing
[ADR-0004](../../adr/ADR-0004-model-lineup.md) decided it should be, which turns changing
`CORTEX_EMBED_MODEL_FILE` from a redeployment into a migration this repo has no runner for. And it
costs recall: **mean overlap with the exact answer is 0.550 at k=20, and the worst single query
kept none of the twenty**. That number is not yet trustworthy in either direction, which is the
finding this entry now turns on. The corpus was 256 topic centres over 220,000 rows, so roughly
860 near-tied neighbours surround each query and a set-overlap metric punishes a reordering a
reader would never see. **Set overlap was the wrong measurement to run and it is the one that was
run.** A third option was measured and does not rescue the exact scan: `SET STORAGE PLAIN` plus a
`VACUUM FULL` buys 22%, 1,154 ms against 1,478 ms, while the table grows from 688 MB to 924 MB,
because a 3,080-byte vector inline fits two rows to a page. One operational fact for whoever picks
this up: an `ivfflat` build at `lists=316` refuses at the default 64 MB of `maintenance_work_mem`,
needing 69 MB, and nothing in the compose raises it. **New trigger, replacing "when it bites",
which could not fire before the store was already too big:** a score-delta calibration, meaning
how much worse in cosine terms the approximate answer is than the exact one rather than how many
ids the two share, over a corpus with realistic topic spread. If the delta is negligible the index
is worth its migration and this entry lands; if it is not, the entry closes as declined and the
answer to a slow scan is scoping or retention rather than approximation.

## Trail

- 2026-08-11: Measured and re-triggered rather than closed, which the area names explicitly because
  a count that does not move is where a measurement changing an entry's whole reason would otherwise
  hide. The shipped search costs 21 ms over a thousand rows and 1,478 ms over 220,000, about three
  times the 0.515 s of time to first token this area measured for a whole recalling turn, so "exact
  search is fine at personal scale" is true for months and false for years. `hnsw` answers the same
  search 268 times faster while freezing the column at one embedder width and overlapping the exact
  answer only 0.550. The entry survives because set overlap punishes a reordering among the roughly
  860 near-tied neighbours the corpus put around each query, so the trigger is now a score-delta
  calibration and the old "when it bites" is struck as unfireable.
