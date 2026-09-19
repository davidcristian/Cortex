# ADR-0038: A ranked `select`, its audit trail, and where a history summary lives

**Status:** Accepted (2026-09-19)

## Context

Three deferred consumers waited on one port change. A model-based rerank needed
`RecallPolicy.select` to be `async`; a blended relevance figure, declined in
[ADR-0008](ADR-0008-memory-v1.md) for want of a reader, would reopen as a richer `select` return;
and recall observability was the reader that would give it one. A fourth, summarizing the history
the window drops ([ADR-0014](ADR-0014-history-windowing.md)), needed the sibling
`HistoryWindow.select` to go `async` too, and left open whether a summary is cached or recomputed.

Both `select` calls run inside `assemble_inference_messages` (`turn_context.py`), which
`handle_turn` awaits to completion before it builds the reply's generator, so selection holds no
GPU lease. The lease is a non-reentrant `asyncio.Lock` held for a stream generator's lifetime
(`LlamaCppBackend.stream`), so a model pass during selection is safe only if its stream is closed
before the reply asks for the lease. And `select` was not given the query, which a rank that reads
what a memory says cannot do without.

## Decision

### The ranked select

1. **`RecallPolicy.select` is `async` and returns a `Ranking`:**
   `async select(hits, *, query, now, k, session_id=None, turn_id=None) -> Ranking`, widened once
   for all three consumers. The two ids are opaque handles a policy may log (decisions 15 and 16);
   `query` and the hits are conversation text, which is why the ids are separate parameters.
2. **The widened return is a ranking, not a wider hit.** `Ranking` is frozen, with
   `hits: tuple[RankedMemory, ...]` and one `basis: RankBasis`; `RankedMemory` pairs a
   `ScoredMemory` with the `key: float` the policy ordered by. `ScoredMemory.score` keeps its one
   meaning, the store's raw cosine. `Ranking.__post_init__` refuses a `DEMUR` ranking that has hits;
   an empty ranking on any other basis is legal and means there was nothing to rank.
3. **The declined blended-relevance field is added as `RankedMemory.key`.** ADR-0008 declined a
   second field on `ScoredMemory`; the placement changes, and decision 5 gives the key a reader.
4. **`RankBasis` names how a memory came to mind, and whether its key compares across a result:**

   | Basis | Policy | The key is | Comparable |
   | --- | --- | --- | --- |
   | `ECHO` | `RawRecallPolicy` | the store's raw cosine | yes |
   | `EMBER` | `RerankingRecallPolicy` | the similarity and recency blend | yes |
   | `SPREAD` | `MmrRecallPolicy` | the MMR objective, computed against the kept set | no |
   | `SWEEP` | `RecencyMmrRecallPolicy` | MMR over the blend | no |
   | `VERDICT` | `JudgeRecallPolicy` | the model's placing, normalized to (0, 1] | yes |
   | `DEMUR` | `JudgeRecallPolicy` | none: the model read the pool and kept nothing | yes, vacuously |

   `RankBasis.comparable` states the split on the type, so a consumer cannot threshold an MMR key.
   `VERDICT` and `DEMUR` are judicial words because each is a decision by something that can be
   wrong. Rejected sets: plain descriptive (`Likeness`, `Warmth`), which reads as a glossary, and
   technical (`Cosine`, `Judge`), which names implementations; for the refusal, `NONSUIT` (a word to
   look up), `SILENCE` (fits an empty store as well as a refusal) and `ABSTAIN` (the judge did
   decide).

### The recall record

5. **Recall observability is a port and a sink, modelled on `ToolAuditSink`.** `RecallAuditSink`
   takes one `RecallAudit` per recall: `session_id`, `turn_id`, `query`, `pool_size`, `available`,
   `k`, the `ranking`, the `dropped` candidates and `at`. `LoggingRecallSink`
   (`cortex_memory/audit.py`) writes one `memory.recall` line with the query's length, never its
   text, and each hit's id, score, key and taint bit, never its text. It is opt-in
   (`CORTEX_MEMORY_RECALL_AUDIT`, default off, which wires no sink), and `MemoryRecaller` builds the
   whole record inside its `audit is not None` guard, so an unaudited recall walks the pool once and
   issues no count. How the line renders is [ADR-0051](ADR-0051-log-line-rendering.md); its logger
   name is declared as [ADR-0045](ADR-0045-documented-log-lines.md) decision 13 requires.
