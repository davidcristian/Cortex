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
should a consumer ever need to display it (the store's cosine is kept today; **declined 2026-07-16**,
the last addendum below, because that condition is still unmet); and **maximal-marginal-
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
rerank addendum (the latter **declined 2026-07-16**, the last addendum below). The
**recency-and-diversity** policy (MMR run over the reranker's recency-blended
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
**model-based reranker** and **surfacing the blended relevance** as a distinct field remain (the
latter **declined 2026-07-16**, the addendum below). One
structural note: this landing split the three opt-in reranking policies and their shared math into
`rerank_policies.py` at the 300-line cap; the port and the default `RawRecallPolicy` stay in
`rerank.py`.

## Addendum (2026-07-16): the blended-relevance field declined, no consumer reads a recall score

The three addenda above each carried **surfacing the blended relevance as a distinct field** as the
one reranker deferral behind the unchanged seam. That is a statement about its *cost*, and it had
come to stand in for readiness. Read against the tree, the entry is **declined**: no behavior
change, and the deferral moves to the backlog's dead-until-a-consumer list
([docs/refinements/memory.md](../refinements/memory.md)). Two findings decide it.

1. **Nothing reads a recall score.** `ScoredMemory.score` is produced by both store adapters
   (`PgVectorMemoryStore._to_scored`, `InMemoryMemoryStore.search`) and consumed only by the recall
   policies as an *input* and by tests. The one production consumer of a recall result,
   `TurnEngine._render_memory_context` (`engine.py`), reads `record.text`, `record.tainted`, and
   `record.id`, and never touches `score`: a recalled memory is rendered as a bullet of text, or
   fenced as untrusted data. Nor is there anywhere else for a score to go. The seam declares no
   memory message at all ([proto/body.proto](../../proto/body.proto)), so the overlay cannot display
   one, and the recall path has neither logging nor an audit sink (the core has no logger; the only
   observability port of this shape is `ToolAuditSink`, which memory has no analog of). The rerank
   addendum's own wording made this the condition: "should a consumer ever need to display it".
   Adding the field now would ship a value no code reads, which is what the backlog's
   dead-until-a-consumer bucket exists to prevent.

2. **There is no single blended relevance to surface.** The three opt-in policies rank by three
   different quantities. `RerankingRecallPolicy` ranks by `_recency_blend`, a convex combination of
   similarity and decay that is comparable across hits and order-independent. `MmrRecallPolicy` and
   `RecencyMmrRecallPolicy` rank by an MMR objective whose redundancy term is measured against the
   set already kept, so a hit's value depends on when it was picked and two hits in one result are
   not comparable. A field named "relevance" would therefore mean three things, one of which cannot
   be read as a ranking at all. `RawRecallPolicy` has no blend to report.

**Cost correction.** The "behind the unchanged seam" reading holds only for the design this ADR
warned against: adding the field to `ScoredMemory`, which is the *store's* output type, so both
adapters would have to emit a blend no store computes and every consumer would carry a bimodal
value. Keeping the raw cosine and a policy's rank key distinct, which is the point of the entry,
means widening what `RecallPolicy.select` returns. That is the same signature the **model-based
reranker** is blocked on widening to async, so the honest sequencing is to reopen both together and
change `select` once, rather than twice.

**What the tree keeps instead.** The invariant is now stated on the type a reader actually opens,
rather than only in these addenda: `ScoredMemory`'s docstring records that its score is the store's
raw cosine similarity in `[-1, 1]`, never the key a policy ranked by, so a reranked result's order
is not explained by the field and no caller may infer a ranking from it
([docs/modules/brain-core.md](../modules/brain-core.md)). It is a docstring, so behavior, coverage,
and the wire are untouched.

**Evidence, live against pgvector** (the memory compose override, real Postgres + pgvector 0.8.5,
seeded probe rows). The adapter's score is cosine *similarity*: a row at distance 0.0002 came back
as 0.9998. Under `CORTEX_MEMORY_RECALL=reranked` the emitted order carried scores 0.6000, 0.9998,
0.7071, which the reported field does not explain, while the recency blend does (0.7131, 0.6999,
0.5700); under `mmr` and `recency_mmr` neither the score nor the blend explains the order, which is
the second finding observed rather than argued. Two mutations confirm the invariant is gated,
not merely documented: making `RerankingRecallPolicy` emit its blend as the score fails
`test_reranking_prefers_a_recent_hit_over_a_slightly_more_similar_stale_one`, and making the shared
`_greedy_mmr` emit its objective fails the MMR and recency-MMR score assertions. A third, dropping
the `1 -` from the adapter's `SELECT` so it reports distance, fails the live contract check against
real pgvector, which is where "higher = closer" is anchored.

**Newly deferred, recorded in [docs/refinements/memory.md](../refinements/memory.md): recall
observability.** Answering the question this addendum answers took a throwaway script against the
store, because the recall path emits nothing: no log line, no audit record, no way after the fact to
see what a policy ranked by. That is a **new port plus a sink adapter** on the `ToolAuditSink`
(ADR-0009) model, which is why it is not a cheap follow-on here, and it is also the consumer that
would reopen the declined field, since a sink recording a hit's rank key is the first code that
reads one. Fix when it bites: the first visibly wrong recall in a real session that cannot be
inspected afterwards.

## Addendum (2026-07-16): the model-based reranker audited, the async widening priced and the lease framing corrected

The rerank, MMR, and recency-and-diversity addenda above each keep a **model-based reranker** (a
cross-encoder or LLM-judge `select`) deferred behind two costs: the sync `RecallPolicy.select` must
go async, and it inherits a non-reentrant GPU-lease hazard "when the reranker runs inside a turn that
already holds the lease." Audited against the code, the first cost is bounded and the second is
misframed, but the reranker stays deferred, now with a sharper blocker, alongside the summarization
half it shares a design with ([ADR-0014 summarization-audit
addendum](ADR-0014-history-windowing.md), [docs/refinements/session-history.md](../refinements/session-history.md)).

**The async widening is clean and contained.** `RecallPolicy.select` has one production caller,
`MemoryRecaller.recall` (`recall.py`), already an `async` method. Widening to `async` adds one `await`
there and propagates no colour upward. The implementers are `RawRecallPolicy` plus the three opt-in
policies (`RerankingRecallPolicy`, `MmrRecallPolicy`, `RecencyMmrRecallPolicy`), and none calls
another's `select`; they compose through the shared `_greedy_mmr` and `_recency_blend` helpers, so no
implementer's async-ness infects another. An `async def select` with a synchronous body is gate-clean
(`RUF029` is preview-only, off here), so each policy wraps unchanged.

**The lease hazard is navigable, and this entry's framing overstated it.** Recall runs inside
`_inference_messages`, which `handle_turn` awaits to completion before the reply stream acquires the
resident model's non-reentrant lock (`model.py`, held across the whole stream in `backend.py`). So at
reranking time the turn does **not** yet hold the lease, and the phrase "inside a turn that already
holds the lease" is imprecise: a reranker that fully drains its model call is a sequential acquire,
the title generator's discipline, proven safe against the real manager (a drained acquire then the
reply's acquire succeeds; a call held open across it deadlocks). The real hazard is an abandoned
reranker stream, not nesting inside a held lease.

**Why it still waits.** Beyond a model reranker's ordering being unverifiable on the 8 GB dev GPU,
where the cortex tier does not fit, the blended-relevance decline above sequences this: the declined
field and the recall-observability entry both resolve to a `RecallPolicy.select` widening, and the
recorded guidance is to change `select` once for all its consumers (a model rank, a distinct blended
field, an observability sink that reads a rank key) rather than twice. An async-only widening now
would be that first of two changes. So the reranker reopens with the model manager's real GPU
lifecycle, landing the async widening, the richer `select` return, and the model policy as one
design. Recorded at [docs/refinements/memory.md](../refinements/memory.md).

## Addendum (2026-07-16): the delete/forget verb lands (`delete_scope`), the policies stay deferred

Decision 2 shipped `MemoryStore` as `add` + `search` only. The tiered/self-editing entry's cost
correction ([docs/refinements/memory.md](../refinements/memory.md)) had found that every richer
memory idea (tiering, self-editing, retention, eviction) needs verbs the port lacks. This addendum
lands the **one** of those verbs with recorded consumers already waiting on it, and keeps the rest
deferred, additively, behind an otherwise unchanged port.

1. **`MemoryStore.delete_scope(scope: str) -> int`.** It hard-deletes every memory in one namespace
   and returns how many rows it removed (0 when the scope holds none). It is the forget primitive two
   backlog entries named as their shared missing verb: the **session-delete cascade** (a session
   delete could not honestly remove a session's derived memories, [session-read-seam.md](../refinements/session-read-seam.md))
   and **per-scope eviction** (the scoping addendum's deferred retention/eviction policy).

2. **By scope, not by id, because the scope _is_ the session-to-memory link.** A memory carries no
   session id; the only thing tying it to the conversation that wrote it is its `scope`, which
   `SessionMemoryScope` sets to the `session_id` (scoping addendum). So a cascade is `delete_scope(
   session_id)`, and under the default `GlobalMemoryScope` (where a session's memories land in the
   shared `GLOBAL_SCOPE` on purpose) there is correctly nothing session-private to cascade. The verb
   takes a single required scope and offers no wildcard, unlike `search`'s `scopes=None`, so a
   namespace is dropped only when named and no call can erase everything by omission; a caller that
   maps a session onto `GLOBAL_SCOPE` must never pass it here.

3. **A hard delete, not a tombstone.** `SessionStore.delete` will likely tombstone a transcript so an
   in-flight read fails cleanly, but memory is different: `search` is a stateless top-k scan with no
   in-flight read of a specific id, so a removed row simply drops from the candidate pool with
   nothing to fail cleanly. The pgvector adapter issues `DELETE FROM memories WHERE scope = $1`,
   parsing the row count from asyncpg's `DELETE n` command tag (a malformed tag wraps as
   `MemoryStoreError`, the malformed-response path `search` already guards for a row). **No schema
   change:** the existing `memories_scope_idx` btree serves the equality.

4. **Data-loss-safe by construction.** A delete triggered by untrusted content ("forget everything")
   is the obvious injection worry. It is foreclosed structurally, not by a runtime check. Memory is
   **not a tool** in any registry, so a model, jailbroken or not, has no call that reaches the store;
   and the `MemoryRecaller` a turn is handed as `caps.memory` exposes only `record` and `recall`, so
   even the engine cannot delete. `delete_scope` lives on the port for out-of-band trusted callers
   (session management, an eviction policy), never on the turn path. A structural test pins the
   recaller's turn-facing surface, so adding a delete there later reddens and forces a taint review.
   This is the same fail-closed stance as the tainted-turn confirm decline (ADR-0022), stronger here
   because there is no tool at all rather than a denied one.

**Consciously deferred (recorded in [docs/refinements/memory.md](../refinements/memory.md)), each
for want of a consumer and no longer for a missing verb:** self-editing memory (**update** in
place), **tiered** promote/demote/expire, **write-salience** (whose separate entry also needs
`MemoryRecaller.record`'s non-optional return to widen), and the **per-scope retention _policy_**
(the eviction verb now exists; a scheduler deciding what to evict when does not, and nothing drives
one). **Per-provenance eviction** ([docs/refinements/untrusted-content.md](../refinements/untrusted-content.md))
is not served by `delete_scope`: a memory record stores only the `tainted` bit, not the ADR-0027
structured provenance, so eviction by sender/URI wants a different filter and stays fix-when-it-bites.

**Evidence.** CI-gated at 100% over the fake (`InMemoryMemoryStore`, bespoke core tests) and the
pgvector adapter (canned-row `Database` fake: SQL, count parsing, error and malformed-tag wrapping);
the shared behavioral contract (`memory_contract.ALL_CHECKS`) gained a delete check and runs against
real pgvector in the host `integration` test. Host-validated live against real Postgres + pgvector:
seeded two scopes (3 rows and 2 rows), `delete_scope` of the first returned 3 and left the table at 0
and 2, `search` of the deleted scope returned nothing while the other scope was untouched, and a
no-match scope returned 0. Distrust-green: a no-op fake delete fails the core deletion test on the
search-after assertion (the count alone still passes, proving the test asserts real mutation), a
by-id adapter SQL fails the adapter's SQL assertion, and a `WHERE scope = $1 AND false` neutered
adapter fails the live contract's `removed == 2`, each turned red before being reverted.

## Addendum (2026-07-19): the model reranker's hardware blocker was false

The 2026-07-16 addendum above opens its "Why it still waits" paragraph with "a model reranker's
ordering being unverifiable on the 8 GB dev GPU, where the cortex tier does not fit". The second
half of that is measurably wrong, and it was wrong before it was written:
[ADR-0029](ADR-0029-vision-screen-capture.md) brought `gemma-4-12b-it-qat-q4_0.gguf` up on that
card on 2026-07-17 at `-ngl 99 --ctx-size 4096 --parallel 1` **with its vision projector loaded**
and drove a real turn through it the next day, and
[ADR-0030](ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
8188 MiB. Ranking a handful of recall
candidates is not a 16K-context question, so the ordering is judgeable agent-side today.

**What this changes.** Not the deferral, only its reason, which matters because a reason that names
hardware reads as "wait for the user" and this one is "take the design decision". What holds the
reranker is the sequencing this ADR already gives: the declined blended-relevance field and the
recall-observability entry resolve to the same `RecallPolicy.select` widening, and that widening
should serve all three consumers in one change rather than go async alone. Read the paragraph above
as saying that and nothing about a card. Corrected the same day in
[docs/refinements/memory.md](../refinements/memory.md) and its
[index](../refinements/index.md).

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-07-19): where decision 7's host-side check is tracked

Decision 7 says mounting PGDATA directly onto the Windows drive "is validated on the host as a
*nice to have*, not the default". That check needs Docker on the host Windows host, so it is
host work, and it now has a written home: the optional item at the end of
[docs/host/windows-desktop.md](../host/windows-desktop.md), indexed at
[docs/host/](../host/index.md), which states plainly that nothing depends on the answer and that
no procedure exists yet, so writing one is part of taking it. Its result comes back here as a dated
addendum and to [runbooks/memory-pgvector.md](../runbooks/memory-pgvector.md).

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-08-06): the `select` widening landed, and the relevance field is un-declined

The rerank addendum's deferred **model-based reranker**, the relevance-field addendum's **declined
blended-relevance field**, and the **recall observability** entry that decline opened all resolve in
[ADR-0038](ADR-0038-ranked-recall.md), which widens `RecallPolicy.select` once for the three of them:
`async def select(hits, *, query, now, k) -> Ranking`.

Two things this ADR's addenda said need correcting here. **The relevance-field decline is
reversed**, and reversed in the way its own last line predicted, as a `select` change rather than a
field: the key a policy ranked by is `RankedMemory.key` on the ranking, so `ScoredMemory.score`
keeps meaning the store's raw cosine and the two quantities stay distinct, which was the invariant
the decline was protecting. Its second finding, that there is no single blend to surface, is
answered rather than dodged: `RankBasis` names each quantity and `comparable` records that an MMR
key was measured against the kept set and cannot be read beside another. **And the audit addendum
undercounted the widening.** It priced `select` going async and its return widening; nobody noticed
that `select` did not carry the query, which a policy that ranks by what a memory *says* cannot do
without. Three changes, not two.

The model rank ships as `JudgeRecallPolicy` and was measured against the shipping cosine on the real
cortex rather than assumed: mean reciprocal rank 0.917 to 1.000, the correct note first 5 of 6 times
against 6 of 6, on a small corpus built so the two rankings could disagree. Numbers, method and the
honest caveats are in ADR-0038. What stays deferred in this area is recorded in
[docs/refinements/memory.md](../refinements/memory.md) and its
[index](../refinements/index.md): a cross-encoder rank, which wants a scoring-model port rather than
a chat completion, and auditing the candidates that were dropped, which the two MMR bases cannot
give a well-defined key for.

## Addendum (2026-08-08): the recall default is the model rank, not the raw cosine

Decision 4 above records `CORTEX_MEMORY_RECALL` as "`raw` (default) or `reranked`", which was true
of the change that wrote it and is no longer true of the tree. The default is now `judge`, the
model rank that [ADR-0038](ADR-0038-ranked-recall.md) built, and the reason is written up in that
ADR's turn-cost addendum rather than restated here.

The short of it, because a reader who opens this ADR for the recall seam should not have to leave
it to learn what ships: the rank was left off on cost alone, bounding its request took that cost
from about 12 seconds to under one, and the question the user held the flip on was what that does
to a whole turn rather than to a rank. Measured over 48 real turns an arm through the seam on the
24 GB card, with two raw blocks around the judged one as a control, a recalling turn's time to
first token rises **0.515 s** (95% CI 0.116 to 0.915) while the two raw blocks differ by an amount
whose interval spans zero. The rank alone costs 0.877 s at the pool a turn asks for; the turn pays
less than that because the judge hands the reply 1.17 notes where the cosine hands it 5. The rank
is paid on every recalling turn and nothing caches it.

Nothing about the `RecallPolicy` seam changed for this. It is one value in `MemoryConfig`, the
policies are all still selected at the composition root, and `CORTEX_MEMORY_RECALL=raw` restores
the byte-for-byte v1 behavior this ADR shipped. What did change is which way the opt is: the
founding cosine is the opt-out now.
