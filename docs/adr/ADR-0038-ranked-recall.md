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

## Summarizing-window addendum (2026-08-06)

Decision 9 designed where a history summary lives; this records what building it found. Every
claim the decision rested on was re-checked against the tree first, and all of them held:
`SessionStore` still has exactly `append`, `history`, `list_sessions`, `set_title`, `delete`
and `set_pinned`, with **no verb that edits or removes a message**, so a recap of a prefix can
only go incomplete and never wrong; the window's caller is still `assemble_inference_messages`
in `turn_context.py`, awaited to completion by `handle_turn` before it builds the reply's
generator; and `drain_text` still leaves the adapter's acquire block in a `finally`.

Four things the decision did not say, found while implementing it.

1. **`select` needs the session, not just the `async`.** Decision 10 priced the widening as
   `async` alone. A recap cached per session has to know which session it is windowing, and the
   port carried only the history, so the signature is
   `async select(history, *, session_id) -> Sequence[Message]`. This is the same shape of miss
   as decision 1's `query`, in the same session, on the sibling port: a `select` that consults
   anything outside its arguments needs an argument naming what it consults.

2. **The verbs are `set_recap`/`recap` and the value is `HistoryRecap`, not "summary".**
   `SessionSummary` already means a chat-list row and would have sat two declarations away from
   a `HistorySummary` meaning something else entirely. `Recap` says what the value is (an
   account of what came before) with no collision anywhere in the tree; `digest` was the other
   candidate and lost because the tree already spends that word on hashes
   (`secrets.compare_digest`).

3. **The port pair belongs to `SessionStore` for a reason stronger than proximity.** Decision 9
   argued placement from what the state IS (one conversation's working context). The binding
   argument turned out to be lifetime: a recap is a model's account of the same conversation and
   exactly as private as the transcript, so "forget this chat" must take it in the SAME
   transaction. A separate port would have made that a second call that can be forgotten or fail
   alone. The contract test asserts the removal, and the Redis test asserts the key is in the
   delete pipeline.

4. **The fallback is structural, not a policy.** The window returns the inner window's selection
   untouched and can only PREPEND to it, so every failure path (store unreachable, model
   unreachable or failing mid-stream, model returning nothing usable) returns byte for byte what
   ships today. Losing a word the user wrote is not reachable from any state of the summarizer,
   which is the property worth having, since a lost recap costs context and a lost message costs
   the conversation.

**A test that could not fail, caught and fixed.** The lease test first asserted that the reply's
acquire succeeds after selection. Removing `drain_text` from the window did **not** redden it:
the abandoned generator was unreferenced, so asynchronous-generator finalization closed it on the
loop before the reply's acquire, exactly the "at the mercy of the collector" release decision 8
names. The test now asserts that the adapter's acquire block was left with **no `await` between
the assertion and `select`'s return**, which the collector cannot rescue, and it does redden when
the drain is removed. Its twin, which retains an abandoned stream and watches the next acquire
time out, stays in the tree to prove the harness's lock is genuinely non-reentrant.

**Measured, and the default still reflects the cost.** `CORTEX_HISTORY_SUMMARY` ships **off**,
the same call `CORTEX_MEMORY_RECALL=judge` got: the recap answers a question the shipped window
cannot, and it costs a full cortex generation on the turns where the boundary moves. The numbers
are below.

### Measured (2026-08-06)

Run against the real cortex (gemma-4-12B on the 24 GB card, via the gpu compose stack) over a
23-message conversation whose opening three exchanges carry facts a later question depends on and
whose middle is unrelated filler, under a character budget small enough to push those openings out
of the window. Baseline is what ships, the char-budget tail alone. Reproduce:
`packages/inference/tests/test_history_recap_live.py`, integration-marked.

| | char budget (ships) | plus recap |
| --- | --- | --- |
| What the model sees | 9 messages, 295 chars | 10 messages, 831 chars |
| Selection cost, boundary moved | 0.0 s | 11.0 s |
| Selection cost, boundary unmoved | 0.0 s | 0.000 s |
| Reply time to first token | 5.2 s | 4.1 s |
| Answered the follow-up | no | **yes** |

The follow-up was "remind me of my booking reference", whose answer appeared once, in the first
exchange. The shipped window answered "I don't have access to your personal information ... you
should be able to find it in your confirmation email"; with the recap the reply was "Your booking
reference is QH7-4412." The recap kept every fact from the dropped openings (the reference, the
flight time, the hotel, the card to charge) and compressed the filler.

