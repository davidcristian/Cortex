# ADR-0008: Memory v1 with MemoryStore + Embedder ports, custom over pgvector

**Status:** Accepted (2026-08-20)

## Context

The cortex needs long-term recall: at turn end the exchange is written to a durable, growing
memory, and at turn start the most relevant past memories are retrieved into context. This is the
first durable (Postgres) store. Session state (Redis, [ADR-0001](ADR-0001-architecture.md)) is hot
and per conversation; memory is knowledge that crosses conversations and survives everything.

The founding plan named this the place to decide between Letta and a custom store, required the
knowledge base to be portable (copied and backed up as plain files, plugged into a future setup),
and put embedding on the CPU so the GPU budget stays with the cortex
([ADR-0004](ADR-0004-model-lineup.md) decision 11).

## Decision

1. **Custom and thin, not Letta.** Memory is a `MemoryStore` port, a pgvector adapter and a small
   use-case in the pure core, with no framework. Letta brings its own agent loop, storage model and
   self-editing control flow, which breaks the invariant that orchestration is explicit typed code
   in the core. Its ideas (tiered or self-editing memory, summarization) stay adoptable behind the
   port; the framework would rule them out.

2. **Two ports, both stateless functions over a backend** (`cortex_core/ports_stores.py`,
   `ports.py`):
   - `Embedder.embed(text) -> Sequence[float]`; failures raise `EmbedderError`.
   - `MemoryStore.add(record)`; `search(embedding, *, k, scopes=None) -> Sequence[ScoredMemory]`,
     the top `k` by cosine similarity, most similar first; `count_candidates(*, scopes=None)`, the
     number of rows a search could draw from ([ADR-0038](ADR-0038-ranked-recall.md) decision 14);
     and `delete_scope(scope) -> int` (decision 11). Failures raise `MemoryStoreError`.

   The values are pure (`memory.py`): `MemoryRecord(id, text, embedding, at, scope, tainted)`,
   built by the caller (id from a factory, `at` from the `Clock`, the embedding from the
   `Embedder`, `tainted` per [ADR-0019](ADR-0019-tainted-memory-recording.md)), so the store is a
   translator exactly as `RedisSessionStore.append` is. `ScoredMemory(record, score)` is a hit
   whose `score` is always the store's raw cosine similarity in `[-1, 1]`, never the key a policy
   ranked by.

3. **Recall is global by default, and scoping is a policy (decision 9).** With the default policy,
   `search` ranks over every memory, because the point is recall across conversations.

4. **The use-case is pure core (`recall.py`, `MemoryRecaller`).** `recall(query, *, k, session_id,
   turn_id)` embeds the query, searches the turn's read scopes for the policy's candidate pool, and
   returns the policy's selection (decision 10); `record(text, *, session_id, tainted)` embeds and
   adds a `MemoryRecord` in the turn's write scope. The engine recalls into a system-role context
   message at turn start and records the exchange at turn end.

