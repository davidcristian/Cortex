# Runbook: memory on Postgres and pgvector

Bring up the durable memory store and check the pgvector adapter against it. CI never runs any of
this, because CI runs no services. Design: [ADR-0008](../adr/ADR-0008-memory-v1.md).

## Bring up Postgres

The memory contract test needs only Postgres; it builds embeddings by hand, with no embedder.

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d postgres
```

`docker/postgres/init.sql` creates the `vector` extension and the `memories` table on first init,
and `docker/postgres/live-contract-db.sql` creates the `cortex_contract` database the integration
test owns. Data lives in the `cortex-pgdata` named volume, not a Windows bind mount. Check it with
`docker compose ... exec postgres psql -U cortex -d cortex -c '\dx vector'`; the loopback publish
is `127.0.0.1:5432`. From WSL with automount and interop off, the same drvfs and `DOCKER_CONFIG`
steps as [llamacpp-gpu.md](llamacpp-gpu.md) apply.

## Run the memory integration test

```
cd brain && CORTEX_MEMORY_DSN=postgresql://cortex:cortex@127.0.0.1:5432/cortex \
  uv run pytest -m integration --no-cov packages/memory
```

`--no-cov` is required, or the workspace's 100% coverage threshold fails the run. This runs the
full `MemoryStore` contract (empty search, cosine ranking, top-k, roundtrip fidelity including the
`scope`, and scope-filter isolation and union) against real pgvector, which CI's canned-row fake
cannot do. **Give it the DSN of the brain's database, not of its own.** The run redirects onto
`cortex_contract` itself, which it empties before the suite and after every check, so your
memories are never touched and the two checks that assert over the whole table hold however much
the brain has remembered. Pointing `CORTEX_MEMORY_DSN` at `cortex_contract` fails the run.

**If the run fails at startup** with `the cortex_contract database is missing or unbootstrapped`,
your data directory predates that database, since an initdb script never re-runs on an existing
volume. Create it once with the same bootstrap file, still mounted after init:

```
docker compose ... exec postgres psql -U cortex -d cortex -c 'CREATE DATABASE cortex_contract;'
docker compose ... exec postgres psql -U cortex -d cortex_contract -f /docker-entrypoint-initdb.d/init.sql
```

It holds nothing but the suite's own rows, so dropping it costs nothing, and `pg-backup` never
exports it.

## Setting a memory variable on the dockerized brain

Every `CORTEX_MEMORY_*` setting below is passed through: `docker/docker-compose.memory.yml` names
it under `brain.environment` with no value, so set on the host it reaches the container and left
unset it never enters the container. Put them in the repo-root `.env` or in front of the command:

```
CORTEX_MEMORY_RECALL=raw CORTEX_MEMORY_RECALL_AUDIT=1 docker compose --project-directory . \
  -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d
```

To change one on a running stack, recreate only the brain and leave Postgres, the embedder and
any loaded model where they are. `docker compose restart brain` will not do, since it reuses the
container and so keeps the old environment.

```
CORTEX_MEMORY_RECALL=raw docker compose --project-directory . \
  -f docker/docker-compose.yml -f docker/docker-compose.memory.yml \
  up -d --no-deps --force-recreate brain
```

## The password the DSN can include

`CORTEX_PG_PASSWORD` reaches Postgres twice, once as the server's own password and once inside
`CORTEX_MEMORY_DSN`, where it has to be percent-encoded. A password containing a character that
ends a URL's authority, `/` above all, makes the driver read the password's first segment as a
port, which the brain refuses at boot:

```
cortex_orchestrator.config.MemoryConfigError: CORTEX_MEMORY_DSN has an authority the Postgres
driver cannot read; percent-encode any password character that would end a URL's authority
```

Percent-encode the character (`/` is `%2F`) in the DSN and leave `POSTGRES_PASSWORD` as raw text.
The check repeats three of `asyncpg`'s own parsing steps rather than calling it, since the driver
reads the DSN inside `create_pool`. After a driver upgrade, take that reading again:

```
cd brain && .venv/bin/python -c "import asyncio, asyncpg; \
  asyncio.run(asyncpg.create_pool('postgresql://cortex:hun/ter@postgres:5432/cortex'))"