Two things the table understates and one it flatters. **The cached read is free**, at three
decimal places of a second, which is the whole argument for caching: the 11 s is paid once per
boundary move, not per turn. **Time to first token did not get worse** here, and was in fact
lower for the larger prompt, which is prefill noise at this size rather than a finding; what is
real is that the reply's prompt grew 2.8x while its answer got shorter, because the model stopped
hedging. And the flattery: **one corpus, hand-built by the author of the feature**, with a fact
placed exactly where a summary would keep it. It shows the mechanism works. It is not a benchmark,
and 11 s on the turns where the boundary moves is why `CORTEX_HISTORY_SUMMARY` still ships off:
a deployment that would rather wait than forget opts in.

## Untrusted-recap addendum (2026-08-06)

The summarizing-window addendum left one deferral marked as the sharp one: a recap of tainted
turns is not fenced. Settling it found the premise wrong and the real exposure a different shape,
so this records what is true, what was built, and what was deliberately not built.

**The prefix a recap reads holds no tool output.** `TurnEngine.handle_turn` appends exactly two
messages per turn: the raw `Role.USER` text and the `Role.ASSISTANT` reply the output guardrail
already scrubbed. The `Role.TOOL` message carrying an untrusted payload lives in the turn's
working list and dies with the turn, which `Role`'s own docstring states and which the
tainted-memory decline established for the record path. The recap therefore cannot read a tool
result, and the entry's "untrusted tool results in the prefix" was never reachable.

**Nor is there a bit to key a refusal on.** A stored `Message` carries role, text, timestamp,
turn id and the turn-local tool fields, and nothing else; taint is a `TaintLedger` rebuilt per
turn and never persisted, and `SessionStore` has no verb that would report it. So "refuse a recap
when the prefix is tainted", the fail-closed option the deferral imagined, has nothing to read.
Making it readable is a store schema change, and it would only ever narrow a fence that is
cheaper to apply unconditionally.

**What is reachable is the assistant's own quotation, and it is enough.** `SECURITY_PREAMBLE`
expressly permits quoting untrusted content, so a reply to "summarize this email" may carry an
injection verbatim, and that reply is persisted. Two things the recap then did that the plain
window does not:

1. **It made a bare model call over that text under an instruction to process it.** This is the
   summarizer-as-target shape the tainted-memory work declined on the record path, arriving on
   the read path instead. The reasoning that declined it there does not decline it here, because
   there the summary bought no safety over an exchange that was already fenced on recall, whereas
   here the pass is the feature: the alternative is not "store the raw text instead", it is "have
   no recap".
2. **It promoted the answer.** The recap enters as `Role.SYSTEM`, the most trusted position in a
   turn, is cached in Redis, and is folded forward for the life of the session. A laundered
   sentence would therefore outlive by an unbounded margin the assistant message it came from,
   which the window drops.

### Decision: fence both ends, unconditionally, without spreading taint

