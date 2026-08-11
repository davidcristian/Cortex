# Runbook for memory on Postgres + pgvector (Slice 5 host half)

Bring up the durable memory store and validate the pgvector adapter against it. This is the
**host-driven** half of Slice 5: the CI half (the adapter, the embedder adapter, the wiring,
100%-covered without a DB) is built and gated; here you run it against real Postgres. Design:
[ADR-0008](../adr/ADR-0008-memory-v1.md); module: [brain-memory.md](../modules/brain-memory.md).
CI never runs any of this (service-free by design, AGENTS.md gate 3).

## Bring up Postgres (enough for the memory adapter)

The memory contract test needs **only Postgres** (it builds embeddings by hand, with no
embedder). From the repo root:

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d postgres
```

`docker/postgres/init.sql` creates the `vector` extension and the `memories` table on first
init, and `docker/postgres/live-contract-db.sql` creates the `cortex_contract` database the
integration test below owns, applying that same file to it. Data lives in the `cortex-pgdata`
named volume (not a Windows bind mount, ADR-0008).

- **Sanity poke** (loopback publish on `127.0.0.1:5432`):
  `docker compose ... exec postgres psql -U cortex -d cortex -c '\dx vector'`.
- **From WSL** (automount/interop off): same drvfs + `DOCKER_CONFIG` one-time steps as the
  [llama.cpp runbook](llamacpp-gpu.md). The models mount only matters for the embedder below.

## Run the memory integration test

```
cd brain && CORTEX_MEMORY_DSN=postgresql://cortex:cortex@127.0.0.1:5432/cortex \
  uv run pytest -m integration --no-cov packages/memory
```

`--no-cov` matters. The 100% gate in the workspace addopts would otherwise fail the run.
This runs the full `MemoryStore` contract (empty search, cosine ranking, top-k, roundtrip
fidelity including the `scope`, and scope-filter isolation/union) against real pgvector,
proving the adapter's SQL, which CI's canned-row fake cannot.

**Give it the DSN of the brain's database, not of its own.** The run redirects onto
`cortex_contract` itself (`brain/packages/memory/tests/live_postgres.py`), which it empties before
the suite and after every check, so your memories are never read, written, or deleted and the two
checks that assert over the whole table (`check_empty_search` wants `search(k=5)` empty,
`check_ranks_by_similarity` an exact top-2) hold however much the brain has remembered. That is
the Redis suites' logical database in the form Postgres has for it (ADR-0002 addendum on the live
pgvector database). Pointing `CORTEX_MEMORY_DSN` at `cortex_contract` fails the run rather than
running there, since that would aim the brain at the database the suite empties.

**If the run refuses to start** with `the cortex_contract database is missing or unbootstrapped`,
your data dir predates that database: an initdb script never re-runs on an existing volume. Create
it once, with the same bootstrap file, which stays mounted in the container after init:

```
docker compose ... exec postgres psql -U cortex -d cortex -c 'CREATE DATABASE cortex_contract;'
docker compose ... exec postgres psql -U cortex -d cortex_contract -f /docker-entrypoint-initdb.d/init.sql
```

It holds nothing but the suite's own rows, so dropping it costs nothing;
`pg-backup` dumps `-d cortex` only, and never exports it.

## Setting any of these on the dockerized brain

Every `CORTEX_MEMORY_*` knob below is a **pass-through** on the memory override, meaning
`docker/docker-compose.memory.yml` names it under `brain.environment` with no value. A bare key is
compose's pass-through: set on the host it reaches the container, left unset it never enters the
container at all, so each shipped default stays declared once in `MemoryConfig` rather than being
restated in YAML where it could drift. Put them in the repo-root `.env` or in front of the command:

```
CORTEX_MEMORY_RECALL=raw CORTEX_MEMORY_RECALL_AUDIT=1 docker compose --project-directory . \
  -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d
```

To change one on a running stack, recreate **only** the brain and leave Postgres, the embedder and
any loaded model where they are. `docker compose restart brain` will not do: it reuses the existing
container and so keeps the old environment.

```
CORTEX_MEMORY_RECALL=raw docker compose --project-directory . \
  -f docker/docker-compose.yml -f docker/docker-compose.memory.yml \
  up -d --no-deps --force-recreate brain
