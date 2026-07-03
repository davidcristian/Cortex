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
init. Data lives in the `cortex-pgdata` named volume (not a Windows bind mount, ADR-0008).

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
fidelity) against real pgvector, proving the adapter's SQL, which CI's canned-row fake
cannot. The test cleans up its own `contract-%` rows.

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
Validating a direct PGDATA bind mount as a nice-to-have (not the default) is optional.

## Teardown

```
docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.memory.yml down
```

Add `-v` to also drop the `cortex-pgdata` volume (wipes the memory store).