5. **The embedder adapter is llama.cpp's CPU `/v1/embeddings`**
   ([ADR-0005](ADR-0005-llamacpp-engine.md)), an httpx translator mirroring the inference adapter:
   injected client, failures wrapped as `EmbedderError`, CI over `httpx.MockTransport`, and an
   `integration`-marked live test against a real CPU `llama-server` (`-ngl 0`). The dimension is a
   deployment parameter and the core is dimension-agnostic. The pick is ADR-0004 decision 9; the
   unbounded `vector` column and the absence of an ANN index are ADR-0004 decision 4, with the
   search numbers in [model-lineup.md](../readings/model-lineup.md#memory-search).

6. **The pgvector adapter stays at 100% coverage without a database in CI.** It takes an injected
   async-connection port, and CI tests it against a fake connection returning canned rows: the row
   mapping, the SQL it sends, the count parsing, and the error wrapping. The behavioural contract
   (`brain/packages/memory/tests/memory_contract.py`) is one shared list used by the in-memory fake
   in CI and by real Postgres and pgvector in an `integration`-marked run
   ([ADR-0068](ADR-0068-port-contract-lists.md)). So CI does not prove the adapter's SQL; the live
   run does, the same trade the inference adapter makes. The list includes a lost-backend check:
   each implementation is given a `break_backend` (the live version closes the adapter's own pool)
   and `add`, `search`, `count_candidates` and `delete_scope` must each raise `MemoryStoreError`,
   never a driver exception and never `MemoryDataError`.

7. **The live data is a named volume, exported as plain files.** Postgres keeps its data directory
   in the named volume `cortex-pgdata` (`docker/docker-compose.memory.yml`), avoiding the ownership
   and latency problems of a Postgres data directory on a Docker Desktop Windows bind mount. The
   `pg-backup` sidecar, on the server's own image, dumps the database into `CORTEX_DB_DIR` (default
   `./pgdata`) on start and every `CORTEX_DB_SYNC_INTERVAL_S` (default 21600, six hours), with an
   atomic replace and a one-deep `cortex-previous.dump`, so the portable copy never depends on an
   operator remembering a step. A data directory mounted straight onto the Windows drive is an
   optional host check that nothing depends on
   ([H-010](../host/tasks/010-pgdata-on-windows-drive.md)).

8. **The `cortex`/`cortex` credential is a dev default, not a secret.** It protects a
   loopback-only, single-user dev database holding locally generated memories. Refusing to default
   it would break bring-up for no protection; `CORTEX_PG_PASSWORD` overrides it for any other
   deployment.

9. **A memory belongs to a scope, and an injected `MemoryScope` picks it.** `MemoryRecord.scope` is
   an opaque label (default `GLOBAL_SCOPE = "global"`; a `session_id` or a future namespace fit the
   same column), and a non-`None` `scopes` restricts `search` to those scopes before ranking
   (`WHERE scope = ANY($n)`). `MemoryScope` (`scope.py`) maps a turn's `session_id` to
   `write_scope(session_id)` and `read_scopes(session_id)`. `GlobalMemoryScope`, the default,
   writes `GLOBAL_SCOPE` and reads with no filter; `SessionMemoryScope` writes and reads the
   session's own id, so recall no longer crosses conversations. `CORTEX_MEMORY_SCOPE` (`global` or
   `session`) selects the policy at the composition root. The `memories` table has `scope text NOT
   NULL DEFAULT 'global'` and the btree `memories_scope_idx`; the default back-filled every earlier
   row into `global`.

   Changing the setting moves no stored memory: each row keeps the scope it was written under. A
   store switched from `global` to `session` keeps its earlier memories in `global`, which
   `SessionMemoryScope` never reads and the session delete never removes; a store switched back
   reads every conversation's former private memories from every conversation.

10. **Ranking is a `RecallPolicy` above the store.** The store returns top-`k` cosine and nothing
    else, so the adapters stay translators. `RecallPolicy` (`rerank.py`) has `candidate_k(k)`, the
    pool to over-fetch, and `async select(hits, *, query, now, k) -> Ranking`
    ([ADR-0038](ADR-0038-ranked-recall.md) decisions 1 to 4). `CORTEX_MEMORY_RECALL` picks one:
    - `judge`, the default: the resident model orders the pool by what each note says, falling back
      to raw cosine when it cannot be used ([ADR-0038](ADR-0038-ranked-recall.md) decision 7, which
      also records the turn cost).
    - `raw`: `candidate_k(k) = k`, the store's order; the founding behaviour, now the opt-out.
    - `reranked`: over-fetches `k * pool_factor`, orders by `(1 - recency_weight) * similarity +
      recency_weight * 0.5 ** (age / half_life)` with the age floored at 0, then drops a hit whose
      cosine to a kept hit reaches `dedup_threshold`.
    - `mmr`: greedy maximal marginal relevance, `lambda * similarity - (1 - lambda) * redundancy`,
      where redundancy is the greatest cosine to a kept hit.
    - `recency_mmr`: the same walk with the recency blend as its relevance term.

    The heuristic policies live in `rerank_policies.py` over the shared `rerank_math.py`. The
    settings are `CORTEX_MEMORY_RECALL_HALF_LIFE_DAYS` (30), `_RECENCY_WEIGHT` (0.3),
    `_DEDUP_THRESHOLD` (0.98), `_POOL_FACTOR` (4) and `_MMR_LAMBDA` (0.5); each policy validates
    the ones it uses. The key a policy ranked by is reported as `RankedMemory.key` on the ranking,
    so `ScoredMemory.score` keeps the store's meaning; a field on `ScoredMemory` would have made
    both adapters emit a value no store computes, and the MMR keys are not comparable across one
    result.

11. **`MemoryStore.delete_scope(scope)` is the forget operation.** It hard-deletes every memory in
    one scope and returns the count (pgvector: `DELETE FROM memories WHERE scope = $1`, the count
    parsed from the `DELETE n` tag, served by the scope index). It works by scope because the scope
    is the only link from a memory to the conversation that wrote it. It takes one required scope
    and no wildcard, so nothing is erased by omission, and `GLOBAL_SCOPE` is never passed to it. It
    is a hard delete, since `search` is a stateless scan with no in-flight read to protect. Memory
    is not a tool in any registry, and the `MemoryRecaller` a turn holds exposes only `record` and
    `recall` (asserted by `test_the_recaller_exposes_no_forget_verb_so_no_turn_can_delete_memory`),
    so no model or turn reaches a delete. Its caller is the session-delete cascade
    ([ADR-0021](ADR-0021-session-read-rpcs.md) decision 11).

