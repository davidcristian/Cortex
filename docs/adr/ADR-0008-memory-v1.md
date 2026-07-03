# ADR-0008: Memory v1 with MemoryStore + Embedder ports, custom over pgvector

- **Status:** Accepted (Slice 5)
- **Date:** 2026-06-29

## Context

Slice 5 gives the cortex long-term recall: at turn end the exchange is written to a
durable, growing memory; at turn start the most relevant past memories are retrieved into
context. This is the first durable (Postgres) store. Session state (Redis, ADR-0003) is
hot and per-conversation; memory is cross-session knowledge that survives everything.

The founding spec named this the place to decide **Letta vs. custom** (ROADMAP Slice 5),
and where the durable data must be **plug-and-play**, carried as plain files under
`D:\Software\AI\Database` (ADR-0004 addendum). Embedding runs on **CPU** (ADR-0004
addendum: the GPU budget is spent on the cortex).

## Decision

1. **Custom and thin, not Letta.** Memory is a `MemoryStore` port + a pgvector adapter + a
   small retrieval/write use-case in the pure core, with no framework. Letta (MemGPT) brings
   its own agent loop, storage model, and self-editing-memory control flow; adopting it
   violates the invariant that *orchestration is explicit typed code in the core, no heavy
   agent framework that hides control flow* (AGENTS.md). Its good ideas (tiered/self-editing
   memory, summarization) can be adopted later **behind the unchanged port**; the framework
   cannot. Extensibility wins the tie for v1: the thin port keeps every one of those
   ideas adoptable later; the framework would foreclose them.

2. **Two ports, both stateless functions over a backend (ports.py):**
   - `Embedder.embed(text) -> Sequence[float]` maps one text to one vector. Failures →
     `EmbedderError`.
   - `MemoryStore.add(record)` / `MemoryStore.search(embedding, *, k) -> Sequence[ScoredMemory]`
     persist one memory and return the top-`k` by cosine similarity, most-similar first.
     Failures → `MemoryStoreError`.

   Value types (pure, `memory.py`): `MemoryRecord(id, text, embedding, at)`. The caller
   builds it (id from a factory, `at` from the `Clock`, `embedding` from the `Embedder`),
   so the store is a pure translator exactly as `RedisSessionStore.append` is.
   `ScoredMemory(record, score)` is a retrieval hit with its similarity.

3. **Global memory space in v1.** `search` ranks over all memories, not a per-session
   subset, because the point is recall *across* conversations ("retrieval that grows"). Per-session
   or namespaced scoping is a later refinement behind the same port.

4. **The use-case is pure core (`memory.py`, `MemoryRecaller`).** `recall(query, k)` embeds
   the query then searches; `record(text)` embeds then adds a `MemoryRecord`. The turn
   integration (retrieve-into-context at turn start, record-at-turn-end) is a thin later
   increment over this. It is kept out of the ports-first increment so the conversation/turn
   changes it needs (a system-role context message) land on their own.

5. **Embedder adapter = llama.cpp CPU `/v1/embeddings` (ADR-0005),** an httpx translator
   mirroring `LlamaCppBackend`: injected client, backend/decoder failures wrapped as
   `EmbedderError`. CI covers it with `httpx.MockTransport`; a host-only, `integration`-marked
   live test hits a real CPU `llama-server` (`-ngl 0`). The embedding **dimension is a
   deployment parameter** (nomic-embed = 768). The core is dimension-agnostic; the fake
   embedder is small-dim.

6. **pgvector adapter, and how it stays 100%-covered without a DB in CI.** There is no
   `fakeredis` for pgvector, so the adapter follows the **already-accepted MockTransport
   pattern**: it takes an injected async-connection port, and CI unit-tests it against a
   fake connection returning canned rows, covering row→`MemoryRecord` mapping and
   `PostgresError`→`MemoryStoreError` wrapping, the asyncpg analog of what `MockTransport`
   does for llama.cpp. The **behavioral contract** (`ALL_CHECKS`: top-k ordering, roundtrip
   fidelity) runs against the in-memory fake in CI and against **real Postgres + pgvector in
   a host-only `integration` test**. Consequence, stated plainly: CI does **not** prove the
   adapter's SQL is correct. Only the host integration test does. That is the identical
   tradeoff already accepted for the inference adapter (MockTransport never proves a real
   `llama-server` behaves). CI stays service-less (no Postgres container), coverage stays
   honest (mapping + error paths are real code).

