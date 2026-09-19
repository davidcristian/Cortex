# brain/packages/core: memory and recall

Part of [`cortex_core`](brain-core.md), which holds the shared values, the public surface rule and
the package invariants. This document covers durable memory: the embedder and store ports, the
recaller a turn calls, how a scope divides the namespace, and the policies that rank an over-fetched
pool down to the hits one turn sees. The turn that calls it is in
[brain-core-turn.md](brain-core-turn.md), and the pgvector adapter is in
[brain-memory.md](brain-memory.md). The decisions are ADR-0008, ADR-0019 and ADR-0038.

## Ports and values

- `Embedder` provides `async embed(text) -> Sequence[float]`: one stateless call, text to vector,
  whose dimension is fixed by the deployment's model and assumed nowhere here. Fake:
  `HashEmbedder`, deterministic and I/O free, never returning an all-zero vector.
- `MemoryStore` provides `add(record)`, `search(embedding, *, k, scopes=None)` (most similar
  first), `count_candidates(*, scopes=None)` and `delete_scope(scope) -> int`. `scopes` restricts
  the candidate set to those namespaces (ADR-0008 decision 9) and `None` ranks over every memory.
  `count_candidates` reports how wide that candidate set is, which `search` structurally cannot
  (ADR-0038 decision 14); it must be the store's own count and never a length over returned rows.
  `delete_scope` removes every memory in one namespace and returns how many, taking one required
  scope and no wildcard. Fake: `InMemoryMemoryStore`; adapter: `cortex_memory`.
- `MemoryRecord(id, text, embedding, at, scope=GLOBAL_SCOPE, tainted=False)` is one durable memory
  and rejects a naive `at`. `ScoredMemory(record, score)` is a retrieval hit and the store's **raw
  cosine similarity**, never the key a policy ranked by, so no caller can infer an order from it.
- `MemoryRecaller(store, embedder, clock, *, scope=GLOBAL_MEMORY_SCOPE, policy=RAW_RECALL_POLICY,
  id_factory=<uuid4>)` is the use case (ADR-0008). `record(text, *, session_id, tainted=False)`
  embeds, persists and returns a `MemoryRecord`. `recall(query, *, k, session_id, turn_id)` embeds
  the query, fetches `policy.candidate_k(k)` hits within `policy.read_scopes(session_id)` and
  awaits `policy.select(...)`, returning that ranking's memories cut to `k`; an empty ranking is no
  hits and is never refilled from the pool. An optional `audit: RecallAuditSink` gets one
  `RecallAudit` per recall, built inside an `is not None` check so an unaudited recall issues no
  counting query. The **id factory has a width past which the audit line stops holding whole
  candidates, and that width is 60 characters** (ADR-0051 decision 15);
  `brain/packages/orchestrator/tests/test_widest_line.py` fails the day a factory here crosses it.
- `MemoryScope` (port, `scope.py`) maps a turn's `session_id` to its `write_scope` and
  `read_scopes`. `GlobalMemoryScope` (the default) writes `GLOBAL_SCOPE` and reads everything;
  `SessionMemoryScope` writes and reads the session id. Selected through `CORTEX_MEMORY_SCOPE`.
- `SessionMemoryCascade(store, scope)` (`memory_cascade.py`, ADR-0021 decision 11) is the forget
  behind a session delete, kept out of the recaller so no tool and no tainted turn can reach a
  forget verb. It exposes only `delete_session_memories(session_id) -> int`, cascades only when the
  scope is the session's own private space, and runs the `GLOBAL_SCOPE` check first.
- `RecallPolicy` (port, `rerank.py`) turns an over-fetched pool into the final `k` hits:
  `candidate_k(k)` sizes the pool and `async select(hits, *, query, now, k, session_id=None,
  turn_id=None) -> Ranking` reranks and cuts it, returning at most `k` hits from the pool, none
  twice, and leaving the pool as it was given, the recaller reading it again for the dropped set.
  `core/tests/recall_policy_contract.py` checks that over all five policies (ADR-0068
  decision 10), and it is async so a policy may call the model.
- The five policies: `RawRecallPolicy` (`RAW_RECALL_POLICY`, top-`k` cosine, this port's own
  default argument), and in `rerank_policies.py` with their math in `rerank_math.py`,
  `RerankingRecallPolicy` (similarity blended with an exponential recency decay),
  `MmrRecallPolicy` (greedy maximal marginal relevance) and `RecencyMmrRecallPolicy` (that
  selection over the recency blend). `JudgeRecallPolicy(backend, model, *, pool_factor,
  fallback=RAW_RECALL_POLICY)` (`rerank_judge.py`) asks the resident model to order the pool under
  a JSON-schema-constrained request using `rank_bounds(k)` (`max_tokens=24 + 8k`, thinking off,
  trace budget zero) and falls back on any failure; an **empty** order is the model declining the
  pool and returns an empty ranking on the `DEMUR` basis without the fallback (ADR-0038
  decision 11). A similarity floor was calibrated and **declined** (ADR-0038 decision 12).
- `Ranking`, `RankedMemory` and `RankBasis` (`ranking.py`) are what `select` returns.
  `RankedMemory` pairs a kept hit with the `key` its policy ordered by, and `Ranking` adds the
  `basis` naming that quantity: `ECHO` (raw cosine), `EMBER` (recency blend), `SPREAD` (MMR over
  cosine), `SWEEP` (MMR over the blend), `VERDICT` (the model's placing) and `DEMUR`. `comparable`
  is `False` for the two MMR bases, and a `DEMUR` ranking with hits is refused at construction.
- `RecallAudit` (`ranking.py`) is what a `RecallAuditSink` records: `session_id`, `turn_id`,
  `query`, `pool_size`, `available`, `k`, `ranking`, `dropped`, `at`. It contains conversation
  text, so the sink decides what it keeps and the shipped `LoggingRecallSink` keeps none.
  `dropped_candidates(pool, ranking, *, limit=DROPPED_TRAIL_LIMIT)` derives what the rank did not
  keep, each `DroppedCandidate` an id and the store's raw score with no rank key and no text.
  `DROPPED_TRAIL_LIMIT` is 20, the shipped pool width, and `omitted` counts what it left out.
- `drain_text(backend, model, messages, *, schema=None, bounds=None, stops=None)` (`drain.py`) runs
  one completion to its end and closes the stream in a `finally`, so the adapter's lease block is
  left before the call returns rather than nesting the turn's own reply inside it. Used by
  `generate_title`, `JudgeRecallPolicy` and `SummarizingHistoryWindow`, all three passing `bounds`.
  It logs a warning when it throws away a trace the request asked against (ADR-0049).

**Invariants.**

- A tainted turn is dropped from memory by default, or recorded with `tainted=True` and fenced on
  recall, so recall stays trustworthy either way.
- A retrieval hit reports the store's raw similarity and never the key a policy ranked by, so no
  caller can infer an order from it.
- An audit record holds memory ids and scores and never the text a rank declined.