The recap prompt carries `SECURITY_PREAMBLE` verbatim as its system message and quotes both the
dropped transcript and the previous account inside `wrap_untrusted`, under one nonce minted for
that call, the way a turn's tool results share the turn's. The instruction that names them stays
outside every fence, so the only text the prompt asks the model to obey is text this repo wrote.
The recap then enters a turn through `fence_recap`, wrapped under a **second** nonce minted after
the model has spoken. That ordering is the load-bearing part rather than a detail: a shared nonce
would hand a compromised summarizer the one string that ends its own fence, and a nonce cached
alongside the recap text would be a session-long secret instead of a per-selection one. Neither
wrap takes an argument or sits behind a condition, so no state of the window produces an unfenced
recap; the fence is a property of the only two functions that build these messages, not of a
caller remembering to ask. The recap explains its markers in its own text, because a window
cannot know whether the turn it feeds will also carry the preamble (which is prepended only for a
tool-enabled or already-tainted turn), and an unexplained marker is worse than none.

**Taint is deliberately not spread by a recap**, and this is the one place the decision trades
safety for usefulness knowingly. Spreading it would close the outbound surface (a tainted gated
call is hard-denied) on every turn of every long conversation for the rest of its life, whether
or not a tool ever ran, which is the "too blunt" failure the fence-without-block recall mode is
already open against. It would also be inconsistent: the plain window hands the model the same
assistant messages, unfenced and untainted, on every turn until they age out, so tainting the
narrower derived artifact while its own source stays trusted would be theatre. That inconsistency
is a real finding rather than an excuse, and it is recorded as its own entry in the
untrusted-content area, where it belongs; it is wider than this feature and predates it.

**What it costs.** The recap now reads as data rather than as the assistant's own notes. The
preamble tells the model that fenced content is inert information to analyze or quote, so the
facts should still be usable, but "should" is the word: the measurement in the addendum above ran
before the fence and has not been re-run behind it. The safety direction needs no model (it is
structural, and asserted against what falls outside the fences), but the usefulness direction
does, and it is recorded as open beside the one-corpus entry, which wants the same run.

**Alternatives rejected.** *Refusing the recap on a tools-enabled deployment* is fail-closed and
structural, but it does not close what it claims (a user can paste untrusted text into their own
message in a tool-less deployment too) and it kills the only deployment the feature is interesting
in. *A persisted per-turn taint marker*, which would let both the fence and the refusal be
precise, is a `SessionStore` schema change bought for a narrowing rather than for a protection,
and the unconditional fence is strictly safer than any predicate over it. *Declining the feature
outright* was weighed against the fact that the recap's input is exactly the corpus the plain
window already sends the model; what the recap adds is the call and the promotion, and both are
fixable at their own site, which is what this does.

**The wider entry this opened was settled the same day.** The inconsistency named above, that the
plain window hands the model the same assistant messages unfenced while this feature fences its
derived artifact, was measured rather than argued. The carrier is real but not automatic: asked for
a one-sentence summary the cortex quoted a payload into its persisted reply not once in ten, and
asked for the wording verbatim it did so every time. Replayed out of history on a bare turn with no
preamble, that quotation was obeyed two times in three, the model appending the payload's own token
to an unrelated answer; behind the standing preamble the identical replay was obeyed not at all.
Nothing was built at the plain window, and the reasoning for fencing this one is unchanged, since
what the recap adds over the window is the model call and the promotion to a durable system-role
artifact rather than the mere presence of the text. The numbers, the two premises the entry got
wrong, and the residue still open are at the [ADR-0013](ADR-0013-untrusted-content.md)
replayed-quotation addendum.

### Re-measured behind the fence, and the default stays off (2026-08-06)

The addendum above left one thing owed: the usefulness table was taken before the fence, and
fencing tells a model it is reading quoted data, which could plausibly make it hedge or refuse.
The re-run was asked for by the user together with a decision to turn the summary on if the
number held. The number for the fence held. **The default still does not move**, and the reason
is something the re-run found on the way rather than the fence.

Same corpus, same shape, same test (`packages/inference/tests/test_history_recap_live.py`), run
three times against the real cortex through the gpu stack:

| | char budget (ships) | plus recap, fenced |
| --- | --- | --- |
| What the model sees | 9 messages, 295 chars | 10 messages, 1283 to 1317 chars |
| Selection cost, boundary moved | 0.0 s | 15.2 s / 23.6 s (11.0 s unfenced) |
| Selection cost, boundary unmoved | 0.0 s | 0.000 s |
| Reply time to first token | 12.7 s / 7.1 s | 5.3 s / 2.7 s |
| Answered the follow-up | no, 3 of 3 | **yes, 3 of 3** |

**The control fired every time**, which is the first thing to check and is now asserted rather
than printed: the shipped window replied "I don't have access to your personal information" in
all three runs, so the arms really are being compared. **The fence did not cost the answer.**
Behind it the reply is still "Your booking reference is QH7-4412.", identical to the unfenced
reading, and no fence marker reached the reply, which is asserted too. What the fence costs is
characters: the same account, 484 chars of it, arrives as a 1022-char message once the standing
preface and the two markers are around it, so the recap message roughly doubled while the account
inside it did not change.

**What stops the default is the case a default runs in.** One fold is not what a long
conversation does; it folds again at every boundary move, each fold reading the previous account
rather than the original turns. Measured over three independent sessions of five folds each, the
booking reference survived into the final account **2 of 3 times** and reached the reply the same
2 of 3. The round that lost it lost the whole opening: the final account named the adapter, the
trains and the museums, and neither the reference, nor the hotel, nor the card to charge. A recap
of a prefix can only go incomplete rather than wrong, which is the property the cache rests on,
and this is what incomplete looks like when it compounds.

**And the fold is far more expensive than 11 s.** Across the same runs a fold cost 14.5 s to
30.8 s typically, with outliers of 77.3 s and **224.5 s**. The server's own numbers say why: that
224.5 s fold decoded 6286 tokens for a 370-token prompt, and a typical one decodes 400 to 850,
while the account it stores is 330 to 650 characters, which is 80 to 160 tokens. Most of every
fold is reasoning that `drain_text` drops on the floor, and nothing bounds it: `RECAP_MAX` cuts
the text after the model has spoken, not the request before it. This is the same gap the session
title has, where a reasoning cortex can spend a whole budget thinking, and it wants the same
missing thing, a way for the inference port to ask for no thinking.

**Decision: `CORTEX_HISTORY_SUMMARY` stays `False`.** The user's decision to turn it on was made
against 11 s per boundary move and a single measured fold, and this re-run falsified both halves
of that premise, so shipping it on would be shipping against numbers rather than on them. A turn
that stalls for as long as 224 s with nothing on screen saying why, and a 1 in 3 chance of the
account quietly forgetting what the conversation opened with, is not a default. It stays exactly
one env variable away for a deployment that would rather wait than forget, which is what it was
built to be.

**What would have to change for it to move**, all four recorded in the refinements backlog:

1. **A token cap on the recap request.** Already the recorded deferral, now with a number on it:
   it is what bounds the 224 s tail, and it is the cheapest of the four.
2. **Thinking off for the fold.** Most of the wall time is discarded reasoning. The inference port
   cannot express it yet, which is an existing entry of its own.
3. **A minimum fold size.** The other half of the recorded deferral. Fewer folds is directly less
   compounding, and the loss measured here is a compounding loss.
4. **Something on screen while it folds.** Nothing tells the user the turn is doing extra work.
   The overlay's whisper breathes its accent mist from the moment they press enter, so a long
   fold looks exactly like a slow model, and the `StatusUpdate` path that would say otherwise
   (the swap conductor and the spawn batch both use it) never reaches a history window, because
   `HistoryWindow.select` takes no progress sink. The sink itself is already in the right place:
   `SeamProgressSink` is per Converse stream, `build_history_window` is called inside the
   per-stream `capabilities` closure that has one, and an event emitted there rides the stream's
   own queue rather than the turn generator, so it would surface during assembly. That is a port
   change and it was not taken here, on a knob that is staying off.