7. **Durable data placement: named volume + export, not a raw PGDATA bind mount.** The live
   Postgres data directory is a **named Docker volume** (avoids the ownership/latency
   pitfalls of a Postgres data dir over a Docker-Desktop Windows bind mount); a dump/sync
   job exports it to `D:\Software\AI\Database` to satisfy the plug-and-play requirement.
   Mounting PGDATA directly onto the Windows drive is validated on the host as a *nice to
   have*, not the default. The plug-and-play guarantee does not depend on it.

## Consequences

- **Increments** (each small, green, documented): (1, this ADR) ports + value types + typed
  errors + in-memory fakes + fake embedder + the `MemoryRecaller` use-case, fully covered in
  core; (2) wire memory into the turn, with a `Role.SYSTEM` context message from `recall`,
  `record` at turn end (end-to-end over the fakes); (3) the CPU embedder adapter
  (`cortex_embedding`); (4) the pgvector adapter (`cortex_memory`) + host validation of the
  volume/export and the bind-mount caveat.
- Config gains, at the composition root only: embedder endpoint/backend (mirroring
  `InferenceConfig`), the Postgres DSN, and the embedding dimension.
- The soft cap (ADR-0004, `CORTEX_VRAM_SOFT_CAP_GB`) is unaffected because the embedder is CPU.

## Risks

- **Retrieval quality.** v1 is raw top-k cosine with no reranking, recency weighting, or
  dedup. Acceptable to prove the loop; revisit behind the port if recall is noisy.
- **Write policy.** v1 records the raw exchange text every turn; summarization / salience
  filtering (what deserves to be remembered) is a later policy, also behind the port.
- **Index tuning.** ivfflat vs. hnsw and its parameters are a host/ops decision recorded
  when the pgvector adapter lands; exact search is fine at small scale.
- **Embedding model + quant.** The nomic pick (v1.5 vs. v2-moe, quant) is the host-driven
  half of this slice, recorded in ADR-0004 when measured.

## Addendum (2026-07-03): the automated dump/sync job is delivered; dev-credential carve-out

Two follow-ups from the 2026-07-02 slice audit (`audit/slice-5.md` and
`audit/cross-cutting.md` holds review artifacts removed after remediation; in git history
through commit `96463aa`):

1. **Decision 7's dump/sync job now exists.** Until 2026-07-03 the export was a manual
   `pg_dump` runbook step. Decision 7's "a dump/sync job exports it" was written in the
   present tense but not delivered, and the automation gap was recorded nowhere. The
   **`pg-backup` sidecar** (`docker-compose.memory.yml` + `docker/postgres/backup.sh`)
   closes it: on the same image as the server, it dumps to `CORTEX_DB_DIR` (default
   `./pgdata`) immediately on start and every `CORTEX_DB_SYNC_INTERVAL_S`
   (default 6 h), atomic replace plus a one-deep `cortex-previous.dump` rotation. The
   plug-and-play guarantee no longer depends on an operator remembering a manual step.
   Validated live via Docker (dump + rotation observed against real Postgres); see
   [memory-pgvector.md](../runbooks/memory-pgvector.md).

2. **The `cortex`/`cortex` Postgres credential is a deliberate dev-stack default, not a
   secret.** AGENTS.md gate 5 says "no secrets in the repo"; this ADR never recorded why the
   memory override commits a password. The carve-out, now written down: the credential guards
   a **loopback-only** (assumption 5), single-user, throwaway dev database whose only content
   is locally-generated memories. It is a well-known default, not a credential to protect,
   and refusing to default it (the email override's pattern, where the password is a *real*
   Proton Bridge secret) would break plug-and-play bring-up. It is now env-overridable as
   `CORTEX_PG_PASSWORD` (compose default `cortex`), so any non-dev deployment can inject a
   real secret via env per gate 5.