```

Before 2026-08-09 none of these reached the dockerized brain at all: the override set the backend,
the DSN and the embedder endpoint and nothing else, so this runbook documented variables an
operator running the stack in Docker had no way to supply. The pass-through block landed with the
turn-cost harness (ADR-0038 harness addendum), which needs exactly this restart between arms.

## Memory scoping (ADR-0008 scoping addendum)

Recall is **global by default** (`CORTEX_MEMORY_SCOPE=global`). Memories are one shared space
across every conversation, the founding "retrieval that grows" behavior. Set
`CORTEX_MEMORY_SCOPE=session` to isolate each conversation: a memory recorded in one session is
never recalled in another (`search` filters on `scope = ANY(read-scopes)`). It applies only when
`CORTEX_MEMORY_BACKEND=pgvector`; the policy is selected at the composition root, never in the core.

## Recall ranking and its trail (`CORTEX_MEMORY_RECALL`, ADR-0008 and ADR-0038)

`judge` **is the default** since the ADR-0038 turn-cost addendum: the model rank hands the
over-fetched pool to the resident cortex and takes back an ordering, so a recalling turn spends one
bounded cortex generation before it answers and the GPU stack has to be up. It falls back to raw
cosine whenever the model cannot be reached or believed, and the fallback is visible rather than
silent, because the trail records the basis that actually ranked. **What it costs, measured over 48
real turns an arm on the 24 GB card:** the rank alone is 0.877 s at the pool a turn asks for (`k` 5
at `pool_factor` 4, so 20 candidates), and a turn's time to first token rises 0.515 s (95% CI 0.116
to 0.915) rather than the full 0.877 s, because a rank that keeps 1.17 notes gives the reply a
smaller memory block to read than the cosine's 5. It is paid on every recalling turn; nothing
caches a rank, unlike the history fold.

Reproduced 2026-08-09 by the committed harness below at 0.539 s (95% CI 0.054 to 1.111) against a
control arm whose interval spans zero, on a different day and a driver rebuilt from that addendum's
prose. The same run puts the whole-turn cost at 0.979 s rather than the 0.526 s first published, and
locates nearly all of the excess in the question memory cannot answer: when the rank declines, the
turn carries no memory block and the model says at length that it does not know, where the cosine's
five nearest misses give it something short to say.

`raw` is top-`k` cosine exactly as it always was, and is now the **opt-out**: set
`CORTEX_MEMORY_RECALL=raw` for the founding behavior, on a stack with no GPU, or to take that half
second back. `reranked`, `mmr` and `recency_mmr` are the heuristic policies, tuned by the
`CORTEX_MEMORY_RECALL_*` knobs.

`judge` is also the only policy that can **return nothing**. Asked a question none of the candidates
answers, it says so and the turn is assembled with no recalled memories at all, which the trail
reports as the `demur` basis with an empty hit list (ADR-0038 abstention addendum). That is a
different line from a fallback, which shows the fallback's basis and the notes it chose, and from an
empty pool, which shows the ranking policy's own basis. The geometric policies have no way to
decline: they always return their nearest `k`, so under `raw` a question memory cannot answer still
recalls the three least-unrelated notes it holds. **That is a property of ranking by distance and
not a gap waiting to be filled**, so setting `CORTEX_MEMORY_RECALL=raw` is an opt-out of the
refusal as much as of the rank. A similarity floor was the obvious way to give geometry a refusal
and was calibrated on the real embedder before being declined (ADR-0038 relevance-floor addendum):
over the 41-note corpus the questions memory can answer and the questions it cannot overlap on
cosine, so every floor that silences the second silences the first, worst of all where a note
answers in words the question never used. Reproduce or reopen it behind another embedding model
with `packages/inference/tests/test_recall_floor_live.py`, which needs only the CPU embedder below.

Set `CORTEX_MEMORY_RECALL_AUDIT=1` to turn that trail on: one `cortex.memory.recall` line per
recall, in the brain's container logs, carrying the pool size, how many candidates were available
to it, the rank basis, whether keys on that
basis may be compared, and each kept hit's memory id, cosine score and rank key. It never carries
text, neither the query nor a recalled memory, so a line names *which* memories came back and never
what they said; pair an id with the `memories` table when you need the content. This is the answer
to "why did recall return these?", which used to need a throwaway script against the store.

The same line answers the harder question, "why did it not remember X?". `dropped` names every
candidate the store offered and the rank did not keep, by memory id and by the store's cosine, so
an id that appears there was read and passed over while an id in neither `hits` nor `dropped` was
never a candidate at all. That distinction matters most under the shipped default, since a judge
rank returns about one note where the cosine returned five, so most of the pool disappears on a
normal turn. Two things to read carefully. A dropped candidate carries **no rank key**, because a
rank has an opinion only about what it kept and the judge leaves an unhelpful note out of its order
rather than scoring it low, so the line says what was available and not why the rank declined it.
And the list is bounded at 20, which is the whole pool a default deployment ever fetches (a recall
of five at a pool factor of four): `dropped_omitted` says how many more there were, and it reads 0
unless you have widened `CORTEX_MEMORY_RECALL_POOL_FACTOR` past what ships.

`available` is what turns "never a candidate" from a name into a reading. It is the store's own
count of the namespaces this recall was allowed to read, so compare it with `pool`:

| Line | What it means | Where to look next |
| --- | --- | --- |
| `pool` equals `available` | The pool WAS everything readable. Nothing was cut. | The memory was never written, or it was written outside the read scopes. Check `scope` in the `memories` table. |
| `pool` below `available` | The pool stopped at its requested width and the rest of the store went unseen. | The memory may simply have ranked below the cut. Widen `CORTEX_MEMORY_RECALL_POOL_FACTOR` and recall again. |

That is also how to answer "is my pool wide enough": `available` says what share of the readable
store a recall actually looks at, and a deployment that has widened its factor can watch the gap
close. The requested width itself is not logged, because it needs no line of its own: where it
matters it is exactly `pool`, and where it does not it explains nothing.

The count is a second statement against Postgres rather than part of the ranked `SELECT`, and it
is issued **only** when this trail is on, so leaving the audit off costs a recall nothing at all.
It is cheap when on: it reads the `memories_scope_idx` btree as an index-only scan and never
touches the embeddings, which measured about 2 ms against a 520 ms search over 100k rows, rising
to roughly 25 ms on a table whose recent writes autovacuum has not yet caught up with. Because the
count and the search are two reads and not one transaction, a `pool` above `available` is possible
in principle and means only that a namespace was deleted between them.

    docker compose --project-directory . -f docker/docker-compose.yml \
      -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml logs -f brain \
      | grep memory.recall

## Measuring what an arm costs a whole turn (ADR-0038 harness addendum)

The numbers above came from real turns through the seam, and the harness that produced them is in
the repo:

```
CORTEX_MODELS_DIR=/path/to/models just turn-cost
```

That brings up the gpu plus memory stacks and runs **three blocks in A/B/A order**, `raw` then
`judge` then `raw`, recreating only the brain between them with `CORTEX_MEMORY_RECALL` changed and
`CORTEX_MEMORY_SCOPE=session` plus `CORTEX_MEMORY_RECALL_AUDIT=1` on throughout. Each block runs
`packages/orchestrator/tests/test_turn_cost_live.py`, which opens one `Converse` stream per turn
against a fresh session whose scope it pre-seeds with the whole 41-note recall corpus, times the
first `TextDelta` and the `TurnComplete`, and writes its sample to `measurements/`. The recipe then
runs `scripts/contrast.py` over the three samples and prints the blocked paired bootstrap. The two
outer blocks are the control: same configuration, different times, so their contrast is the noise
floor the middle one has to clear. Roughly 15 minutes at the default of eight repetitions.

`just turn-cost mmr raw 4` measures a different arm, and `just turn-cost judge judge` makes both
outer blocks match the middle one, which is the null run to reach for when the harness itself is
what is in doubt. Nothing is torn down at the end, so `docker compose ... logs brain | grep
memory.recall` still holds the trail for the last block. The samples in `measurements/` are
gitignored: they are evidence of one run on one machine, and the reading they support belongs in an
ADR addendum.

## Tainted-turn recording (`CORTEX_MEMORY_ON_TAINTED`, ADR-0019)

A turn that reads untrusted content is dropped from memory by default (`skip`), so every stored
memory is trusted. Set `CORTEX_MEMORY_ON_TAINTED=record` to preserve that context instead: the
exchange is recorded with the `tainted` marker, and recall **fences** it (and re-taints the turn)
so it can only re-enter as data, never trusted context. The knob governs only *writing*. A stored
tainted memory is always fenced on recall regardless. It applies only when
`CORTEX_MEMORY_BACKEND=pgvector`; the string maps to a bool at the composition root, never in the
core.

**Upgrading an existing DB.** `docker/postgres/init.sql` only runs on a *fresh* data dir, so a
volume created before these addenda lacks the `scope` and/or `tainted` columns. Add them in place as
each column's `DEFAULT` back-fills every existing row (into the global space / as trusted, since
old rows were only ever written by untainted turns), so recall is unchanged until you opt into
`session` scoping or `record` recording:

```
docker compose ... exec postgres psql -U cortex -d cortex -c \
  "ALTER TABLE memories ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT 'global'; \
   ALTER TABLE memories ADD COLUMN IF NOT EXISTS tainted boolean NOT NULL DEFAULT false; \
   CREATE INDEX IF NOT EXISTS memories_scope_idx ON memories (scope);"
