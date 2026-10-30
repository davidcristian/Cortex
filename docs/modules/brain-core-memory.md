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
  `HashEmbedder(dimension=16, *, max_chars=EMBED_INPUT_CHARS)`, deterministic and I/O free, never
  returning an all-zero vector, and raising `EmbedderError` on a text over `max_chars`.
- `embedding_input(text)` (`embed_input.py`) returns the first `EMBED_INPUT_CHARS` characters of a
  text, which is 1800, or all of a shorter one. `EMBEDDER_CONTEXT_TOKENS` is 2048, the input bound
  of the shipped embedder; the model's tokenizer measured at most one token per character
  ([embedding-input.md](../readings/embedding-input.md)), so 1800 characters always fit.
- `MemoryStore` provides `add(record, *, recalled=()) -> bool`, `search(embedding, *, k, scopes=None)` (most similar
  first), `count_candidates(*, scopes=None)` and `delete_scope(scope) -> int`. `scopes` restricts
  the candidate set to those namespaces (ADR-0008 decision 9) and `None` ranks over every memory.
  `count_candidates` reports how wide that candidate set is, which `search` structurally cannot
  (ADR-0038 decision 14); it must be the store's own count and never a length over returned rows.
  `delete_scope` removes every memory in one namespace and returns how many, taking one required
  scope and no wildcard. `delete_tainted(*, scopes=None) -> int` removes every memory marked tainted
  in those namespaces, or in all of them, and `count_tainted(*, scopes=None) -> int` counts them.
  `delete_ids(ids) -> int` removes the listed rows in any scope and counts them; an id not stored
  adds nothing, and `find_text(text, *, limit, scopes=None)` returns the rows whose text contains
  `text`, case ignored, oldest first (ADR-0075). `delete_written_by(session_id) -> int` removes and
  counts every row that session wrote, in any scope (ADR-0021 decision 11). `add` stores the record only while every memory id in
  `recalled` still exists and returns whether it did, so a reply that recalled a memory a forget
  removed is not stored again. Fake: `InMemoryMemoryStore`; adapter: `cortex_memory`.
- `MemoryRecord(id, text, embedding, at, scope=GLOBAL_SCOPE, tainted=False, session_id=None)` is
  one durable memory and rejects a naive `at`; `MemoryRecaller.record` sets `session_id` to the
  writing session, and `None` marks a row stored before that was kept. `ScoredMemory(record, score)` is a retrieval hit and the store's **raw
  cosine similarity**, never the key a policy ranked by, so no caller can infer an order from it.
- `MemoryRecaller(store, embedder, clock, *, scope=GLOBAL_MEMORY_SCOPE, policy=RAW_RECALL_POLICY,
  id_factory=<uuid4>)` is the use case (ADR-0008). `record(text, *, session_id, tainted=False,
  recalled=())` embeds `embedding_input(text)`, persists the whole text and returns a
  `MemoryRecord`, or `None` when a memory in `recalled` is gone. `discard(memory)` deletes one
  record `record` returned, which `record_exchange` does when the chat was deleted meanwhile, under
  the write's bound. A `SessionStoreError` from that `deleted` read, or a failed or overrun
  `discard`, keeps the row and logs `the memory row of a chat that may be deleted was not removed`
  at `error` with `session_id` and `memory_id`; the turn completes.
  `recall(query, *, k, session_id, turn_id)` embeds `embedding_input(query)`, fetches `policy.candidate_k(k)` hits within `policy.read_scopes(session_id)` and
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
  behind a session delete, kept out of the recaller and out of every engine, so no tool reaches it.
  It exposes only `delete_session_memories(session_id) -> int`, which removes every memory the
  session wrote (`delete_written_by`) and then, when the write scope is the session's own private
  space and not `GLOBAL_SCOPE`, that scope.
- `finish_cleanup(store, cascade, schedules, session_id)` (`chat_cleanup.py`, ADR-0021 decision 11)
  runs a deleted chat's cascade, then `detach_session`, then `SessionStore.clear_cleanup`, so a
  failed step leaves the chat in `pending_cleanups`. `CleanupRepeater` runs it for every pending chat
  in a task started by `start()`, at once and then every `CLEANUP_REPEAT_INTERVAL_S` (60 s), logging
  each failure; a failed read of the pending set is logged and read again on the next pass.
- `UntrustedMemoryForget(store, scope)` (`memory_forget.py`, ADR-0019 decision 9) is a delete
  a tool reaches: `forget(session_id)` calls `delete_tainted` over the session's read scopes. The
  built-in `ForgetUntrustedTool` over it is `forget_untrusted_memories`: no arguments,
  `confirm_required`, and a `RecordCard` whose card is the fixed `FORGET_CARD`, so the dispatcher
  shows it on a tainted turn too. A store failure returns an `is_error` result and forgets nothing.
  It is a `ToolOffer`: `offered(session_id)` is `any_to_forget(session_id)`, a `count_tainted` over
  the same read scopes, so a chat with nothing to forget is not offered it; a failed count offers it.
  `record_exchange` (`turn_output.py`) stores nothing for a tainted turn in which it ran `ok`.
