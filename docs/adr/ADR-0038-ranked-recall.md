# ADR-0038: A ranked `select`, its audit trail, and where a history summary lives

Date: 2026-08-06. Status: accepted.

## Context

Two deferred refinements in two areas had been recorded for weeks as one design problem:
session-history summarization ([session-history.md](../refinements/session-history.md)) and the
model-based reranker ([memory.md](../refinements/memory.md)). Both were blocked on a synchronous
`select` going async (`HistoryWindow.select`, `RecallPolicy.select`), both inherited the same
non-reentrant GPU-lease hazard, and a third entry, the blended-relevance field, had been
**declined** in ADR-0008's relevance-field addendum for want of a consumer while explicitly saying
that a consumer would reopen it as a `select` widening rather than as a field. A fourth, recall
observability, was opened by that same decline and named as the consumer that would do it.

The 2026-07-16 audits priced the two mechanical blockers and found both milder than their entries
read, and the hardware clause ("the cortex tier does not fit the dev GPU") was struck 2026-07-19.
What was left binding was design work: `select` should be widened **once**, for all three of its
deferred consumers, and summarization's cache-versus-recompute question was undecided. This ADR is
that design work.

### What the code actually says (re-derived 2026-08-06, before designing)

Per the backlog's own standing warning that an entry is a record of what somebody once measured and
never a reading of what the tree does now, every claim was re-checked against `HEAD`:

- **`HistoryWindow.select(history) -> Sequence[Message]` is sync, one implementer.** Held.
  `windowing.py`; `CharBudgetHistoryWindow` is the only implementer in the tree.
- **`RecallPolicy.select(hits, *, now, k) -> Sequence[ScoredMemory]` is sync, four implementers.**
  Held. `rerank.py` holds the port and `RawRecallPolicy`; `rerank_policies.py` holds the three
  opt-in policies, and none of them calls another's `select`.
- **Each has exactly one production caller and both callers are already async.** Held in
  substance, **wrong in location**: both entries name `_inference_messages` in `engine.py`, a
  method that no longer exists. The window's caller is `assemble_inference_messages` in
  `turn_context.py` (the ADR-0029 decision 15 split), still `async`; the policy's caller is
  `MemoryRecaller.recall` in `recall.py`, still `async`. The widening is one `await` each, as
  claimed.
- **The GPU lease is a non-reentrant `asyncio.Lock` held for a stream generator's lifetime.**
  Held. `SingleResidentModelManager.acquire` (`model.py`) is an `asynccontextmanager` around
  `asyncio.Lock`; `LlamaCppBackend.stream` (`backend.py`) opens that context around its whole SSE
  loop, so the lock is held until the generator is exhausted or closed.
- **Selection runs before the reply takes the lease.** Held, and more firmly than the entries
  claim. `handle_turn` awaits `assemble_inference_messages` (which is where both selections run)
  at one statement, and only afterwards builds `stream_tool_loop`; because that is an async
  generator, its first `acquire` does not even happen until `stream_turn_events` is first
  iterated, several statements later. At selection time the turn holds nothing.
- **The title generator is the precedent for a sequential acquire.** Held as a fact, and it is a
  weaker precedent than it reads. `generate_title` drained `backend.stream(...)` inside an
  `async for` comprehension, which exhausts the generator and releases the lock whenever the drain
  finishes or the stream itself raises. What it does not do is state anywhere that leaving the
  acquire block is the requirement, so the next caller that stops early inherits nothing. The engine
  states it one screen away: `handle_turn` closes its event generator with `await events.aclose()`
  in a `finally`. So the discipline this ADR imposes is the engine's rather than the title
  generator's, and the title generator adopts it.
- **`select` carries the query.** It does not, and neither entry noticed. `RecallPolicy.select`
  took `(hits, *, now, k)`, so a policy that ranks by what a memory says had nothing to rank
  against. Widening the signature therefore means three changes, not two.

## Decision

