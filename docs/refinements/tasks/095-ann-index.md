# ANN index for memory search

**Status:** open, fix when it bites
**Area:** memory
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** `SELECT count(*) FROM memories` in a deployment's pgvector database reaching 75,000 rows
while `CORTEX_MEMORY_SCOPE` is `global`, the size at which the exact scan costs a whole recalling
turn's time to first token; the recall trail's `available` field carries the same count on every
recalled turn when `CORTEX_MEMORY_RECALL_AUDIT` is on.
**Verified:** 2026-09-17

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
`CORTEX_MODEL_FILE_EMBED` (spelled `CORTEX_EMBED_MODEL_FILE` until 2026-08-30) from a
redeployment into a migration this repo has no runner for. And it
costs recall: **mean overlap with the exact answer is 0.550 at k=20, and the worst single query
kept none of the twenty**. That number is not yet trustworthy in either direction, which is the
finding this entry now turns on. The corpus was 256 topic centres over 220,000 rows, so roughly
860 near-tied neighbours surround each query and a set-overlap metric punishes a reordering a
reader would never see. **Set overlap was the wrong measurement to run and it is the one that was
run.** A third option was measured and does not rescue the exact scan: `SET STORAGE PLAIN` plus a
`VACUUM FULL` buys 22%, 1,154 ms against 1,478 ms, while the table grows from 688 MB to 924 MB,
because a 3,080-byte vector inline fits two rows to a page. One operational fact for whoever picks
this up: an `ivfflat` build at `lists=316` fails at the default 64 MB of `maintenance_work_mem`,
needing 69 MB, and nothing in the compose raises it. **New trigger, replacing "when it bites",
which could not fire before the store was already too big:** a score-delta calibration, meaning
how much worse in cosine terms the approximate answer is than the exact one rather than how many
ids the two share, over a corpus with realistic topic spread. If the delta is negligible the index
is worth its migration and this entry lands; if it is not, the entry closes as declined and the
answer to a slow scan is scoping or retention rather than approximation.

**Restated 2026-09-17: the calibration is the first step of the work, and the trigger is the size
at which the work is owed.** "A score-delta calibration" names nothing that happens by itself, so
it could fire only when somebody chose to do this entry. The 2026-08-11 objection to a size trigger
was that the scan's cost shows only once the table is already too big to migrate comfortably. The
tree has read the size since 2026-08-10: `PgVectorMemoryStore.count_candidates` runs a
`count(*)` beside every search, and the recall trail logs it as `available`. So the trigger now
fires on the size, before the cost dominates. A straight line through the two measured sizes, 21 ms
at 1,000 rows and 1,478 ms at 220,000, crosses the 0.515 s time to first token at about 75,000
rows. Both readings were taken on one machine, so the row count is that machine's ratio of turn
time to scan time per row; another host would read its own two numbers. When the trigger fires, the
next step is the calibration, on the CPU `pgvector/pgvector:pg16` image, and its result decides
between the index and scoping or retention. The trigger depends on four settings: the pgvector
backend (`CORTEX_MEMORY_BACKEND`), because the default `none` records and recalls nothing; the
global scope,
because a session-scoped read ranks one conversation, measured at 40 rows and 1.3 ms; the recall
trail, which is off by default, for reading the count off the log rather than off the database; and
the write policy in `record_exchange` (`cortex_core/turn_output.py`), which records at most one
memory per turn and skips tainted and opaque turns by default, and so sets how fast the count grows. `CORTEX_MEMORY_RECALL_POOL_FACTOR` does not move it, since k=5 and k=20 measured the same.

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
- 2026-09-11: read against the tree and the trigger has not fired. `docker/postgres/init.sql` still
  declares `embedding vector NOT NULL` with no typmod and indexes only `scope`, with a btree;
  `cortex_memory/store.py` still ranks by `embedding <=> $1::vector` under `LIMIT $2`, and the width
  it ships is still 20, from `DEFAULT_RECALL_K = 5` in `turn_context.py`, `recall_pool_factor: int
  = 4` in the orchestrator's `config.py` and `GlobalMemoryScope.read_scopes` returning `None`. No
  compose file or brain source spells `maintenance_work_mem`. No score-delta calibration has run:
  the only mentions of one are the 2026-08-11 addendum's, and no addendum on that record since
  names `hnsw` or `ivfflat`. One name in the body had gone stale, the embedder's variable, which was
  renamed to `CORTEX_MODEL_FILE_EMBED` on 2026-08-30, and it is corrected above.
- 2026-09-17: read against the tree, and the calibration has not run: outside this entry and the
  2026-08-11 addendum, `hnsw` and `ivfflat` appear only in the `docker/postgres/init.sql` header
  comment and in the ADR-0008 line deferring index tuning, and no file spells
  `maintenance_work_mem`. The schema, the ranked `SELECT`, `DEFAULT_RECALL_K = 5`,
  `recall_pool_factor: int = 4` and `GlobalMemoryScope.read_scopes` returning `None` are as the
  2026-09-11 reading gives them, and `scope` still defaults to `"global"` in the orchestrator's
  `MemoryConfig`. The trigger was restated, because a calibration is work somebody chooses to do
  and not an event, and because the tree has counted the candidate set on every search since
  2026-08-10 (`_COUNT_ALL` in `cortex_memory/store.py`, logged as `available` when
  `recall_audit` is on, which defaults to `False`). Nothing in the tree times the search itself,
  so the size is the reading to take. The new trigger is a row count derived above from the
  2026-08-11 measurement.