```

On 0.31.0 that raises `ValueError: invalid literal for int() with base 10: 'hun'`, the password's
first segment and nothing else. An upgrade that fails differently, or at connection time, is a
driver whose parse `dsn.py` no longer mirrors.

## Memory scoping

Recall is global by default (`CORTEX_MEMORY_SCOPE=global`), so memories are one shared space
across every conversation. `CORTEX_MEMORY_SCOPE=session` isolates each conversation: a memory
recorded in one session is never recalled in another. It applies only when
`CORTEX_MEMORY_BACKEND=pgvector`.

Changing the setting does not move a memory already stored. Each row keeps the scope it was
recorded under, and rows older than the scope column were back-filled into `global`. So a store
that ran under `global` and is then set to `session` keeps every earlier memory in `global`, where
session recall never reads it and deleting a session never removes it, and setting `global` over a
store that ran under `session` makes every conversation's private memories recallable from every
other conversation.

## When a recall is not ranked, and how to read the audit line

What each policy does and costs: [memory-measurements.md](memory-measurements.md). A judge that
falls back says so even with the audit off, warning in the brain's container logs whenever
something stops it ranking:

    docker compose --project-directory . -f docker/docker-compose.yml \
      -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml logs brain \
      | grep "unjudged ranking"

Which of the two lines arrives is most of the diagnosis. `the model could not be asked to rank
recall` is the backend: the cortex is not serving or the model host is down, and the traceback
under the line says which. `the model returned no usable recall order` is a reply that could not
be read as an order, and two of its fields split the causes apart:

| Reading | What happened | Where to look next |
| --- | --- | --- |
| `capped=True` | The reply ran out of tokens mid-envelope, so it is not JSON at all. | Recall fewer notes, or widen the rank bound (`RANK_ENVELOPE_TOKENS` and `RANK_TOKENS_PER_CANDIDATE` in `rerank_judge.py`). |
| `capped=False chars=0` | The model emitted no answer text at all, which on this path means a tier that ignored the request to skip thinking and put the whole reply in its reasoning. | The model's own chat template, and the thinking switch the inference adapter sends with the request. |
| `capped=False` and `chars` above zero | Text arrived and was not the envelope, so constrained decoding did not hold. | Whether the llama-server build honours the JSON schema in the rank request. |

Fields render in name order, so those two arrive adjacently as `capped=True chars=0`. Both lines
also name `pool`, the candidates that went unjudged, `k`, the width asked of the rank, and
`session_id`, the conversation the recall was for, written the way the audit line below writes it,
so a fallback and the audit line for one recall are joined by
`grep "session_id=<id>"` on one stream. `session_id=None` means the port was called by something
that named no conversation, which nothing in the shipped brain does. Both lines name
`turn_id` too, and so does the audit line, so
`grep "turn_id=<id>"` returns the one audit line the fallback belongs to. No such line at all
means the rank is working.

Set `CORTEX_MEMORY_RECALL_AUDIT=1` to turn the audit on: one `cortex.memory.recall` line per
recall, in the brain's container logs, with the conversation and turn it was made for, the pool
size, how many candidates were available to it, the rank basis, whether keys on that basis may be
compared, and each kept hit's memory id, cosine score and rank key. It is a bare
`memory.recall` message followed by those as `key=value` fields, with `hits` and `dropped` as
compact JSON inside their own field, so one line is both readable and pasteable into `jq`
(`CORTEX_LOG_FORMAT=packed` makes the whole line one JSON object; see
[brain-logs.md](brain-logs.md)). It never includes text, so a line names which memories came
back and never what they said; pair an id with the `memories` table for the content.

    docker compose --project-directory . -f docker/docker-compose.yml \
      -f docker/docker-compose.gpu.yml -f docker/docker-compose.memory.yml logs -f brain \
      | grep memory.recall

The same line answers the harder question, "why did it not remember X?".
`dropped` names every candidate the store offered and the rank did not keep, by memory id and by
the store's cosine, so an id that appears there was read and passed over while an id in neither
`hits` nor `dropped` was never a candidate at all. A dropped candidate has no rank key, because a
rank key is assigned only to what the rank kept, so the line says what was available and not why
the rank declined it. The list is bounded at 20, the whole pool a default deployment fetches;
`dropped_omitted` says how many more there were.

`available` is the store's own count of the namespaces this recall was allowed to read, which is
what makes "never a candidate" readable off the line. Compare it with `pool`:

| Line | What it means | Where to look next |
| --- | --- | --- |
| `pool` equals `available` | The pool was everything readable. Nothing was cut. | The memory was never written, or it was written outside the read scopes. Check `scope` in the `memories` table. |
| `pool` below `available` | The pool stopped at its requested width and the rest of the store went unseen. | The memory may simply have ranked below the cut. Widen `CORTEX_MEMORY_RECALL_POOL_FACTOR` and recall again. |

The count is a second statement against Postgres, issued only when the audit is on, so leaving it
off costs a recall nothing. It is an index-only scan of `memories_scope_idx` and never touches the
embeddings: about 2 ms against a 520 ms search over 100k rows, up to roughly 25 ms when autovacuum
is behind. Count and search are two reads rather than one transaction, so a `pool` above
`available` means only that a namespace was deleted between them.

## Tainted-turn recording

A turn that reads untrusted content is dropped from memory by default
(`CORTEX_MEMORY_ON_TAINTED=skip`), so every stored memory is trusted. Set it to `record` to keep
that context instead: the exchange is recorded with the `tainted` marker, and recall fences it and
re-taints the turn, so it can only re-enter as data. The setting governs only writing, since a
stored tainted memory is always fenced on recall, and it applies only when
`CORTEX_MEMORY_BACKEND=pgvector`.

**Upgrading an existing database.** `docker/postgres/init.sql` only runs on a fresh data
directory, so a volume created before the `scope` and `tainted` columns existed lacks one or both.
Add them in place; each column's `DEFAULT` back-fills every existing row, into the global space
and as trusted, so recall is unchanged until you opt into one of those settings:

```
docker compose ... exec postgres psql -U cortex -d cortex -c \
  "ALTER TABLE memories ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT 'global'; \
   ALTER TABLE memories ADD COLUMN IF NOT EXISTS tainted boolean NOT NULL DEFAULT false; \
   CREATE INDEX IF NOT EXISTS memories_scope_idx ON memories (scope);"