1. **`RecallPolicy.select` becomes `async` and returns a `Ranking`, in one change, now.** The
   signature becomes
   `async def select(hits, *, query, now, k) -> Ranking`, the `query` being what a model rank
   needs and what nobody had noticed `select` did not carry. This is the single widening the backlog
   reserved for three consumers, and all three are served by it: a model rank needs the `async`,
   the blended-relevance field needs the richer return, and an observability sink needs a rank key
   with a stated meaning. Widening it twice was the outcome the recorded guidance existed to
   prevent.

2. **The widened return is a ranking, not a wider hit.** `Ranking` is a frozen value with
   `hits: tuple[RankedMemory, ...]` and `basis: RankBasis`; `RankedMemory` pairs a `ScoredMemory`
   with the `key: float` the policy actually ordered by. This is what keeps the change from being
   a grab bag: the store's `ScoredMemory.score` keeps its one meaning (the raw cosine, which is
   the invariant ADR-0008's relevance-field addendum kept when it declined the field), and the
   policy's own quantity lives on the policy's own return type, where the policy is the thing that
   computed it. The basis rides the ranking rather than each hit because one `select` call ranks by
   exactly one quantity.

3. **The declined blended-relevance field is reversed, and lands as `RankedMemory.key`.** ADR-0008's
   relevance-field addendum declined it on two findings: nothing read a recall score, and there was
   no single blend to surface. The first is now false by construction (decision 5 gives it a
   reader), and the second is answered rather than dodged, by decision 4. The decline stands as
   correct for the design it declined, which was a second field on `ScoredMemory`; it is the
   *placement* that changes, not the verdict on that placement.

4. **The rank key names what it is, and whether it can be compared.** `RankBasis` is a designed
   one-word family, sibling to the overlay's registries, for **how a memory came to mind**:

   | Basis | Policy | The key is | Comparable across a result |
   | --- | --- | --- | --- |
   | `ECHO` | `RawRecallPolicy` | the store's raw cosine | yes |
   | `EMBER` | `RerankingRecallPolicy` | similarity still warm: the recency blend | yes |
   | `SPREAD` | `MmrRecallPolicy` | likeness less what is already said: the MMR objective | no |
   | `SWEEP` | `RecencyMmrRecallPolicy` | Ember, spread out: MMR over the blend | no |
   | `VERDICT` | `JudgeRecallPolicy` | the model's own placing, normalized to (0, 1] | yes |

   The family's structure carries the finding that closed the original entry: `SPREAD` and `SWEEP`
   are computed against the kept set at pick time and are therefore **not** comparable between hits,
   while `ECHO`, `EMBER` and `VERDICT` are. `RankBasis.comparable` states it on the type, so a
   consumer that plots or thresholds a key cannot get it wrong by reading a float with no
   provenance, which is precisely the confusion the decline was protecting against.
   Alternates considered and rejected: a plain-descriptive set (`Likeness`, `Warmth`, `Breadth`,
   `Balance`, `Judgment`), which reads as a glossary rather than a family, and a technical set
   (`Cosine`, `Blend`, `Margin`, `Judge`), which names implementations that may change. Within the
   family, `Sense` was the closer sibling to `Echo`'s sensory register, and `Verdict` won anyway:
   it is the only candidate whose word says that a *decision* was made by something that can be
   wrong, which is the operational fact an operator reading the trail needs.

5. **Recall observability is a port plus a sink adapter, modelled on `ToolAuditSink`.** A new
   `RecallAuditSink` port takes one `RecallAudit` per recall: the session, the query, the pool
   size, the requested `k`, the ranking (basis and keyed hits), and the time. `MemoryRecaller`
   gains an optional `audit` collaborator and awaits it after selecting, so a recall is audited
   whichever policy ran. The shipped `LoggingRecallSink` writes one structured line and, exactly as
   `LoggingAuditSink` logs a tool result's size rather than its content, logs each hit's **id,
   score, key and taint bit and never its text**: memory text is conversation content and has no
   business in container logs. The port carries the full hits so a different sink can decide
   otherwise; the shipped one does not.