6. **`MemoryRecaller.recall` keeps returning `Sequence[ScoredMemory]`.** The ranking is the
   policy's return; the recaller unwraps it, so the ranking never reaches turn assembly or the gRPC
   layer.

### The judge

7. **The model rank is `JudgeRecallPolicy`, a core policy over the `InferenceBackend` port, and the
   default.** It over-fetches `k * pool_factor`, sends the candidates to the resident cortex as a
   numbered list under the JSON-schema-constrained `ORDER_ENVELOPE`
   ([ADR-0028](ADR-0028-grammar-constrained-subagents.md)), and turns the order into keys in (0, 1].
   `CORTEX_MEMORY_RECALL` defaults to `judge`; `raw` is the opt-out that restores the founding
   behaviour. Its fallback (default `RAW_RECALL_POLICY`, which `recall_policy_from_config` does not
   override) takes an unreachable model, a reply outside the envelope, a truncated one, an order of
   nothing that exists and an empty pool, and the ranking then uses the fallback's basis, so the
   record says what ranked. `rank_bounds(k)` is `24 + 8k` tokens with no thinking
   ([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) decision 5), computed because the
   envelope admits only numbers: a cut reply is not JSON and costs the whole judgement, so the cap
   is generous.

### A pass during selection

8. **Any selection-time inference goes through `drain_text` (`drain.py`)**, which consumes the
   stream and closes it in a `finally`, the engine's own `await events.aclose()` discipline one
   layer down; `generate_title` uses it too. Selection then completes before the reply's first
   `acquire`, so the two acquisitions are sequential, never nested, and the release survives a
   caller that stops early. `drain_text` takes an optional `stops: StopLedger | None` and still
   returns a bare `str`; at six arguments it is at ruff's `max-args`, so a seventh collaborator
   needs a bundle. `TITLE_BOUNDS` is 32 tokens with no thinking, eight times the four tokens a title
   costs and past the 48 characters `clean_title` keeps, so the cap cannot change a stored title.

### The history recap

9. **A session summary is cached in the store, not recomputed per turn, because history is
   append-only.** It lives in Redis behind `SessionStore`, beside the session's messages and title,
   and never in `MemoryStore`, which would make it recallable into other sessions. `SessionStore`
   has no verb that edits or removes a message, so a summary of a prefix can go incomplete and
   never wrong: it is keyed by the boundary it covers, rewritten only when the window's boundary
   moves forward, and each new one folds the previous account with the newly dropped turns.
   Recomputing would put a full generation ahead of every reply; the cache pays it once per
   boundary move. It survives a swap because it is text in Redis written after the pass completes.
10. **`HistoryWindow.select` is `async select(history, *, session_id, progress=None)`.** It went
    `async` with the summarizing window, the one consumer that needed it, and needs the session
    because a cached recap belongs to one.

### The judge may decline, and geometry may not

11. **The judge may decline.** `parse_order` has three outcomes: `None` for a reply nothing can be
    read from (including a list whose every pick fails the range check), `()` for a complete
    `{"order": []}`, and the picks otherwise. `()` returns an empty `DEMUR` ranking without
    consulting the fallback; the recaller returns no hits without re-fetching; turn assembly sends
    no memory block, exactly what a memory-less turn sends, rather than a message claiming memory
    was empty, which the assembly does not know.
12. **There is no relevance floor on a geometric policy.** Behind both embedders the repo ships a
    path for, answerable and unanswerable questions overlap in cosine, so any floor that silences
    unanswerable questions also silences answerable ones, worst in the vocabulary trap the judge
    was bought for. Declining is a property of reading, not of ranking. `test_recall_floor_live.py`
    asserts the overlap and goes red behind an embedder whose populations separate, which reopens
    it; the shape it would take then is a decorator over any policy, including the judge's fallback,
    thresholding `hit.score` over the pool before the inner policy picks.

### What the record holds