- `ForgetChosenTool(store, scope)` (`memory_forget_chosen.py`, ADR-0075) is `forget_memories`: one
  `text` argument, `confirm_required`, and a `RecordCard`. `card` runs `find_text` over the
  session's read scopes and lists an excerpt of each match, so the card holds stored text and never
  the model's; it keeps the matched ids under the call's id (the latest 32 calls). `invoke` deletes
  exactly those ids with `delete_ids`, searches again, and says how many were removed and whether
  any match is left. No text, no match, more than `FORGET_CHOSEN_LIMIT` (20) matches or a failed
  store deletes nothing: `card` returns `None`, so the dispatcher shows no card and runs the call,
  whose result says why. The description asks for the value or one word from the request that names
  it, and the no-match result tells the model to say that nothing about it was stored and not to
  ask the user for the value. It is a
  `ResultNote`: the dispatcher ends every result a call to it gets, run, declined, expired or
  refused, with `FORGET_NOT_KEPT_NOTE`, which says the message is not kept and asks the model to
  have the user send anything else in it again. `record_exchange` stores nothing for a turn that
  called `forget_memories`, whatever its result, since the query or reply may name the text; a deep
  phase passes the cortex's runs of the turn as `earlier`, so a forget before a handoff counts. A
  call that never ran counts too: the tool loop sets `TaintLedger.forget_asked` for every call the
  model names before any refusal or cut, the engine and the deep phase set it for an unreadable call
  whose `MalformedToolCallError.tool_name` is the forget, and the handoff record keeps it for the
  deep phase. Each of those also counts in `TaintLedger.forget_calls` (`name_forget`), and the
  round counts a run whose result has `matched_nothing` set, which only the no-match run of
  `forget_memories` sets, in `forget_unmatched`.
- `memory_withheld(caps, taint, runs, *, query)` (`memory_claim.py`, ADR-0019 decision 10) is the
  one check of whether memory is on and stores nothing of a turn: an opaque turn whatever
  `record_tainted_memory` says (ADR-0029), a tainted turn whose `forget_untrusted_memories` ran
  `ok`, a turn that named `forget_memories` unless every call ran and matched nothing and
  `asks_kept(query)` reads a request to remember (ADR-0075 decision 5), a turn whose `query` `asks_not_kept`
  (`memory_request.py`, ADR-0075 decision 5) reads as a request not to keep, to forget or to
  remove something, with or without a call, and a tainted turn under `skip`. `record_exchange`
  returns on it, and both phases pass it to `limit_notes` as `withheld`, which then appends
  `UNKEPT_CLAIM_NOTE` when `claims_kept(reply)` finds a statement, not a question, saying something
  was noted, remembered, made a note of, or kept or saved "in mind" or "in memory". A bare "saved"
  or "stored" does not count, since a file tool's reply says it saved a file. Neither do the forms
  that point at text rather than memory: "as I noted", "noted above", "I will note that" before a
  clause that is not about "you", "has been noted by" or "that", a file name such as `memory.txt`,
  and a bare "Noted" past the reply's first line, which is a line read back from a file. With
  memory off the check is false and no note shows.
- `unforgotten_claim(runs, reply, *, unmatched=0)` (`forget_claim.py`, ADR-0075) is true when
  `claims_forgotten(reply)` finds a statement, not a question, saying something was forgotten, or
  removed, deleted, erased, wiped or cleared from memory, no longer in memory or no longer
  remembered, or that memory was updated not to keep it, and no forget call in `runs` deleted a
  memory: no `forget_untrusted_memories` run is `ok`, and the `ok` runs of `forget_memories`
  number no more than `unmatched`, the turn's `forget_unmatched`. A clause whose subject is
  negated ("Nothing was removed") and a removal that names no memory ("I've removed the reminder")
  do not count. Both phases pass `forget_unmatched` to `limit_notes`, which then appends
  `UNFORGOTTEN_CLAIM_NOTE`, telling the person nothing was forgotten and to ask again in a
  message of its own. The deep phase's ledger starts its count at zero, so a cortex forget that
  matched nothing before a handoff counts there as one that deleted a memory.
- `RecallPolicy` (port, `rerank.py`) turns an over-fetched pool into the final `k` hits:
  `candidate_k(k)` sizes the pool and `async select(hits, *, query, now, k, session_id=None,
  turn_id=None) -> Ranking` reranks and cuts it, returning at most `k` hits from the pool, none
  twice, and leaving the pool as it was given, the recaller reading it again for the dropped set.
  `core/tests/recall_policy_contract.py` checks that over all five policies (ADR-0068
  decision 10), and it is async so a policy may call the model.
- The five policies: `RawRecallPolicy` (`RAW_RECALL_POLICY`, top-`k` cosine, this port's own default
  argument), and in `rerank_policies.py` with their math in `rerank_math.py`,
  `RerankingRecallPolicy` (similarity blended with an exponential recency decay), `MmrRecallPolicy`
  (greedy maximal marginal relevance) and `RecencyMmrRecallPolicy` (that selection over the recency
  blend). `JudgeRecallPolicy(backend, model, *, pool_factor, fallback=RAW_RECALL_POLICY)`
  (`rerank_judge.py`) asks the resident model to order the pool, each note on one line after its age
  (`memory_age.py`, "(age unknown)" for a date after now, which a clock that ran ahead wrote, so it
  never reads as the newest), under a JSON-schema-constrained request using `rank_bounds(k)`
  (`max_tokens=24 + 8k`, thinking off, trace budget zero) and falls back on any failure; an
  **empty** order is the model declining the pool and returns an empty ranking on the `DEMUR` basis
  without the fallback (ADR-0038 decision 11). A similarity floor was calibrated and **declined**
  (ADR-0038 decision 12).
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

- No text longer than `EMBED_INPUT_CHARS` reaches the `Embedder`, so an exchange of any length is
  recorded and a query of any length recalls; what is stored is always the whole text.
- A tainted turn is dropped from memory by default, or recorded with `tainted=True` and fenced on
  recall, so recall stays trustworthy either way.
- A retrieval hit reports the store's raw similarity and never the key a policy ranked by, so no
  caller can infer an order from it.
- An audit record holds memory ids and scores and never the text a rank declined.