6. **`MemoryRecaller.recall` keeps returning `Sequence[ScoredMemory]`.** The ranking is the
   *policy's* return, not the recaller's. Turn assembly wants hits, and widening the recaller's
   return would push the ranking into `turn_context.py`, the seam, and eventually the proto, for no
   consumer. The recaller unwraps.

7. **The model rank ships as `JudgeRecallPolicy`, a fourth opt-in policy over the
   `InferenceBackend` port.** It over-fetches like the others, sends the candidates to the resident
   cortex as a numbered list under a JSON-schema-constrained request (the ADR-0028 mechanism), and
   turns the returned order into keys normalized to (0, 1] so `VERDICT` is comparable across the
   result. It takes a **fallback policy** (default `RAW_RECALL_POLICY`): a model failure, a
   malformed reply, or an empty candidate list falls back rather than failing the turn, and the
   emitted basis is then the fallback's, so the trail says what actually ranked. It lives in the
   core because it depends on nothing but ports, like `SubagentRunner`; `CORTEX_MEMORY_RECALL=judge`
   selects it at the composition root.

8. **A model pass during selection must drain and close its stream at a point in the code.** The
   rule: any selection-time inference goes through `drain_text` (`drain.py`), which consumes the
   stream and closes it in a `finally`. This is the engine's own discipline
   (`await events.aclose()` in `handle_turn`), applied one layer down, and `generate_title` moves
   onto the same helper as part of this change so there is one answer rather than two. With it, the
   sequencing is safe by construction: selection completes before `handle_turn` iterates the reply's
   generator, so the reply's `acquire` is the second acquire of a sequence, never a nested one.

   Honest scope of the close: today every caller consumes the stream to exhaustion, and a generator
   that raises runs its own `finally` on the way out, so the explicit `aclose` is not yet the thing
   that releases the lease. It is what makes the release survive the first caller that stops early
   (a token cap, a first-answer-wins race), which is exactly the abandoned-stream shape the backlog
   named as the hazard. The port promises only an `AsyncIterator`, so the close is guarded and both
   shapes are tested.

9. **A session summary is cached in the store, not recomputed per turn, and the reason is that
   history is append-only.** The undecided question the summarization entry named is settled here so
   the remaining work is implementation:
   - **Where.** Redis, behind the `SessionStore` port, alongside the session's other hot state
     (its messages and its title). Not `MemoryStore`: a summary is in-context working state for one
     conversation, derived and disposable, not durable cross-session knowledge, and putting it in
     pgvector would make it recallable into other sessions, which is a different feature.
   - **What invalidates it.** Nothing, which is the point. `SessionStore` has `append`, `history`,
     `set_title` and a whole-session delete; there is no verb that edits or removes a message. A
     summary of a **prefix** of an append-only log can therefore never become wrong, only
     incomplete. So the cache is keyed by the boundary it covers (the session, plus how many
     messages are summarized), a new summary is written only when the window's boundary moves
     further forward, and each new summary folds the previous one together with the newly dropped
     turns (a rolling summary). A deleted session takes its summary with it. There is no
     invalidation path to get wrong, which is why caching is safe here and would not be in a system
     with an edit verb.
   - **What recompute would cost.** One full cortex generation over the dropped prefix on **every**
     turn, serialized ahead of the reply and therefore added directly to time-to-first-token, plus
     a second GPU serialization point per turn for every turn of every session. The cached form
     pays that once per boundary move, which is once every several turns.
   - **How it survives a model swap.** By construction: it is text in Redis, written after the pass
     completes and read back by whatever model is resident next. Nothing lives in a model process
     or a KV cache, and a swap between the write and the next read is invisible.