```

An existing volume now has **two** databases holding that table, so run the same statements
against `-d cortex_contract` as well, or drop and re-create it from `init.sql`; the contract run
tests the adapter against whatever schema it finds there.

## Bring up the CPU embedder (for the end-to-end path)

The embedder needs the nomic GGUF present under the models dir. Set `CORTEX_MODELS_DIR` (WSL:
`/srv/models`) and `CORTEX_EMBED_MODEL_FILE` (the nomic pick's path under it), then:

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d llama-embed
cd brain && CORTEX_EMBEDDING_ENDPOINT=http://127.0.0.1:8081 \
  uv run pytest -m integration --no-cov packages/embedding
```

- **Healthcheck:** if the CPU `server` image ships without `curl`, the healthcheck stays
  unhealthy though the server is up. Watch `docker compose logs llama-embed` for the
  `listening on http` line, or swap the compose test for a `python -c` poke.
- With both up, `docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up` runs
  the brain with `CORTEX_MEMORY_BACKEND=pgvector`, so turns recall + record for real.

## The nomic pick (validated 2026-06-29)

**nomic-embed-text-v1.5 Q8_0** (768-dim, ~146 MB) is the compose default and the validated
pick. It loads in ~1.2 s on CPU with negligible RAM. `nomic-embed-text-v2-moe` (also
768-dim, larger, multilingual) is the alternative via `CORTEX_EMBED_MODEL_FILE`. Recorded in
the [ADR-0004 addendum](../adr/ADR-0004-model-lineup.md). The `memories.embedding` column is
dimension-agnostic, so switching needs no migration.