Retention is reported by the live test as a rate rather than asserted, because asserting a
probabilistic model behaviour would pin the model rather than the code; what it asserts every
round is that the folds really happened, that the control really failed to answer, and that no
fence marker reached the user.

### The fold made cheap, and the default moves (2026-08-06)

The addendum above held `CORTEX_HISTORY_SUMMARY` off and named four things a default move waited
on: a token cap on the fold's request, thinking disabled for a pass whose thinking nobody reads,
a minimum fold size, and something on screen while it folds. All four are built and all four are
measured. **The default is now `True`**, which is the user's standing decision finally carried by
its own numbers rather than shipped over them.

**The diagnosis held on every point.** The fold's request is built in `SummarizingHistoryWindow`
and issued through `drain_text`, which called `backend.stream(model, messages, schema=schema)`;
`_build_payload` put `model`, `messages` and `stream` on the wire and nothing else, so there was
no `max_tokens` and no `chat_template_kwargs`. `RECAP_MAX` was applied by `clean_recap` to text
the model had already finished writing. And `drain_text` keeps only `TextChunk`, so a reasoning
model's whole `ReasoningChunk` stream was decoded, paid for, and dropped before the caller saw a
character of it.

#### Thinking off, per request

`InferenceBackend.stream` gains `bounds: GenerationBounds | None`, a frozen value carrying
`max_tokens` and `thinking`. The llama.cpp adapter renders `thinking=False` as
`chat_template_kwargs: {"enable_thinking": false}`, which is the per-request twin of the server
flag the subagent tier bakes into its compose command; the other documented lever,
`--reasoning-budget 0`, still does not work on this build, so this is the one that does. It was
verified against the shipped cortex before any of it was written rather than assumed.

Per request rather than per server is the whole point. One resident cortex both answers the user,
where deliberation earns its wait and the compose file deliberately leaves it on, and folds a
recap, where the deliberation is discarded by construction. A server flag cannot tell those apart.
`None` stays the default and emits no key, so every user-facing reply sends the byte-identical
request it always did.

#### A cap, sized from the account and paired with the switch

`RECAP_BOUNDS` is `max_tokens=512, thinking=False`. 512 is `RECAP_MAX` said in the request's own
unit: 2000 characters at the roughly 4 chars per token the character budget already assumes, and
about six times the account this prompt actually produces. The two bounds now agree, so neither
can silently truncate under the other.

**Capping without the switch is a trap this repo measured rather than inherited.** A reasoning
model spends its budget deliberating first, so a cap sized from the wanted answer is reached with
nothing said: the identical fold prompt at `max_tokens` 160 and 256 with thinking on both came
back `finish_reason: "length"` carrying 624 and 988 characters of `reasoning_content` and an
**empty** reply. Even at the shipped 512 it is a coin flip, which the live suite reports rather
than asserts: one run decoded the full 512 and returned 92 unusable characters, another finished
its thinking in 404 and returned a usable account. Paired with `thinking=False` the same cap is
never approached, because the fold decodes 61 to 163 tokens.

**Hitting a bound degrades to the plain window, never to half a sentence.** `clean_recap` now
returns `""` for a reply that does not end a sentence and for one longer than `RECAP_MAX`, and
the window rejects it. Trimming to the last full stop was considered and rejected: storing a
truncated account would advance the recap's `covers` to a boundary it only half describes, and
because the next fold reads from `covers` forward, the turns the missing tail never reached would
be lost for good rather than for a turn. Refusing keeps the boundary where it is, so the next
fold reads them again.

#### A floor under a fold, clamped to the window

`SummarizingHistoryWindow` takes `min_dropped_chars` (`CORTEX_HISTORY_RECAP_MIN_CHARS`, default
2000). Below it a boundary move does not spend a model pass. **Deferring is not skipping**: the
boundary the stored account covers does not move, `history[covers:boundary]` is what the next fold
reads, and it therefore picks up everything deferred since. Characters are the unit because that
is what the budget it wraps is denominated in, and 2000 is `RECAP_MAX` again: below one account's
worth of new material there is less to fold in than the account being folded into, and folding
again is exactly what compounds a recap's losses.