10. **`HistoryWindow.select` stays sync until the summarizing window lands with it.** Widening it
    now would be the empty async layer the entry warns against: its only implementer has a
    synchronous body and its only deferred consumer is the summarizer. The two land together. This
    is not the same call as decision 1, and the difference is the number of waiting consumers:
    `RecallPolicy.select` has three, `HistoryWindow.select` has one.

## Consequences

- `select` is now `async` on a port whose four existing implementers have synchronous bodies. This
  is gate-clean here (the `unused-async` rule, `RUF029`, is preview-only and this repo runs ruff
  without preview), re-verified in this session rather than taken from the entry.
- Every existing policy gained a `RankBasis` and now returns a keyed ranking, which is behaviour
  preserving: order and membership are byte-for-byte what they were, and the tests that pin them
  were kept pinning them by unwrapping.
- `MemoryRecaller` gained one optional collaborator. A deployment that sets nothing is unchanged.
- The recall path has an audit trail for the first time, and it is the trail that would have
  answered the question the relevance-field decline had to write a throwaway script for.
- `select` gained a `query` argument as well as the two the entries predicted. Neither entry saw
  this: a policy that ranks by what a memory *says* needs the question, and `select` carried only
  the hits, the time and `k`. So the widening is async, plus `query` in, plus `Ranking` out. This
  is the one place the audits' cost estimate was too small.

## Measured

The judge was run against the real cortex (gemma-4-12B on the 24 GB card, via the gpu compose stack)
over ten notes and six questions, each question worded so that its answer shares none of its
vocabulary while a distractor shares plenty, since a corpus of paraphrases would flatter both
rankings and settle nothing. Baseline is what ships: the raw cosine order over real nomic
embeddings from the CPU embedder. Reciprocal rank of the correct note, at `k=3`:

| | cosine (ships) | judge |
| --- | --- | --- |
| Mean reciprocal rank | 0.917 | **1.000** |
| Correct note placed first | 5 of 6 | **6 of 6** |
| Fell back to cosine | n/a | 0 of 6 |

The one question the cosine got wrong ("is it alright to release at the end of the week?") ranked a
note about flight prices above the release policy, on the word "week"; the judge placed the release
note first. The other five it already had first, so on this corpus the judge is better on one
question of six and no worse on any.

Two things the run showed that the number does not. The judge **returns fewer hits than `k`**,
because it is told to leave out notes that do not help: where the cosine always filled three slots
with two distractors, the judge returned one or two notes and nothing else, so the win in the turn's
context window is larger than the win in the ranking. And it costs a full cortex generation per
recall (about 12 seconds per question in this run, on a cold context), which is why the default
stays `raw` and this is opt-in. The corpus is small and hand-built by the author of the policy,
which is the honest caveat: it shows the mechanism works and is not a benchmark.

Reproduce: `packages/inference/tests/test_rerank_judge_live.py`, integration-marked.

## Deferred

Recorded in [session-history.md](../refinements/session-history.md) and
[memory.md](../refinements/memory.md) with their lines on
[the index](../refinements/index.md):

- **The summarizing history window itself.** Its design question is settled by decision 9 and its
  lease discipline by decision 8, so what remains is implementation: the `SessionStore` summary
  verbs (port, fake, Redis adapter, contract test), a `SummarizingHistoryWindow`, the `async`
  widening of `HistoryWindow.select` alongside it, and the config. **Trigger:** it is the next
  slice in this area; nothing blocks it now.
- **A cross-encoder rank.** Decision 7 ships the LLM-judge form of the model reranker. A
  cross-encoder is the other form and wants a different port (a scoring model, not a chat
  completion), so it is a new adapter rather than a policy. **Trigger:** a measured shortfall of
  the judge on a real corpus, or a latency budget the judge cannot meet.
- **Auditing the candidates that were dropped.** `RecallAudit` carries the kept hits and the pool
  size, not the rejected candidates' keys, because for `SPREAD` and `SWEEP` a non-picked
  candidate's key is not even well defined (it depends on the kept set at each step).
  **Trigger:** the first investigation that needs to know why a specific memory was *not* returned.