12. **An unavailable memory costs a turn its notes, never the turn.** `EmbedderError` and
    `MemoryStoreError`, and nothing else, are caught in the core: in
    `turn_context._recalled_context` for the read and `turn_output.record_exchange` for the write,
    the two places the engine and the deep phase share. A failed read logs a `warning`
    (`memory recall unavailable`), writes no recall log line (a line for a recall that never ran
    would read as an empty store), and emits one `StatusUpdate` in the state `forgoing`, because a
    recalled memory is knowledge from other conversations the user cannot supply. A failed write
    logs an `error` (`memory write unavailable`) and tells the user nothing: the reply is already
    streamed and persisted, so raising could not save the memory and would only replace an answered
    turn with an error, and the exchange itself is still in the conversation. The catch is not in
    the adapter, which also serves the session-delete cascade where a swallowed failure would be a
    privacy defect, and not in `MemoryRecaller`, which cannot know what its caller can do without.
    A store unreachable at startup still fails the brain's start.

13. **A malformed row is a data defect, and it fails visibly.** The criterion is whether the
    condition resolves without anyone touching the deployment: a stopped server comes back, a row
    that will not decode does not. `MemoryDataError` subclasses `MemoryStoreError`; the pgvector
    adapter raises it only from its decoding catches (a `KeyError`, `IndexError`, `TypeError` or
    `ValueError` reading a reply, or rendering the query embedding), while asyncpg's
    `PostgresError`, `InterfaceError` and `OSError` stay `MemoryStoreError`. `_recalled_context`
    re-raises it ahead of the degrading catch, with no `forgoing` status, since that status says
    the turn answers without notes. The write still degrades on the whole family. `DeleteSession`
    aborts `INTERNAL` on it where an outage aborts `UNAVAILABLE`; that is a label for the operator,
    not a retry change, because the body never repeats a delete.

## Consequences

- The embedder runs on the CPU, so the GPU budget is unaffected.
- Configuration lives at the composition root: `CORTEX_MEMORY_BACKEND`, the DSN, the embedder
  endpoint, the scope, the recall policy and its settings, the tainted-turn policy
  ([ADR-0019](ADR-0019-tainted-memory-recording.md)) and the recall log line. No core code reads
  the environment.
- Every exchange is recorded as raw text. A write-salience policy
  ([093](../refinements/tasks/093-write-salience-policy.md)), tiered or self-editing memory
  ([087](../refinements/tasks/087-tiered-self-editing-memory.md)), a session and global union read
  ([084](../refinements/tasks/084-session-global-union-read.md)), and cross-scope ranking
  ([086](../refinements/tasks/086-cross-scope-recall-ranking.md)), which is a `RecallPolicy` and a
  `RankBasis` member rather than a `MemoryScope`, all wait for a consumer. A union policy must stay
  on the read side, since the cascade deletes exactly `write_scope(session_id)`.
- Retention ([085](../refinements/tasks/085-per-scope-retention-eviction.md)) has the operations it
  needs only under `session` scoping, where it drops whole conversations. Under the default every
  memory lives in `GLOBAL_SCOPE`, so evicting by a cap or an age needs a delete by id or by
  timestamp that the port does not have.
- A memory stores only the `tainted` bit, so eviction by provenance needs another filter.

## Alternatives rejected

- **Letta**, for the framework reasons in decision 1.
- **A raw PGDATA bind mount as the default**, for the reasons in decision 7.
- **Degrading on a data defect with a log line.** The log is the silence decision 12 was written to
  end, and the turn would answer thinly on every run until the data is fixed.
- **Other names for the `forgoing` state.** `forgetting` claims a memory was lost; `blanking` is
  the interpretation the state exists to be told apart from; `recalling` names the attempt at the
  one time it did not happen; `bypassing` sounds like a choice.

## Related

- [brain-core](../modules/brain-core.md), [brain-memory](../modules/brain-memory.md),
  [brain-embedding](../modules/brain-embedding.md), [memory-pgvector
  runbook](../runbooks/memory-pgvector.md).
- [ADR-0038](ADR-0038-ranked-recall.md) (the ranked select, the judge and the recall log line),
  [ADR-0019](ADR-0019-tainted-memory-recording.md) (tainted memory),
  [ADR-0021](ADR-0021-session-read-rpcs.md) (the session-delete cascade).