**What a deferred fold costs is a bounded gap.** Between `covers` and the boundary sits
conversation in neither the window nor the account, and it is invisible until the next fold runs.
The gap is always smaller than the floor, which is why `build_history_window` clamps the floor to
the character budget: a fold's cost is flat, so an absolute floor is the right shape for deciding
whether the pass is worth it, but the gap is only bearable while it is small next to the window,
and a floor above the budget would leave more unaccounted for than the model can see at all. The
clamp is at the composition root because that is the one place both numbers are in hand.

#### The fold says so while it runs

`HistoryWindow.select` gains `progress: ProgressSink | None`, and the summarizing window emits one
`StatusUpdate(state="folding", detail="summarizing the earlier part of this conversation")` before
the pass, and only when a pass is really about to happen (a cache hit and a deferred fold both
emit nothing, since neither costs the user a second). The sink is handed per CALL rather than held
on the window, matching the dispatch stamp's discipline: a sink belongs to one `Converse` stream
while a window is a policy, so passing it in keeps a shared window correct for every stream
instead of relying on one being built per stream. `assemble_inference_messages` passes
`caps.progress`, and because the sink writes onto the stream's own queue rather than through the
still-suspended turn generator, the chip appears while assembly is running. No overlay change was
needed: a generic status already renders as a chip, which its own suite already pins.

#### Measured, in the same shape as the run that held the default

Same corpus, same test, same stack. The pricing arm sends the identical fold prompt twice, once
with `bounds=None` (the request that shipped) and once with `RECAP_BOUNDS`, and the counters are
llama-server's own `eval time` lines:

| one fold, identical prompt | unbounded (before) | `RECAP_BOUNDS` (now) |
| --- | --- | --- |
| Decoded tokens | 378, 531, 602 | 88, 87, 88 |
| Wall time | 13.6 s, 18.9 s, 21.5 s | 3.9 s, 3.8 s, 3.9 s |
| Account produced | 345 to 367 chars | 369 to 382 chars |

The account did not get shorter. It got slightly longer, because none of the budget went on
deliberation. Across the staged five-fold arm a fold decoded **61 to 163 tokens** and cost **2.9 s
to 6.2 s**, against the recorded 400 to 850 typical, 6286 worst, and 14.5 s to 224.5 s.

**Retention moved from 2 of 3 to 3 of 3.** Three independent sessions of five compounding folds
each, the arm that held the default off: the booking reference survived into the final account and
reached the reply every round, and the accounts now carry the hotel, the card, the adapter, the
museums and the transit advice together rather than keeping recent filler and dropping the
opening. The control fired all three rounds and no fence marker reached a reply, both asserted.

At the shipped floor the same conversation folded **once over five boundary moves**, for 3.4 s of
model time in total, retention 3 of 3. That run also shows the cost honestly: the account covered
10 of the 20 dropped messages and the other 10 sat in neither place, under the floor, which is the
gap the clamp bounds.

#### Decision: `CORTEX_HISTORY_SUMMARY` defaults to `True`

The user asked for this on and accepted a real cost; what the previous two passes refused to do
was ship it over numbers rather than on them. The numbers now say a boundary move costs a few
seconds with a chip on screen explaining them, the tail is bounded by a cap rather than by luck,
most boundary moves cost nothing at all, and the account keeps what the conversation opened with.
A deployment that would rather forget than wait sets the variable to `false`, which is the same
one switch it always was, pointing the other way.

**What is still true and recorded as open.** The corpus is one hand-built conversation, by the
author of the feature, with the needed fact placed where a summary would keep it, and three rounds
is a small sample: the standing one-corpus entry does not close, and it is now the only thing
between this feature and a claim about real conversations. Nothing has been measured about a
cortex under load, and the fold still lands on the turn that triggers it.
