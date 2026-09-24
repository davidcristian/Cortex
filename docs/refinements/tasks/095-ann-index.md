# ANN index for memory search

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** `SELECT count(*) FROM memories` in a deployment's pgvector database reaching 75,000 rows
while `CORTEX_MEMORY_SCOPE` is `global`, the size at which the exact scan costs a whole recalling
turn's time to first token; the recall trail's `available` field reports the same count on every
recalled turn when `CORTEX_MEMORY_RECALL_AUDIT` is on.
**Verified:** 2026-09-24

Memory search is an exact cosine scan. An approximate index would need a migration
([ADR-0004](../../adr/ADR-0004-model-lineup.md)).

**Measured 2026-08-11.** Against the real `pgvector/pgvector:pg16` image in a scratch database,
driving `PgVectorMemoryStore.search` at the width that ships (`LIMIT 20`, no scope filter, since
`DEFAULT_RECALL_K` is 5, the judge's `recall_pool_factor` is 4, and `GlobalMemoryScope.read_scopes`
returns `None`):

- The search costs 21 ms at a thousand rows and 1,478 ms at the median at 220,000 (n=8, 1,458 to
  1,521). That is about three times the 0.515 s of time to first token measured for a whole
  recalling turn, so at that size the scan is the turn.
- The cost is per candidate, not per returned row: k=5 and k=20 measure the same. Most of it is
  detoasting, since `vector` has an `attstorage` of `e`, so every candidate is fetched out of line
  at about nine buffers a row.
- A session-scoped read never had the problem: 40 rows return in 1.3 ms at the same table size. So
  this is a fact about the default global space.
- `hnsw` at the defaults answers the same search in 5.5 ms, a factor of 268. It costs the
  dimension, because both index types need a typmod, so the column becomes `vector(768)` and stops
  being dimension-agnostic, which turns a change of `CORTEX_MODEL_FILE_EMBED` (named
  `CORTEX_EMBED_MODEL_FILE` until 2026-08-30) from a redeployment into a migration this repo has
  no runner for. It also costs recall: mean overlap with the exact answer is 0.550 at k=20, and
  the worst single query kept none of the twenty.
- `SET STORAGE PLAIN` plus a `VACUUM FULL` buys 22%, 1,154 ms against 1,478 ms, while the table
  grows from 688 MB to 924 MB, because a 3,080-byte vector stored inline fits two rows to a page.
- An `ivfflat` build at `lists=316` fails at the default 64 MB of `maintenance_work_mem`, needing
  69 MB, and nothing in the compose raises it.

The 0.550 overlap is not yet trustworthy in either direction. The corpus was 256 topic centres
over 220,000 rows, so roughly 860 near-tied neighbours surround each query, and a set-overlap
metric punishes a reordering a reader would never see. The measurement to run instead is a
score-delta calibration: how much worse in cosine terms the approximate answer is than the exact
one. That calibration is the first step of this work, on the CPU `pgvector/pgvector:pg16` image,
and its result decides between the index and scoping or retention.

The trigger depends on four settings: the pgvector backend (`CORTEX_MEMORY_BACKEND`), since the
default `none` records and recalls nothing; the global scope, since a session-scoped read ranks
one conversation; the recall trail, which is off by default, for reading the count off the log
rather than off the database; and the write policy in `record_exchange`
(`cortex_core/turn_output.py`), which records at most one memory per turn and skips tainted and
opaque turns by default, and so sets how fast the count grows.
`CORTEX_MEMORY_RECALL_POOL_FACTOR` does not move it, since k=5 and k=20 measured the same.

## History

- 2026-08-11: Measured, and the trigger was replaced rather than the entry closed. The claim
  repeated in `docker/postgres/init.sql` and `docs/modules/brain-memory.md`, that an exact scan is
  fine at personal scale, is true for months and false for years: at one memory per turn the scan
  is fine for a few months, noticeable within a year or two, and dominant after several. `hnsw` is
  268 times faster while freezing the column at one embedder width and overlapping the exact
  answer only 0.550. The old "fix when it matters" trigger was struck because it could not fire
  before the store was already too big.
- 2026-09-11: Read against the tree; the trigger has not fired. `docker/postgres/init.sql` still
  declares `embedding vector NOT NULL` with no typmod and indexes only `scope`, with a btree.
  `cortex_memory/store.py` still ranks by `embedding <=> $1::vector` under `LIMIT $2`, and the
  width is still 20, from `DEFAULT_RECALL_K = 5` in `turn_context.py`, `recall_pool_factor: int =
  4` in the orchestrator's `config.py`, and `GlobalMemoryScope.read_scopes` returning `None`. No
  compose file or brain source names `maintenance_work_mem`. No score-delta calibration has run.
  The embedder's variable name had gone stale here and was corrected to
  `CORTEX_MODEL_FILE_EMBED`.
- 2026-09-17: Read against the tree; the calibration has not run. Outside this entry and the
  2026-08-11 measurement, `hnsw` and `ivfflat` appear only in the `docker/postgres/init.sql`
  header comment and in the ADR-0008 line deferring index tuning, and no file names
  `maintenance_work_mem`. The schema, the ranked `SELECT`, `DEFAULT_RECALL_K = 5`,
  `recall_pool_factor: int = 4` and `GlobalMemoryScope.read_scopes` returning `None` are as the
  2026-09-11 reading gives them, and `scope` still defaults to `"global"` in the orchestrator's
  `MemoryConfig`. The trigger was restated as a row count, because a calibration is work somebody
  chooses to do rather than an event, and because the tree has counted the candidate set on every
  search since 2026-08-10 (`_COUNT_ALL` in `cortex_memory/store.py`, logged as `available` when
  `recall_audit` is on, which defaults to `False`). A straight line through the two measured
  sizes, 21 ms at 1,000 rows and 1,478 ms at 220,000, crosses the 0.515 s time to first token at
  about 75,000 rows. Both readings came from one machine, so the row count is that machine's
  ratio of turn time to scan time per row, and another host would take its own two readings.
- 2026-09-24: Read against the tree; the trigger has not fired and the calibration has not run.
  `docker/postgres/init.sql` has not changed since 2026-07-06, and no compose file, brain source or
  SQL file names `maintenance_work_mem`. The ranked `SELECT`, `_COUNT_ALL`, `DEFAULT_RECALL_K = 5`,
  `recall_pool_factor: int = 4`, `scope` defaulting to `"global"` and `recall_audit` to `False` are
  as above. The one change in `record_exchange` since 2026-09-17 is its comment, which now says an
  opaque turn is any turn that saw an untrusted picture; the code that skips it is unchanged.
  `hnsw` and `ivfflat` are named today in ADR-0004's decision and in
  `docs/readings/model-lineup.md`, and not in `init.sql` or ADR-0008.