13. **The record names what the rank left behind.** `dropped_candidates(pool, ranking, *, limit)`
    in `ranking.py` is the one answer: `DroppedCandidates` holds up to `DROPPED_TRAIL_LIMIT` (20)
    `DroppedCandidate(id, score)` in the store's own order plus an `omitted` count, rendered as
    `dropped` and `dropped_omitted`. Identity is the memory id, so an empty ranking drops the whole
    pool. A dropped candidate holds the store's cosine and never a rank key, which does not exist
    for `SPREAD`, `SWEEP` or `VERDICT`, and has no field that could hold text. Twenty is the shipped
    pool (`DEFAULT_RECALL_K` 5 times `CORTEX_MEMORY_RECALL_POOL_FACTOR` 4), so a shipped line never
    truncates. The line says a memory was a candidate and was passed over, never why.
14. **The record says what the pool came from.** `MemoryStore.count_candidates(*, scopes=None)`
    is a verb beside `search`, returning the store's own count under the same scope filter
    (`SELECT count(*)` with the search's `WHERE scope = ANY`); `RecallAudit.available` holds it.
    `available` equal to `pool_size` means the pool was the whole readable store; below it, the pool
    was cut. The count runs straight after the search, only when a sink is wired, and a failed count
    fails the recall rather than inventing a figure. The requested width is not logged: where it
    would matter it equals `pool_size`. The memory contract suite runs over both implementations.
15. **A fallback line says why the rank did not run, and names the recall.** Of the judge's four
    exits, an empty pool and a refusal log nothing (the refusal is in the record as `demur`); an
    `InferenceError` logs `the model could not be asked to rank recall; falling back to the unjudged
    ranking` with the pool, `k` and the exception; an unreadable reply logs `the model returned no
    usable recall order; falling back to the unjudged ranking` with `capped` (from a `StopLedger`)
    and `chars`. So every line the module writes means the configured rank did not run. Both
    include `session_id` and `turn_id`, `None` when the caller named none, and never the query or a
    note; the judge hands both ids to its fallback on every exit, so a nested judge still has them.
16. **A recall is named by the turn it was made for.** `MemoryRecaller.recall(query, *, k,
    session_id, turn_id)` requires the turn; `_recalled_context` passes `context.turn_id`, and
    `RecallAudit.turn_id` is required. The shared policy contract
    (`core/tests/recall_policy_contract.py`) holds that all five policies rank the same with or
    without the two ids, since the ids name a recall and never rank it.

### The recap as built

17. **The verbs are `set_recap` and `recap`, the value `HistoryRecap`,** since `SessionSummary`
    already names a chat-list row and `digest` a hash. A whole-session delete removes the recap in
    the same transaction, because a recap is as private as the transcript.
18. **The summarizing window only prepends.** It returns the inner window's selection untouched plus
    at most one recap message, so every failure (store or model unreachable, a failed stream, an
    unusable reply) sends what the plain window sends, and no state of it loses a user's message.
19. **A recap is fenced at both ends and does not spread taint.** The prompt uses
    `SECURITY_PREAMBLE` as its system message and quotes the dropped transcript and the previous
    account inside `wrap_untrusted` under one nonce; the recap enters a turn through `fence_recap`
    under a second nonce minted after the model has spoken, so a compromised summarizer never holds
    the string that ends its own fence. Neither wrap has a condition. The persisted prefix holds no
    tool output (a turn persists the user text and the scrubbed reply) and no taint bit, but a reply
    may quote an injection, which the recap would otherwise promote to a durable system message.
    Taint is not spread, since that would block outbound tools on every later turn of every long
    conversation while the plain window sends the same messages untainted.
20. **The fold is bounded, floored and announced, and the summary is on by default.**
    `InferenceBackend.stream` takes `bounds: GenerationBounds | None` per request, because one
    resident cortex both answers the user and folds, which a server flag cannot tell apart; `None`
    sends the request unchanged. `RECAP_BOUNDS` is 512 tokens with no thinking, which is `RECAP_MAX`
    (2,000 characters) at four characters a token. `clean_recap` returns `""` for a reply that does
    not end a sentence or is longer than `RECAP_MAX`, and the window rejects it rather than
    trimming, since a stored cut account would advance `covers` past turns its tail never reached.
    `min_dropped_chars`
    (`CORTEX_HISTORY_RECAP_MIN_CHARS`, default 2,000) defers a fold below one account's worth of
    new material; deferring leaves `covers` where it was, and `build_history_window` clamps the
    floor to the character budget so the unaccounted gap stays smaller than the window. A pass that
    will run emits `StatusUpdate(state="folding")` through the per-call `progress` sink.
    `CORTEX_HISTORY_SUMMARY` defaults to `true`.
21. **A rejected fold says why.** Its line includes `capped`, read off the `StopLedger` given to
    `drain_text`, and `chars`, measured through `collapse_recap`, the normalization `clean_recap`
    itself uses, so the logged length is the one the rejection was decided on.

### Measuring a whole turn

22. **A turn-cost measurement is a recipe plus a pure reader.** `just turn-cost` runs three blocks
    in A/B/A order, restarting the brain container with one environment variable changed between
    them; the driver (`orchestrator/tests/test_turn_cost_live.py`) asserts only invariants and
    writes one JSON sample per block; `scripts/contrast.py` treats the first sample as the baseline
    and reports each later one as a blocked paired bootstrap by question (the mean of per-question
    mean differences, a seeded percentile interval over questions), printing its seed and the
    per-question layout. The last A/B/A line is a null contrast whose interval should span zero.
    One warmup turn per block is discarded; each turn runs in a fresh session under
    `CORTEX_MEMORY_SCOPE=session` seeded with the 41-note corpus, and a turn that finds more rows
    than it seeded stops the block. `docker/docker-compose.memory.yml` passes through every
    `MemoryConfig` field it does not set as a bare key, so every documented setting reaches the
    container without a second copy of its default.

## Consequences

- The judge adds a model call to time to first token on every recalling turn, with no cache; it
  hands the reply fewer notes than the cosine, which gives back part of that cost. The readings are
  in [ranked recall](../readings/ranked-recall.md).
- A recall may legitimately return nothing where the judge is on.
- Under concurrent streams a reply queues behind other streams' folds on the one lease; the
  ordering argument of decision 8 holds, and the cost is queueing
  ([history recap](../readings/history-recap.md)). A stalled reader holds the lease across its
  reply only once it has used up the gRPC flow-control credit, which the one shipped consumer does
  not do (R-035).
- `RecallAudit` gained required fields as the record grew, so every construction site states them
  and no sink silently emits less.
- Every quality reading of the judge is over notes written for the measurement; a shortfall on a
  real corpus needs a deployed store and is what would bring a cross-encoder rank (R-097), which
  needs a scoring port rather than a chat completion.

## Alternatives rejected

- **Widening `MemoryRecaller.recall`'s return:** pushes the ranking into turn assembly and the
  gRPC layer for no consumer.
- **Recomputing the recap per turn, or storing it in `MemoryStore`:** a generation ahead of every
  reply; recallable across sessions.
- **Refusing the recap when tools are enabled, or persisting a taint marker:** does not close a user
  pasting untrusted text; a schema change bought for a narrowing.
- **A fifth policy name for the threshold:** it cannot reach the judge's fallback, and it
  multiplies policy names.
- **`count(*) OVER ()` in the ranked select:** materializes every row before the limit, 2.85 times
  the plain search at 100k rows; a capped count trades an exact answer for 2 ms.
- **The turn-cost test calling `docker compose`, or changing the variable in process:** the test
  would own a stack it did not start, or measure a second composition root.

## Related

- Readings: [ranked recall](../readings/ranked-recall.md), [history recap](../readings/history-recap.md).
- Module contracts: [brain-core](../modules/brain-core.md), [brain-memory](../modules/brain-memory.md),
  [brain-session](../modules/brain-session.md), [brain-orchestrator](../modules/brain-orchestrator.md).
- Runbooks: [memory-pgvector](../runbooks/memory-pgvector.md), [llamacpp-gpu](../runbooks/llamacpp-gpu.md).
- [ADR-0008](ADR-0008-memory-v1.md) (memory), [ADR-0014](ADR-0014-history-windowing.md) (the
  window), [ADR-0013](ADR-0013-untrusted-content.md) (the fence),
  [ADR-0048](ADR-0048-generation-bounds.md) and [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md)
  (bounds), [ADR-0051](ADR-0051-log-line-rendering.md) (how the trail renders).
- Open: [R-035](../refinements/tasks/035-stalled-consumer-holds-lease.md),
  [R-097](../refinements/tasks/097-cross-encoder-rank.md).