## Plug-and-play export (ADR-0008)

The durable data is a named volume, not a raw `D:\Software\AI\Database` bind mount (Postgres
PGDATA over a Windows bind mount has ownership/latency pitfalls). The plug-and-play guarantee
is the **`pg-backup` sidecar** (in `docker-compose.memory.yml`, script
`docker/postgres/backup.sh`): it `pg_dump`s into `CORTEX_DB_DIR` (default
`./pgdata`; WSL: `/srv/pgdata`) immediately on start and then every
`CORTEX_DB_SYNC_INTERVAL_S` seconds (default 6 h), writing `cortex.dump` atomically and
keeping the prior dump as `cortex-previous.dump`. It starts with the stack:

```
CORTEX_DB_DIR=/srv/pgdata \
  docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d postgres pg-backup
ls /srv/pgdata   # cortex.dump appears after the first tick; watch: docker compose logs pg-backup
```

Restore with `pg_restore -U cortex -d cortex /path/to/cortex.dump`. A one-off manual dump
remains available (`docker compose ... exec postgres pg_dump -U cortex -d cortex -Fc -f
/tmp/cortex.dump`, then copy it out) but the guarantee no longer depends on remembering it.
Validating a direct PGDATA bind mount as a nice-to-have (not the default) is optional, and is
tracked as an optional user check in
[docs/host/index.md#windows-desktop](../host/index.md#windows-desktop); no procedure exists for it yet.

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml down
```

Add `-v` to also drop the `cortex-pgdata` volume (wipes the memory store).
