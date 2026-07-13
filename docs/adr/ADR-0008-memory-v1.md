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

## Addendum (2026-07-06): memory scoping as the deferred decision-3 refinement

Decision 3 shipped v1 as **one global memory space** and named per-session / namespaced
scoping as "a later refinement behind the same port." This addendum delivers it, additively,
behind the unchanged `MemoryStore`/`Embedder` ports and the `MemoryRecaller` use-case. CI-gated
end to end over the fakes; the pgvector SQL is host-validated via Docker (as decision 6 requires
because CI never proves the adapter's SQL).

1. **A memory belongs to a `scope` (an opaque namespace string).** `MemoryRecord` gains
   `scope: str` (default `GLOBAL_SCOPE = "global"`, appended last so every positional caller and
   the contract's `make_record` are source-compatible). The scope is a free-form label, not an
   enum: `"global"`, a `session_id`, or a future `"work"`/`"personal"` namespace all fit the
   same column. The store is still a pure translator. The caller (the `MemoryRecaller`) sets the
   scope, exactly as it already sets id/timestamp/embedding.

2. **`search` gains an optional scope filter, defaulting to the v1 behavior.**
   `MemoryStore.search(embedding, *, k, scopes: Sequence[str] | None = None)`. `None` ranks over
   **all** memories (the global recall v1 always did, unchanged), a non-`None` sequence restricts
   the candidate set to those scopes before ranking (pgvector: `WHERE scope = ANY($n)`; the fake:
   a Python filter). `add` is unchanged (the record carries its scope). No existing caller passes
   `scopes`, so the default keeps every current path byte-for-byte identical.

3. **The write-scope and read-scopes for a turn come from an injected `MemoryScope` policy, which is
   the extensible seam.** `MemoryScope` (pure core, `scope.py`, the `HistoryWindow` pattern) maps
   a turn's `session_id` to `write_scope(session_id) -> str` and
   `read_scopes(session_id) -> Sequence[str] | None`. Two reference policies ship:
   - **`GlobalMemoryScope`** (the default, `GLOBAL_MEMORY_SCOPE` singleton) means write to
     `GLOBAL_SCOPE`, read `None` (all). **v1 behavior exactly**, so recall stays cross-session by
     default: that is the founding "retrieval that grows across conversations" feature (decision 3)
     and what the eventual README sells. Scoping is **opt-in**, not a default flip.
   - **`SessionMemoryScope`** means write to `session_id`, read `(session_id,)`. Each conversation's
     memory is private to that conversation; recall no longer crosses conversations.

   `MemoryRecaller.__init__` takes `scope=GLOBAL_MEMORY_SCOPE`; `record(text, *, session_id)` and
   `recall(query, *, k, session_id)` thread the turn's session through the policy. `TurnEngine`
   already owns `session_id` in `handle_turn` and now passes it to both calls. The store filters,
   the policy decides, the engine stays dumb: three responsibilities, three seams.

4. **Config selects the policy at the composition root only.** `CORTEX_MEMORY_SCOPE`
   (`MemoryConfig.scope`) is `global` (default) or `session`; `build_memory` maps it to the policy
   via `memory_scope_from_name` and injects it into the `MemoryRecaller`. No core code reads env.

5. **Schema + migration.** `init.sql`'s `memories` table gains `scope text NOT NULL DEFAULT
   'global'` and a btree `memories_scope_idx` (equality filtering, not the still-deferred ANN
   index). The `DEFAULT 'global'` makes the column additive for an existing dev DB
   (`ALTER TABLE memories ADD COLUMN scope text NOT NULL DEFAULT 'global';` +
   `CREATE INDEX …` (runbook)), and back-fills every pre-existing row into the global space, so an
   in-place upgrade keeps recalling exactly as before.

**Consciously deferred (behind these same seams), recorded in the ROADMAP:** a **session+global
union** read policy (a `SessionMemoryScope` that also reads `GLOBAL_SCOPE`, once something writes
durable global facts under scoping, though today nothing does, so the union would be dead); a
**per-scope retention / eviction** policy; and **cross-scope recall ranking** (weighting a hit by
which scope it came from). All are `MemoryScope`/`MemoryStore` refinements, none a port change.

## Addendum (2026-07-13): retrieval quality as a `RecallPolicy` seam (recency rerank + dedup)

The "Retrieval quality" risk named v1 recall as **raw top-k cosine with no reranking, recency
weighting, or dedup**, "revisit behind the port if recall is noisy." This addendum delivers all
three, additively, behind the **unchanged `MemoryStore`/`Embedder` ports** and the `MemoryRecaller`
use-case. CI-gated end to end over the fakes; no SQL change, so no host validation is owed (the
reranking is pure core, above the store).

1. **The rerank lives in the use-case, not the store, behind a new pure `RecallPolicy` seam
   (`rerank.py`, the `MemoryScope`/`HistoryWindow` pattern).** It needs the record's age, which means
   the `Clock` the `MemoryRecaller` already owns and the store does not, and it must compose recency
   with dedup in one pass that the pgvector `ORDER BY <=> LIMIT` cannot express cleanly. Keeping it
   above the store also means the two adapters (pgvector, in-memory fake) stay pure translators and
   the port keeps its one meaning: `search` still returns top-k by cosine, most-similar first.
   `RecallPolicy` has two methods: `candidate_k(k) -> int` (how wide a pool to over-fetch) and
   `select(hits, *, now, k) -> Sequence[ScoredMemory]` (rerank, dedup, truncate to `k`).

2. **`MemoryRecaller.recall` over-fetches, then applies the policy.** It searches for
   `policy.candidate_k(k)` candidates in the turn's read-scopes, then returns
   `policy.select(pool, now=clock.now(), k=k)`. `record` is untouched. The policy is injected
   (`policy=RAW_RECALL_POLICY`), exactly as `scope=GLOBAL_MEMORY_SCOPE` is.

3. **Two reference policies ship.**
   - **`RawRecallPolicy`** (the default singleton `RAW_RECALL_POLICY`) is **v1 behavior exactly**:
     `candidate_k(k) = k`, `select = hits[:k]`. The pool the store returns is already
     similarity-sorted and length-`k`, so every current recall path stays byte-for-byte identical and
     pays no extra fetch. Reranking is **opt-in, not a default flip** (the scoping addendum's stance),
     because it changes what the model sees and its value depends on the embedding model's observed
     recall noise, which the risk framed as the trigger to enable it.
   - **`RerankingRecallPolicy`** over-fetches `k * pool_factor`, scores each hit by a convex blend
     `relevance = (1 - recency_weight) * similarity + recency_weight * recency`, where `recency =
     0.5 ** (age_seconds / half_life_seconds)` is an exponential decay over an **age floored at 0**
     (so a future-dated record from clock skew or a corrupt row is treated as maximally recent: it
     cannot exceed a fresh one, and the non-positive exponent cannot overflow). It sorts by `relevance`
     (stable, so equal-relevance ties keep the store's similarity order), then greedily drops a hit
     whose embedding cosine to an already-kept hit is `>= dedup_threshold` (identical text
     roundtrips to cosine 1.0, so exact duplicates fall out first, and paraphrases with them),
     and truncates to `k`. Each emitted `ScoredMemory.score` **stays the raw cosine similarity**:
     the order and membership reflect relevance, but the reported score keeps the store's meaning,
     so the field never silently becomes "relevance." A degenerate zero-magnitude embedding scores
     cosine 0.0 and so is never deduped against another.

4. **Config selects and tunes the policy at the composition root only.** `CORTEX_MEMORY_RECALL`
   (`MemoryConfig.recall`) is `raw` (default) or `reranked`; the tuning knobs
   `CORTEX_MEMORY_RECALL_HALF_LIFE_DAYS` (30), `CORTEX_MEMORY_RECALL_RECENCY_WEIGHT` (0.3),
   `CORTEX_MEMORY_RECALL_DEDUP_THRESHOLD` (0.98), and `CORTEX_MEMORY_RECALL_POOL_FACTOR` (4) build
   the `RerankingRecallPolicy` via `recall_policy_from_config`. No core code reads env; the half-life
   is authored in days and converted to seconds at the seam.

**Consciously deferred (behind the same `RecallPolicy` seam), recorded in the ROADMAP:** a
**model-based reranker** (a cross-encoder or an LLM-judge `select`, the natural next policy once a
deterministic blend proves too blunt); **surfacing the blended relevance** as a distinct field
should a consumer ever need to display it (the store's cosine is kept today); and **maximal-marginal-
relevance** diversity beyond threshold dedup (**landed 2026-07-13**, the addendum below). All are
policy swaps, none a port change.

## Addendum (2026-07-13): maximal-marginal-relevance diversity as a third `RecallPolicy`

The rerank addendum's deferred **maximal-marginal-relevance** diversity lands here, additively, as a
third reference `RecallPolicy` behind the **unchanged `MemoryStore`/`Embedder` ports** and the
`MemoryRecaller` use-case. No new seam, no SQL change, so no host validation is owed (pure core,
above the store); CI-gated end to end over the fakes at 100%.

1. **Why beyond threshold dedup.** `RerankingRecallPolicy`'s dedup only drops a hit whose embedding
   cosine to an already-kept hit clears `dedup_threshold` (0.98 by default), so a pool of *distinct
   but redundant* memories (several phrasings of one fact, each below the cutoff) still crowds out
   the rest and the turn sees one region of the query's neighborhood `k` times. MMR penalizes *every*
   candidate by its similarity to what is already kept, so the returned `k` spread across the
   neighborhood rather than clustering on its single closest region.

2. **`MmrRecallPolicy` (a new pure-core policy in `rerank.py`).** `candidate_k(k) = k * pool_factor`
   over-fetches (MMR needs a wider pool to diversify over). `select` builds the result greedily from
   the empty set, each step picking the candidate maximizing
   `relevance_weight * similarity - (1 - relevance_weight) * redundancy`, where `similarity` is the
   hit's raw cosine to the query (the store's `score`) and `redundancy` is its greatest embedding
   cosine to an already-kept hit (0 for the first pick, so the first pick is the most similar).
   `relevance_weight` is the MMR `lambda`: `1.0` is pure relevance (degenerating to `RawRecallPolicy`
   order), `0.0` pure diversity after the first pick. Candidates are scanned in the store's
   similarity order and only a strict improvement displaces the incumbent, so ties keep that order; a
   zero-magnitude embedding is never counted redundant (the `_cosine` no-magnitude guard). Each
   emitted `ScoredMemory.score` **stays the raw cosine**, exactly as `RerankingRecallPolicy`. Recency
   is out of scope: it is `RerankingRecallPolicy`'s axis, a distinct policy.

3. **Config selects it at the composition root only.** `CORTEX_MEMORY_RECALL` gains `mmr` (now `raw`,
   `reranked`, or `mmr`); `CORTEX_MEMORY_RECALL_MMR_LAMBDA` (0.5) tunes `relevance_weight`, reusing
   the shared `CORTEX_MEMORY_RECALL_POOL_FACTOR` (4). `recall_policy_from_config` builds it; no core
   code reads env.

**Consciously deferred (behind the same `RecallPolicy` seam), recorded in the ROADMAP:** the
**model-based reranker** and **surfacing the blended relevance** as a distinct field remain from the
rerank addendum. The **recency-and-diversity** policy (MMR run over the reranker's recency-blended
relevance) it also named **landed 2026-07-13**, the addendum below. All are policy swaps, none a
port change.

## Addendum (2026-07-13): recency-and-diversity as a fourth `RecallPolicy`

The MMR addendum's deferred **recency-and-diversity** policy lands here, additively, as a fourth
reference `RecallPolicy` behind the **unchanged `MemoryStore`/`Embedder` ports** and the
`MemoryRecaller` use-case. `RerankingRecallPolicy` weights recency and `MmrRecallPolicy` diversifies
on raw similarity; a memory wanted for being fresh, on-topic, *and* non-redundant needs both axes at
once, which neither alone gives. No new seam, no SQL change, so no host validation is owed (pure
core, above the store); CI-gated end to end over the fakes at 100%.

1. **`RecencyMmrRecallPolicy` composes the two existing policies (`rerank.py`).** It runs the MMR
   greedy selection (`_greedy_mmr`: repeatedly keep the candidate of highest marginal score,
   penalizing each by its `_redundancy` to what is already kept) with the `_recency_blend`
   similarity-and-recency combination as the relevance term, in place of `MmrRecallPolicy`'s raw
   cosine. A candidate scores `relevance_weight * blend - (1 - relevance_weight) * redundancy`, where
   `blend = (1 - recency_weight) * similarity + recency_weight * recency`. `relevance_weight` is the
   MMR `lambda` (relevance vs diversity); `recency_weight` is the recency share within the relevance
   term. Each emitted `ScoredMemory.score` **stays the raw cosine**, as the other reranking policies.

2. **The shared machinery was extracted, behavior-preserving.** `_recency_blend` (was
   `RerankingRecallPolicy._relevance`), `_redundancy` (was `MmrRecallPolicy`'s inline max-cosine),
   and `_greedy_mmr` (was `MmrRecallPolicy.select`'s loop) are now module free functions the three
   reranking policies share, so the fourth is a composition rather than a paste. The existing
   policies' behavior is byte-for-byte unchanged (their tests pass untouched).

3. **Config selects it at the composition root only.** `CORTEX_MEMORY_RECALL` gains `recency_mmr`
   (now `raw`, `reranked`, `mmr`, or `recency_mmr`), reusing the existing `recall_half_life_days`,
   `recall_recency_weight`, `recall_mmr_lambda`, and `recall_pool_factor` knobs; no new knob, and no
   core code reads env. `recall_policy_from_config` builds it.

**Consciously deferred (behind the same `RecallPolicy` seam), recorded in the ROADMAP:** the
**model-based reranker** and **surfacing the blended relevance** as a distinct field remain. One
structural note: this landing split the three opt-in reranking policies and their shared math into
`rerank_policies.py` at the 300-line cap; the port and the default `RawRecallPolicy` stay in
`rerank.py`.