```

An existing volume has two databases holding that table, so run the same statements against
`-d cortex_contract` too, or drop and re-create it from `init.sql`.

## Bring up the CPU embedder

The embedder needs the nomic GGUF under the models directory, so set `CORTEX_MODELS_DIR` (on
WSL, `/srv/models`) and `CORTEX_MODEL_FILE_EMBED` first.

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d llama-embed
cd brain && CORTEX_EMBEDDING_ENDPOINT=http://127.0.0.1:8081 \
  uv run pytest -m integration --no-cov packages/embedding
```

`CORTEX_MODEL_FILE_EMBED` was `CORTEX_EMBED_MODEL_FILE` until 2026-08-30, and nothing reads the
old name, so a `.env` that still sets it runs the shipped nomic model instead of the override.
Recreate `llama-embed` after changing it; the column is dimension-agnostic, so a wrong choice is a
silent change in what recall returns rather than an insert that fails. If the CPU `server` image
ships without `curl` the healthcheck stays unhealthy though the server is up; watch
`docker compose logs llama-embed` for the `listening on http` line instead.

**nomic-embed-text-v1.5 Q8_0** (768 dimensions, about 146 MB) is the compose default, validated
2026-06-29: it loads in about 1.2 s on CPU with negligible RAM. `nomic-embed-text-v2-moe` (also
768 dimensions, larger, multilingual) is the alternative. With both services up, adding the memory
override to `docker compose up` runs the brain with `CORTEX_MEMORY_BACKEND=pgvector`, so turns
recall and record for real.

## Export and restore

The durable data is a named volume rather than a raw Windows bind mount, because Postgres PGDATA
over one has ownership and latency problems. Export is the `pg-backup` sidecar in
`docker-compose.memory.yml` (script `docker/postgres/backup.sh`): it runs `pg_dump` into
`CORTEX_DB_DIR` (default `./pgdata`; on WSL `/srv/pgdata`) on start and then every
`CORTEX_DB_SYNC_INTERVAL_S` seconds (default 6 h), writing `cortex.dump` atomically and keeping
the prior dump as `cortex-previous.dump`.

```
CORTEX_DB_DIR=/srv/pgdata \
  docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml up -d postgres pg-backup
ls /srv/pgdata   # cortex.dump appears after the first tick; watch: docker compose logs pg-backup
```

The sidecar runs the same `pgvector/pgvector:pg16` image as the server so `pg_dump` matches the
major version. That image declares `VOLUME /var/lib/postgresql/data` and docker keeps the
declaration even though the sidecar never opens a data directory, so it mounts a `tmpfs` there.
Restore with `pg_restore -U cortex -d cortex /path/to/cortex.dump`, or dump by hand with
`docker compose ... exec postgres pg_dump -U cortex -d cortex -Fc -f /tmp/cortex.dump`.

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml down
```

Add `-v` to also drop the `cortex-pgdata` volume, which wipes the memory store.
