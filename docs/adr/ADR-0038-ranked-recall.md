# ADR-0038: A ranked `select`, its audit trail, and where a history summary lives

Date: 2026-08-06. Status: accepted.

## Context

Two deferred refinements in two areas had been recorded for weeks as one design problem:
session-history summarization ([session-history](../refinements/index.md#session-history)) and the
model-based reranker ([memory](../refinements/index.md#memory)). Both were blocked on a synchronous
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

Recorded in [session-history](../refinements/index.md#session-history) and
[memory](../refinements/index.md#memory) with their lines on
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

## Bounded-side-calls addendum (2026-08-06)

The cheap-fold addendum above bounded one caller of `drain_text` and recorded its own residue: the
session title and this ADR's own recall rank ran the same discarded-thinking pass and still sent no
bounds. Both are bounded here, each from what its answer actually is, and the rank's measurement
reopens the question of its default.

**Re-derived from the code before anything was written**, per the standing rule that an entry
records what somebody once measured rather than what the tree does now:

- `generate_title` called `drain_text(backend, model, messages)` with no schema and no bounds, and
  `JudgeRecallPolicy.select` called it with `schema=ORDER_ENVELOPE` and no bounds. Both held.
- Both discard the model's deliberation before their caller sees it, because `drain_text` keeps
  `TextChunk` and drops `ReasoningChunk`. Held, and it is the whole argument for the switch.
- What each answer has to be: a title is a handful of words that `clean_title` collapses and cuts
  to `TITLE_MAX`, which is 48 characters; a rank is `{"order": [n, ...]}` and nothing else, because
  the request is schema-constrained.

**Three things the residue did not say, found by measuring rather than by reasoning.**

1. **A schema does not protect a constrained reply from a cap.** The concern this addendum started
   with was that a grammar might interact with `max_tokens` in some way prose does not. It does
   not protect it at all: the rank prompt capped below its answer came back as `{"order":`, and one
   capped further came back as an opening markdown fence. Neither is JSON, so `parse_order` returns
   empty and `select` takes the fallback, which is the same degraded path an unreachable model
   takes. That is the whole interaction, and it is why the cap here is generous rather than snug:
   running into it costs the entire judgement rather than a candidate off the end.
2. **The trap the fold measured as a coin flip is a certainty on both of these.** The identical
   title prompt capped at 16, 32 and 64 tokens with thinking left on came back `finish_reason:
   "length"` with an **empty** reply three times in three, and the rank prompt did the same at the
   same three caps. The fold could sometimes finish thinking inside 512; a title cannot, because
   the answer is four tokens and the deliberation before it is hundreds.
3. **The title's cap cannot change the title that gets stored**, which the recap's cannot claim.
   `clean_title` keeps 48 characters, and a reply that reaches 32 tokens has already written past
   them, so the cut lands beyond the stored text. Where the fold had to refuse a truncated account
   outright (storing one would advance a boundary it only half describes), a truncated title is
   simply a title with the same first 48 characters.

### The two bounds and their sizes

`TITLE_BOUNDS` is `max_tokens=32, thinking=False` (`session_title.py`). 32 is `TITLE_MAX` said in
the request's own unit with room to spare: 48 characters is 12 tokens at the roughly 4 characters
per token this repo's character budgets assume, and eight times the four tokens a title actually
costs. A test pins the relation rather than the number, so lowering the cap under twelve tokens
reddens the suite instead of quietly starting to cut stored titles.

`rank_bounds(k)` is `max_tokens=24 + 8k, thinking=False` (`rerank_judge.py`), and it is **computed
rather than fixed** because unlike prose this reply's length is known before it is asked for:
`ORDER_ENVELOPE` admits an array of numbers and nothing else, so the only thing that varies is how
many the caller allowed. The envelope's own punctuation measured 14 to 16 tokens, JSON decoding at
roughly a token per character, and each further candidate adds a comma, a space and its digits. A
constant sized for today's `k` of 5 would have started truncating silently the day a deployment
recalled more, and silently is the operative word: the degraded path is a fallback whose only trace
is a `RankBasis` of `ECHO` on the audit line.

**The sequencing is untouched, and that is checked rather than assumed.** Neither change moves a
call: the title still runs after `handle_turn` closes the reply's event generator, and the rank
still runs inside `assemble_inference_messages`, which `handle_turn` awaits to completion before it
builds the reply's generator. Both still go through `drain_text`, so the adapter's `acquire` block
is still left in a `finally`. The live runs are evidence of the same thing from the other side:
each drives several sequential drains through one `SingleResidentModelManager`, whose lock is
non-reentrant, so a lease held across any of them would have deadlocked the run rather than
reported a number.

### Measured (2026-08-06)

Both runs are against the real cortex (gemma-4-12B on the 24 GB card, via the gpu compose stack),
in the same shape as the fold's pricing arm: the identical prompt each way, wall time from the
test, decoded tokens from llama-server's own `eval time` lines. Reproduce:
`packages/inference/tests/test_session_title_live.py` and
`packages/inference/tests/test_rerank_judge_live.py`, both integration-marked.

| one title, identical prompt | unbounded (before) | `TITLE_BOUNDS` (now) |
| --- | --- | --- |
| Decoded tokens | 277, 235, 303 | 4, 4, 4 |
| Wall time | 9.7 s, 7.9 s, 10.4 s | 0.3 s, 0.2 s, 0.3 s |
| Title produced | Cat Sleeping Habits, Cat Sleeping Preferences, Cat Sleeping Habits | the same three, run for run |

The title did not change. It is the same words in the same runs, which is the strongest form the
result could take: the deliberation the pass was paying for was not contributing to the answer it
kept. The trap arm at the same cap with thinking on decoded the whole 32 tokens in 1.0 s and
returned nothing at all.

The rank was scored twice over the same corpus as the original measurement, ten notes and six
questions, at `k=3`, against the same cosine baseline. The middle column is the request the policy
used to send, rebuilt in the test out of the same prompt and envelope with no bounds on it, since
the policy itself can no longer send it:

| | cosine (ships) | judge, unbounded | judge, bounded (now) |
| --- | --- | --- | --- |
| Mean reciprocal rank | 0.917 | **1.000** | **1.000** |
| Correct note placed first | 5 of 6 | **6 of 6** | **6 of 6** |
| Fell back to cosine | n/a | 0 of 6 | 0 of 6 |
| Decoded tokens per rank | n/a | 448 to 613 | 12 to 22 |
| Cost per recall | 0.0 s | 18.4 s | **0.9 s** |

**The bounded judge is the same judge.** It returned the identical note for all six questions, it
still returns **fewer** hits than `k` (one note per question here, where the cosine filled three
slots with two distractors), and it still placed the release note first on the question the cosine
loses on the word "week". Roughly 0.2 s of the 0.9 s is evaluating the pool prompt, which no bound
touches, and the rest is a dozen tokens of decoding.

### The judge's default: a recommendation, not a flip

`CORTEX_MEMORY_RECALL` **stays `raw` in this change**, and the recommendation is to move it to
`judge` for any deployment that has memory on at all. (Taken 2026-08-08, after the turn-cost
measurement the user asked for first; the turn-cost addendum is the last section of this ADR.)

The reason the default was `raw` was cost and only cost: the original measurement said the judge
was better on this corpus and priced it at about 12 seconds per recall, and the choice to leave it
off was made against that number by the user. The number is now 0.9 seconds, the quality is
unchanged, and the premise the choice rested on is therefore gone. That is a recommendation rather
than a flip because the standing decision is the user's own, and because two things a default has
to answer for are still true. **A rank runs on every turn that recalls**, unlike the fold, which a
cache pays for once per boundary move, so 0.9 s is added to time to first token on every such turn
rather than amortized across several. And **the corpus is still ten notes and six questions, hand
built by the author of the policy**, worded so that the answer shares no vocabulary with the
question while a distractor shares plenty; it shows the mechanism works and it is not a benchmark.
A deployment sets one variable either way, and the audit trail (`CORTEX_MEMORY_RECALL_AUDIT=1`)
says which policy actually ranked each recall, so the move is observable after the fact.

The one open item this closes on the way is the title's own: the reasoning cortex that spent 13,882
characters on thinking and returned no title (ADR-0021 titles addendum) was waiting on exactly this
lever, and `TITLE_BOUNDS` is it. `CORTEX_GENERATE_TITLES` still ships off, for the reason that
survives: it is an extra inference call per new session, now a cheap one.

### The corpus widened (2026-08-06)

The caveat the recommendation above carries about its own evidence is the one this section
answers. Ten notes and six questions, every one of them the single case the judge was bought for,
is a demonstration of a mechanism and not a measurement of a default. So the input was widened to
41 notes and 26 questions across six categories (`packages/inference/tests/recall_corpus.py`,
scored by `test_rerank_judge_wide_live.py`, both integration-marked), and only the first category
is the case the original corpus was made of.

**Written by the same interested party, and that caveat does not go away.** The agent that
recommends the judge wrote these notes and these questions; no sample of real memories was
involved. What changed is the direction of the bias rather than its presence. The original corpus
could only produce the answer it was cut for, because every gold note answered in words its
question never used while a distractor echoed the question's vocabulary. This one is built to be
adversarial to its author's conclusion: `LEXICAL` questions are answered in their own words, so
the embedding is already right and a judge can only subtract; `TWIN` puts two near-duplicate notes
in the pool differing in the one detail asked for; `STALE` competes a superseded version against
the current one with the recency signal in the prose alone, since the rank prompt carries no
timestamps and neither ranking may be credited for one; `CLAUSE` buries the answer in a
subordinate clause of a note about something else; and `ABSENT` asks four questions **nothing in
the corpus answers**, where the correct result is no hit at all.

The pool is the shipped width rather than the whole corpus. `MemoryRecaller` over-fetches
`k * pool_factor`, so at the default `pool_factor` of 4 and `k` of 3 the judge sees the cosine's
top 12 of 41 and never sees anything the cosine left out. The gold note was inside that pool for
all 22 answerable questions, so nothing below is a pool miss in disguise.

| category (n) | cosine (ships) | judge (bounded) | reversed (control) |
| --- | --- | --- | --- |
| `TRAP`, no shared words (6) | MRR 0.806, first 4/6 | **MRR 1.000, first 6/6** | MRR 0.000 |
| `LEXICAL`, answer shares them (4) | MRR 1.000, first 4/4 | MRR 1.000, first 4/4 | MRR 0.000 |
| `TWIN`, two plausible notes (4) | MRR 1.000, first 4/4 | MRR 1.000, first 4/4 | MRR 0.000 |
| `STALE`, a superseded version (4) | MRR 0.750, first 2/4 | **MRR 1.000, first 4/4** | MRR 0.000 |
| `CLAUSE`, answer buried (4) | MRR 1.000, first 4/4 | MRR 1.000, first 4/4 | MRR 0.000 |
| `ABSENT`, no answer exists (4) | returned nothing 0/4 | returned nothing 0/4 | returned nothing 0/4 |
| **aggregate over the 22 answerable** | **0.902** | **1.000** | **0.000** |

**The judge is not worse anywhere, and it is better in exactly two places.** It wins the
`TRAP` category it was designed for and it wins `STALE`, which nobody designed it for: asked which
floor the team is on, the cosine cannot tell "sat on the fourth floor until the lease ran out" from
"since the move the team sits on the ninth floor", and put the dead version first on two of the
four. On the three categories where the geometry was already right it tied at a ceiling rather
than overthinking its way off one, which was the specific risk `LEXICAL` was written to catch. It
also still returns **fewer** hits than `k`, on every answerable question here (22 of 22, one note
each), and every one of those omissions was correct, since the gold note was always the one kept.

**The control fired, in both directions, which is what makes the rest of the table admissible.**
The reversed arm ranks the same pool worst first and scores 0.000 in every category: a scorer that
cannot fail has been watched failing. And the cosine's own behaviour splits the way the corpus
predicted rather than being uniformly good or bad, failing on `TRAP` and `STALE` and holding 1.000
on `LEXICAL`, `TWIN` and `CLAUSE`. A measurement whose control does not fire has measured nothing.
Note that the cosine scores **worse on the original six here (0.806) than in the run above
(0.917)**, which is the pool widening rather than a contradiction: the same six questions now draw
their 12 candidates from 41 notes instead of 10, so there are more distractors available to
outrank the gold.

**The fallback rate is not zero, and the reason is the finding.** Four of 26 recalls fell back, all
four of them `ABSENT` questions. This was checked rather than assumed, exactly because a
schema-constrained reply cut by a token cap also lands in the fallback: each fallback was
re-sampled and the raw reply read, and all four came back `{"order": []}`, which is valid,
complete, well-formed JSON. **The model got these right.** It was asked which notes help answer a
question nothing in the corpus answers, and it correctly answered "none of them".

`JudgeRecallPolicy` then throws that away. `select` treats an empty parse as a failure and hands
the query to its fallback, so the caller receives the cosine's top three irrelevant notes with the
fallback's basis on the ranking. The one behaviour the judge has that no geometric policy can
imitate, declining to answer, is the one behaviour the policy cannot express, and it is
indistinguishable at the port from an unreachable model. That is a real defect and it is recorded
as a deferral rather than fixed here (`docs/refinements/index.md#memory`): the fix is a third `RankBasis`
separating a considered abstention from a failure to rank, and it changes what a recall may return
to a turn, which is a wider blast radius than a measurement's closing commit should carry.

Cost, from llama-server's own counters over the same run: **0.75 s per recall** across all 26
(including the four that spent a model call to abstain and then paid for the cosine anyway), 12 to
20 decoded tokens each, on prompts of 257 to 312 tokens now that the pool is 12 candidates rather
than 10. The wider pool costs prompt-eval time and no more decoding, which is what the bounds
predict.

**The recommendation stands, with better evidence and one narrowed claim.** `CORTEX_MEMORY_RECALL`
**still stays `raw` in this change**, because the standing decision is the user's own. (It moved to
`judge` on 2026-08-08; the turn-cost addendum below is what the user asked for first.) What the
wider corpus changes is that the recommendation no longer rests on a corpus built to produce it:
the judge ties the cosine wherever the cosine is right and beats it wherever the cosine is wrong,
on a corpus with four categories the judge could have lost. The two things a default still has to
answer for are unchanged in kind and one is now sharper. A rank still runs on every turn that
recalls, so 0.75 s lands on time to first token every time rather than being amortized. And a
deployment that turns the judge on should know that **on a question its memory cannot answer, the
judge's correct refusal is currently converted into the cosine's three wrong notes**, which is no
worse than what `raw` does on the same question and is not the improvement the refusal was.

## Abstention addendum (2026-08-07)

The widened corpus above found one defect and recorded it rather than fixing it: the judge answers
`{"order": []}` on a question nothing in memory answers, `JudgeRecallPolicy.select` reads that empty
parse as a failure, and the turn receives the cosine's three irrelevant notes under the fallback's
basis. This addendum is the fix. The judge may now decline, the refusal is a distinct outcome at
every consumer of a recall, and the trail can tell it from an unreachable model.

**Re-derived from the code before designing, and the backlog entry was right about the defect and
wrong about its price.** `parse_order` did return `()` for both an unusable reply and a complete
`{"order": []}`, and `select` did branch on `if not order` alone, so the defect was exactly as
recorded. The entry then priced the fix as changing "what a recall may hand a turn, so the recaller,
the audit trail and the prompt assembly each need to mean something by zero hits". Two of those
three already did, which the entry had not checked:

- `MemoryRecaller.recall` returns `ranking.memories`, so an empty ranking already left it as an
  empty sequence, and it neither re-fetched nor substituted the pool. No change was needed beyond
  saying so on the method.
- `_recalled_context` (`turn_context.py`) already returned `None` on no hits, so the turn was
  already assembled without a memory block. Also unchanged beyond its docstring.
- `Ranking` was already constructible with no hits, and its own docstring already said an empty
  ranking carries a basis worth knowing.

So the whole of the code change is the third `RankBasis`, the three-outcome parse, and the one
branch in `select` that tells them apart. The blast radius the entry feared is real in the sense
that a recall may now legitimately return nothing where the judge is on, and it was already
survivable everywhere it lands.

**The basis is `DEMUR`, and the register is deliberate.** `VERDICT` won its name in decision 4 for
being the only candidate whose word says a decision was made by something that can be wrong; its
sibling here has to say the same about a decision to keep nothing. A demurrer is the finding that
the material offered makes no case even if every word of it is granted, which is precisely what the
model is asked and precisely what it answered. Alternates: `NONSUIT` is the more exact legal term
for the same finding and was rejected as a word a reader has to look up; `SILENCE` reads as a
sibling to `ECHO`'s sensory register but says nothing about who decided, so it would fit an empty
store as well as a refusal, which is the confusion this member exists to end; `ABSTAIN` names a
voter declining to decide, and the whole point is that the judge decided.

**The parse now has three outcomes rather than two.** `parse_order` returns `None` for a reply
nothing can be read out of, the empty tuple for an `order` that arrived empty, and the picks
otherwise. A list that named notes and had none of them survive the range check returns `None`,
not the empty tuple: a model that tried to pick and produced nothing pickable has failed, while a
model that named none has answered. The truncation case stays on the failure side by construction,
since a reply cut by the token cap is not JSON at all while a refusal is complete JSON, so the
generous cap argued in the bounded-side-calls addendum keeps its whole argument. (That addendum's
wording, "`parse_order` returns empty", now reads "returns `None`"; the behaviour it describes is
unchanged.)

**What zero hits means, stated once per consumer.**

| Consumer | An empty ranking on `DEMUR` | An empty ranking on any other basis |
| --- | --- | --- |
| `JudgeRecallPolicy.select` | returns it; the fallback is not consulted | the fallback's own empty answer over an empty pool, which never reaches the model |
| `MemoryRecaller.recall` | returns no hits, without re-fetching or substituting | the same, and it means the pool was empty |
| turn assembly | no memory block at all, exactly what a memory-less turn sends | the same |
| `LoggingRecallSink` | `"basis": "demur"` with `"hits": []` | the basis that ranked, with `"hits": []` |

The trail is where the difference had to be legible, and it is carried by the basis rather than by
a new flag: `demur` with no hits is a model that read a pool and declined it, another basis with no
hits is a pool that held nothing to rank, and a fallback after an unreachable or unbelievable model
shows the fallback's own basis with the hits it chose. Three events, three readings, from fields the
line already carried.

**One invariant is enforced rather than described.** `Ranking.__post_init__` refuses a `DEMUR`
ranking that carries hits, because a policy cannot both decline and return something and no consumer
could act on one that claimed to. The converse stays legal: a heuristic policy handed an empty pool
returns an empty ranking on its own basis and means only that there was nothing to rank.

**Turn assembly says nothing rather than saying nothing was found.** The alternative considered was
a system message reporting that memory had nothing to offer. It was rejected: that is a claim about
the store's contents that the assembly does not know (the judge declined a pool of candidates, which
is not the same as memory being empty), and putting it in the prompt invites the model to answer for
it. A turn whose memory declines sends what a memory-less turn sends.

**What does not change.** The fallback stays, and it stays on the failure path it was built for: an
unreachable model, a reply outside the envelope, a truncated one, an order of nothing that exists,
or an empty candidate pool (where the model is never consulted, so a refusal is not available to
report). `CORTEX_MEMORY_RECALL` still defaults to `raw` **as of this addendum**, so nothing changes
for a deployment that has not opted into the judge, and the recommendation to move it stands where
the widened corpus left it, with the caveat it carried about refusals now answered. (The default
moved to `judge` on 2026-08-08, in the turn-cost addendum below, once the recommendation's own
caveat about whole turns had a number.)

### Measured (2026-08-07)

The same widened corpus, rerun against the real cortex (gemma-4-12B on the 24 GB card, via the gpu
compose stack plus the memory override's CPU embedder) on the fixed policy. Reproduce:
`packages/inference/tests/test_rerank_judge_wide_live.py`, integration-marked, which now separates a
refusal from a fallback in its own tally rather than counting both as "fell back".

| | before (widened-corpus run) | after |
| --- | --- | --- |
| `ABSENT` questions returning nothing | 0 of 4 (the cosine's notes, via the fallback) | **4 of 4** |
| Fell back over the whole corpus | 4 of 26 | **0 of 26** |
| Aggregate MRR over the 22 answerable | 1.000 (cosine 0.902) | 1.000 (cosine 0.902) |
| Reversed-cosine control | 0.000 | 0.000 |
| Cost per recall | 0.75 s | 0.76 s |

The four `ABSENT` questions now print as `judge [] (declined)` where they printed the cosine's three
irrelevant notes, and the fallback column is empty for the first time: every recall in the run was
either ranked or refused by the model itself. The ranking on the 22 answerable questions is
unchanged, which is the result that matters, since a policy allowed to return nothing could have
started returning nothing where it should not.

Two honest notes on the rerun. The refusal costs the same as a rank (0.76 s against 0.75 s) because
the pool prompt is evaluated either way, so declining is not a saving, it is a correct answer. And
the "fewer hits than `k`" observation is sampled rather than fixed: this run kept one note on 21 of
the 22 answerable questions and three on one `STALE` question, where the earlier run kept one on all
22. The gold note was still first every time, so the variation is in what it adds after the answer,
not in the answer.

### Deferred by this addendum

Recorded in [memory](../refinements/index.md#memory) with its line on
[the index](../refinements/index.md):

- **A geometric policy still cannot decline.** The refusal is the judge's alone. `RawRecallPolicy`
  (the shipped default) and the three heuristic policies always return their nearest `k`, so a
  deployment that has not opted into `CORTEX_MEMORY_RECALL=judge` still receives three nearest
  misses on a question memory cannot answer: the same turn this addendum fixes, from a different
  cause. The geometric analogue is a relevance floor, which the widened `select` return can already
  express and no policy computes; it was declined here because a cosine threshold belongs to the
  `Embedder` it was calibrated against and means something else behind another one, and because a
  floor on `RawRecallPolicy` would break the one promise that policy makes, which is that recall is
  byte-for-byte what v1 returned. It therefore wants a fifth policy rather than a knob on the
  default. **Trigger:** a deployment that wants recall to stay geometric and still be able to say
  nothing, or a calibration run that gives the floor a defensible number.
  **Closed 2026-08-08 as declined on measurement** (the relevance-floor addendum at the foot of this
  ADR). The calibration ran and found no defensible number to give: over this corpus the answerable
  and unanswerable populations overlap behind both embedding models the repo ships a path for, so
  every floor that silences the unanswerable questions also silences answerable ones, worst of all
  in the vocabulary-trap category the rank was bought for. The consumer was larger than this bullet
  says, which is why it was worth measuring rather than shrugging at: the default deployment's
  fallback is `RAW_RECALL_POLICY`, so the cosine ranks whenever the model cannot be reached.

## Turn-cost addendum (2026-08-08): the default moves to `judge`, measured on whole turns

Every earlier section priced the rank in isolation and left the default alone, and both of the
recommendation's own caveats were about that gap: a rank runs on **every** recalling turn, and
0.75 s of rank was never the same claim as 0.75 s of user-visible latency. The user's call was to
measure the turn before flipping. This is that measurement, and the flip it licensed.

### What was measured, and how

Real turns through the shipped seam, not a policy in a harness. The gpu stack plus the memory
override was brought up on the 24 GB card with the resident cortex (gemma-4-12B), and a host-side
gRPC client opened one `Converse` stream per turn against the brain's `BrainService`, timing from
the moment it wrote the `UserTurn` to the **first `TextDelta`** (time to first token, the part a
user feels) and to `TurnComplete`. Each turn ran in its own fresh session under
`CORTEX_MEMORY_SCOPE=session`, whose scope had been pre-seeded with all 41 notes of
`recall_corpus.py`, so every turn ranked an identical corpus, no turn's own recorded exchange
reached the next turn's pool, and the real global memory space was neither read nor written.
Six questions, one per corpus category, eight repetitions, 48 turns an arm.
`CORTEX_MEMORY_RECALL_AUDIT=1` was on throughout, so which policy actually ranked each recall is a
fact of the run rather than an assumption about it.

**Three blocks in A/B/A order**, `raw` then `judge` then `raw`, each block a container restart with
one environment variable changed. The two raw blocks are the control: they differ from each other
only in when they ran, so whatever they show is the run-to-run noise floor that the judge block has
to clear. Arms are compared question by question rather than pooled, because a question's answer
length dominates its turn time and the questions are the same in every block.

### The numbers

| | raw (block A) | judge (block B) | raw (block C) |
| --- | --- | --- | --- |
| Time to first token, mean | 4.296 s | 4.732 s | 4.138 s |
| Time to first token, median | 4.193 s | 4.502 s | 4.024 s |
| Time to first token, sd | 1.467 s | 1.519 s | 1.648 s |
| Whole turn, mean | 4.906 s | 5.357 s | 4.756 s |
| Whole turn, sd | 1.514 s | 1.619 s | 1.711 s |
| Turn start through the pgvector search | not captured | 0.363 s | 0.396 s |
| Notes handed to the reply, mean | 5.00 | 1.17 | 5.00 |
| Rank bases seen | `echo` | `verdict`, `demur` | `echo` |

Blocked by question and bootstrapped over 20,000 resamples:

- **judge against raw: time to first token +0.515 s** (95% CI +0.116 to +0.915), whole turn
  **+0.526 s** (95% CI +0.131 to +0.921).
- **The null arm, raw against raw: -0.158 s** (95% CI -0.669 to +0.377), an interval spanning zero.

So the harness separates two arms that should differ and does not separate two that should not,
which is the only thing that makes the first number readable.

**The rank alone costs more than the turn does.** Timed on its own through the same
`JudgeRecallPolicy.select`, at the shape turn assembly actually asks for (`DEFAULT_RECALL_K` 5 at
`recall_pool_factor` 4, so a pool of 20 of the 41 notes), a rank is **0.877 s** (median 0.859,
0.704 to 1.160, sd 0.120, n=30). That is above the 0.75 s this ADR published, and the reason is
recorded rather than surprising: the published figure was measured at `k` 3 over a pool of 12, and
a wider pool costs prompt-eval time. Yet the turn only pays 0.515 s of it. **The judge gives about
a third of its own cost back** by handing the reply 1.17 notes where the cosine hands it 5, so the
memory block the model must read before it can speak is smaller. The saving is real and it is not
free of risk: it is proportional to how much the cosine over-returns, so a deployment whose recalls
are mostly answerable will see less of it than this corpus shows.

**Where in the turn it lands: before generation, on the first token.** Recall runs inside
`assemble_inference_messages`, which `handle_turn` awaits to completion before `stream_tool_loop`
opens the reply. The trail's own timestamps say the same thing from the other side: everything up
to and including the pgvector search takes 0.363 s under `judge` and 0.396 s under `raw`, which are
the same number, and the whole difference sits after it. A recalling turn's first word is half a
second later than it was.

**It is paid every turn, and nothing caches it.** `JudgeRecallPolicy.select` holds no state and no
cache, `MemoryRecaller.recall` calls it on every recall, and `_recalled_context` recalls on every
turn where memory is on: the run logged exactly 48 recall lines for 48 turns in each arm. This is
the asymmetry with `SummarizingHistoryWindow` that the recommendation kept naming, and it is
confirmed rather than softened. What changed is only its size.

### The ranking, re-checked at the width a turn uses

The corpus runs behind this decision scored `k` 3 over a pool of 12. Read off this run's audit
trail at `k` 5 over a pool of 20, over the 40 answerable turns an arm:

| | raw | judge |
| --- | --- | --- |
| Mean reciprocal rank | 0.767 | **1.000** |
| Unanswerable questions returning nothing | 0 of 8 | **8 of 8** |
| Recalls that fell back to another policy | n/a | **0 of 48** |

Every judged recall in the run was ranked or refused by the model itself. The wider pool did not
cost the judge anything and it cost the cosine something, the extra candidates being extra ways for
a distractor to outrank the answer.

### Decision

`CORTEX_MEMORY_RECALL` **now defaults to `judge`**. The premise the old default rested on was cost,
the cost is 0.515 s of time to first token on a recalling turn, and it buys a rank that was worse
nowhere and better on two of six categories over a corpus built to refute it, plus a refusal on
questions memory cannot answer that no geometric policy can express. `CORTEX_MEMORY_RECALL=raw` is
the one variable that puts the founding behavior back, and it is now the opt-out rather than the
default.

**What this does not settle**, and what no run by this repo's own author can: the corpus is still
hand built by an interested party. What the flip changes about that is who is exposed to it. The
judge is now what a real conversation meets, so the standing objection is answered by use rather
than by another staged corpus, and the audit trail is how a disagreement gets diagnosed after the
fact. The remaining entries in [docs/refinements/index.md#memory](../refinements/index.md#memory) say what is
still open, and one of them changed shape here: the relevance floor was filed as the gap left for
"every deployment that has not opted into the judge", and it is now the gap left for a deployment
that opts **out** of it.

### Deferred by this addendum

Recorded in [repo-gates](../refinements/index.md#repo-gates) with its line on
[the index](../refinements/index.md):

- **This measurement's harness is not in the repo.** Every other run in this ADR names an
  `integration`-marked test that reproduces it; the numbers above name none. The host-side client
  that opened one `Converse` stream per turn, timed the first `TextDelta` and the `TurnComplete`,
  and ran the three blocks with a container restart between them was left in a scratchpad, so the
  0.515 s is re-derivable only by rebuilding the driver from the prose here. It was punted because
  a driver spanning the seam is not an adapter test and wanted its own decision about where such a
  thing lives, and it is filed under the repo's test-runner mechanics rather than under memory
  because that placement, not recall, is what stayed unsettled. The tree answers most of it
  already: `packages/orchestrator/tests/test_schedule_live_seam.py` is an `integration`-marked
  host-side client of the shipped `BrainServiceStub`. What it does not answer is a harness that
  restarts containers between arms and reports a distribution rather than asserting a bound.
  **Trigger:** the next end-to-end measurement of a whole turn, or a challenge to the shipped
  recall default that needs this run reproduced rather than cited.
  **Closed 2026-08-09 as landed** (the harness addendum at the foot of this ADR), on the second
  half of that trigger. The answer to both questions it left is one division of labour: an arm is a
  container configuration, so the restarts live in a `just turn-cost` recipe, which puts the arms in
  separate processes, so each block writes a JSON sample and `scripts/contrast.py` reports the
  blocked paired bootstrap over the samples afterwards. Time to first token reproduces at 0.539 s
  against the 0.515 s above; the whole turn does not, and the samples name the one question it
  sits in.

## Relevance-floor addendum (2026-08-08): declined on measurement, and the number does not exist

The abstention addendum taught `JudgeRecallPolicy` to say that nothing in the pool helps and left
behind the gap that the refusal is the judge's alone. `RawRecallPolicy` and the three heuristic
policies always return their nearest `k`, so a recall that runs on geometry hands a turn its nearest
misses on a question memory cannot answer. The geometric analogue that entry named is a **relevance
floor**: drop a candidate whose similarity is below some threshold, and return nothing when none
clears it, which the `Ranking` this ADR introduced can already express. Its trigger was "a
calibration run that gives the floor a defensible number". The run was done, on the real embedder
over the real corpus, and the answer is that no such number exists. **The floor is declined.**

### Who the consumer actually is, re-derived first

The entry was written while `raw` shipped, and the turn-cost addendum above inverted its premise
without closing it, so the consumer was re-derived from the tree before anything was designed. It is
larger than "a deployment that opts out", and the reason is the fallback:
`recall_policy_from_config` (`memory_builders.py`) builds `JudgeRecallPolicy(backend, cortex_model,
pool_factor=...)` and passes no `fallback`, so the shipped default carries `RAW_RECALL_POLICY`, and
`select` hands the pool to it on an `InferenceError`, on a reply outside the envelope, and on an
order that parses to nothing usable. The cosine therefore ranks inside the **default** deployment
every time the model cannot be reached or believed, which is precisely the moment nothing else is
watching the recall. A floor would have been a default-path guard rather than an opt-out nicety, so
the entry was worth answering with a measurement rather than with a shrug.

### The shape it would have taken, decided before the measurement could bias it

The entry proposed a **fifth policy**. That is the wrong shape, and the argument is worth keeping
for whoever reopens this:

- **A fifth name cannot reach the consumer above.** `CORTEX_MEMORY_RECALL` selects one policy. A
  `floor` member would be a policy a deployment runs *instead of* the judge, which leaves the
  judge's own fallback, the default path, exactly as unfloored as it is today. The floor has to be
  something the fallback can wear.
- **A floor is orthogonal to how you rank**, so a name per combination multiplies the matrix: five
  policies become ten the moment a deployment wants a floor under `mmr`. The shape that composes is
  a decorator holding an inner `RecallPolicy`, the shape `JudgeRecallPolicy` already uses for its
  fallback, plus one knob (`CORTEX_MEMORY_RECALL_FLOOR`, default `0.0`).
- **The founding-behavior objection is answered by the default, not by a separate name.** The entry
  refused to floor `RawRecallPolicy` because that policy's promise is byte-for-byte v1 recall. With
  the knob defaulting to `0.0` the composition root wraps nothing, so `raw` is unchanged unless a
  deployment asks for a floor, which is the same protection a fifth name buys and costs no name.
- **It would threshold `hit.score`, never `RankedMemory.key`.** The store's cosine is the one
  quantity every hit carries with a stable meaning; `SPREAD` and `SWEEP` keys are measured against
  the kept set at pick time, which is what `RankBasis.comparable` exists to say, so a floor over
  them would compare numbers that do not compare.
- **It would pre-filter the pool rather than post-filter the result**, so the inner policy still
  fills its `k` from whatever qualifies and a hit that clears the floor is never displaced by one
  that does not. An empty pool then reaches the inner policy, which already returns an empty ranking
  on its own basis, so no new `RankBasis` member is needed and none is wanted: the basis says which
  policy ranked, and a floor does not rank. The trail already tells the two empties apart, since a
  geometric basis with zero hits and a `pool_size` above zero can only be the floor.
- **It would not wrap the judge itself.** The model can already decline, and the corpus's vocabulary
  trap is the case where the answering note's cosine is *low*, so flooring the pool the model reads
  would hide exactly the note the rank was bought to find. The floor belongs on the geometric side:
  the selected policy when it is geometric, and the judge's fallback when it is not.

None of that survives the measurement, and it is recorded because the measurement is about whether a
floor can work at all, not about which of these shapes it would have taken.

### Measured (2026-08-08)

Reproduce: `packages/inference/tests/test_recall_floor_live.py`, integration-marked, which needs
only the memory override's CPU embedder because a floor reads similarity and never the model. It
sweeps the floor operator over the 41-note corpus in `recall_corpus.py` at the shipped pool width
(`k` 3, `pool_factor` 4) and prints three populations plus what every candidate threshold does.

The corpus's 26 questions give two of them: 22 answerable, and 4 `ABSENT` ones that are unanswerable
but adjacent, each sitting beside notes the corpus does hold. The run adds a third, `UNRELATED`, 8
questions about subjects no note mentions at all, which is the easiest case a floor could ever be
asked to catch. Behind the shipped embedder (nomic-embed-text-v1.5 Q8_0):

| population | cosine band |
| --- | --- |
| answerable, the gold note's own score | 0.4742 to 0.9063 (mean 0.6947) |
| answerable, the best score in the pool | 0.4919 to 0.9063 |
| unanswerable and adjacent | 0.5112 to 0.6325 |
| unanswerable and unrelated | 0.4057 to 0.4994 |

**The populations do not separate, and the headroom is negative.** The lowest answerable gold sits
**0.1582 below** the highest adjacent-unanswerable best hit, so no threshold has both above it and
below it. Against the unrelated population the gap is still negative, at 0.0252: a question about
the atomic weight of tungsten scores 0.4994 against these notes while the trap question "where are
we keeping things while a conversation is in progress?" tops out at 0.4919.

What that costs, swept (MRR over the 22 answerable, `raw` selection from the same pool):

| floor | adjacent silenced | unrelated silenced | MRR | answerable silenced | hits handed to turns |
| --- | --- | --- | --- | --- | --- |
| 0.0 (off) | 0 of 4 | 0 of 8 | 0.902 | 0 of 22 | 102 |
| 0.45 | 0 of 4 | 6 of 8 | 0.902 | 0 of 22 | 79 |
| 0.50 | 0 of 4 | 8 of 8 | 0.886 | 1 of 22 | 60 |
| 0.55 | 1 of 4 | 8 of 8 | 0.864 | 1 of 22 | 41 |
| **0.6325** (the tightest that silences all four) | 4 of 4 | 8 of 8 | **0.659** | **6 of 22** | 22 |
| 0.65 | 4 of 4 | 8 of 8 | 0.591 | 8 of 22 | 18 |
| 1.01 | 4 of 4 | 8 of 8 | 0.000 | 22 of 22 | 0 |

The bolded row is derived from the data rather than picked off the grid: it is the lowest floor
above every adjacent-unanswerable question's best hit, so it is the **cheapest** price of the promise
"a question memory cannot answer returns nothing". That price is **6 of 22 answerable questions
returning nothing at all** and an MRR of 0.902 down to 0.659, and it falls where it can least be
afforded: the `TRAP` category, the vocabulary trap the model rank was bought for, drops from 0.81 to
**0.17**, because a note that answers in words the question never uses is exactly a note with a low
cosine. A floor calibrated to make geometry decline deletes the case geometry was already worst at.

**The number is also not portable, which the entry asserted and this run measures.** The same sweep
behind nomic-embed-text-v2-moe Q8_0, the alternative `CORTEX_EMBED_MODEL_FILE` pick, moves every
band: answerable golds 0.2552 to 0.8176, adjacent unanswerable 0.2939 to 0.4485, unrelated 0.1650 to
0.2484. Separation is **0.1933 negative**, so the conclusion holds, but the tightest floor that
silences all four adjacent questions moves from 0.6325 to 0.4485 (costing 7 of 22 answerable
questions there, MRR 0.841 down to 0.591, `TRAP` to 0.00), and the band an off-topic question lands
in moves from between 0.41 and 0.50 down to between 0.17 and 0.25. A number calibrated behind one
embedder is a different decision behind the other.

**The instrument was proved able to fail before its result was believed**, since a floor that never
fires and a floor that works are indistinguishable on a corpus of answerable questions. Three
mutations, each reddening the assertion that covers it: an operator that drops a hit breaks the
floor-of-zero identity (68 hits handed out where an unfloored run hands 102); an operator that
ignores its floor breaks the absurd end (a floor of 1.01 returned three hits instead of none); and
running the finding assertion over a corpus restricted to `LEXICAL` plus `ABSENT`, whose populations
genuinely do separate, fails it with a separation of **+0.2104**. That last one is the reopening
condition, wired as a test rather than as a note: point the run at an embedder whose populations
separate and it goes red.

### Decision: declined, and declining stays a property of reading

There is no defensible number, so there is no floor. A threshold high enough to make geometry
decline destroys the recall it was supposed to protect, and a threshold low enough to be safe
declines nothing that matters. The two ranges are worth stating exactly, because a floor is only
shippable where they overlap. A floor costs this corpus nothing while it stays at or below the
lowest answerable gold, which is **0.4742** behind the shipped embedder, and pre-filtering only ever
promotes a surviving gold, so nothing below that ceiling can move the MRR. The lowest floor that
catches even the *easiest* population, the questions about subjects no note mentions, is **0.4995**.
Behind the shipped embedder the safe range and the useful range therefore do not overlap at all:
they cross by 0.0253. Behind the alternative embedder they do overlap, by **0.0068**, between the
highest unrelated question at 0.2484 and the lowest answerable gold at 0.2552. A knob whose entire
safe and useful range is seven thousandths wide behind one embedding model and empty behind the
other, read off the sample minimum of 22 hand-built questions rather than off a bound, and narrowing
on a real store where more notes mean a closer nearest neighbour for every question, is the magic
constant this repo refuses, with the added defect that a deployment could never tell which side of
it they were on.

What the run establishes positively is worth stating, because it is the reason the shipped default
is what it is: **an abstention is a property of reading, not of ranking.** The judge returns nothing
on these questions because it reads the candidates and answers about them; the cosine cannot,
because the geometry of a question memory cannot answer looks exactly like the geometry of a
question whose answer is worded unlike it. The capability exists in the shipped stack and
`CORTEX_MEMORY_RECALL=raw` is an opt-out of exactly that capability, which the runbook now says in
those terms.

**Reopens** behind an embedder whose populations separate, which the test above measures and
asserts, or on a signal that is not an absolute cosine. The one already-filed candidate is the
**cross-encoder rank**, which reads the pair rather than measuring the distance and so is the same
kind of thing as the judge rather than the same kind as a floor; it stays deferred on its own
trigger in [memory](../refinements/index.md#memory).

### Deferred by this addendum

Nothing. The decline opens no new item: the calibration harness ships as the test named above rather
than staying in a scratchpad, and the reopening condition is an assertion inside it.

## Fold-under-load addendum (2026-08-08): the sequencing argument, measured against overlapping streams

`CORTEX_HISTORY_SUMMARY` ships **on**, so every long conversation now spends a model pass inside
turn assembly, and the reason that was ever safe to do on the turn's critical path was an
**argument about ordering** rather than a measurement. The argument is worth stating exactly,
because it is what was tested:

The GPU lease is one non-reentrant `asyncio.Lock` per `ModelManager` (`model.py`), and the
composition root builds one `LlamaCppBackend` over one manager for the whole process, so every
`Converse` stream contends for that one lock. The adapter takes the lease **inside its stream
generator** (`backend.py`), on the generator's first `__anext__`, and holds it until that
generator leaves the `async with` block. A fold takes it through `drain_text`, which leaves the
block in a `finally`; `SummarizingHistoryWindow.select` awaits the fold to completion;
`assemble_inference_messages` awaits `select`; and `handle_turn` awaits the whole assembly several
statements before it first iterates the reply's generator. So within one turn the fold's lease and
the reply's lease are two acquisitions **in sequence**, never one nested inside the other.

Concurrency is what tests that, and nothing had ever run more than one stream. The measurement is
`packages/orchestrator/tests/test_fold_under_load_live.py` (integration-marked, five arms), which
drives the shipped `converse` use case over the real adapter, the real Redis store and the real
resident cortex, with each model call's lease timestamped at request, grant and release.

### Designed to falsify, and what proves the run is not empty

Concurrent streams that never actually overlap would pass every assertion in this file while
measuring nothing, which is the null result this backlog has recorded twice. So the run does not
assert "the turns ran together": it collects every moment one stream **asked** for the lease
strictly inside a different stream's **hold**, and fails when it finds none. Two arms then break
the system deliberately and show the same helpers catching the break, because a concurrency test
that passes on a broken system is worthless.

### Measured (2026-08-08, 24 GB card, gemma-4-12B at 16K, three overlapping streams)

A solo turn over the same corpus first, so the concurrent numbers have something to read against:
time to first token **4.6 s**, whole turn **4.9 s**, the fold holding the lease **2.4 s**.

Three streams then start together, each on its own session with its own planted booking reference,
each with enough dropped history to force a fold. Seconds are from the first acquisition request:

| acquisition | asked | granted | released | waited | behind |
|---|---|---|---|---|---|
| s0 fold | 0.00 | 0.00 | 2.81 | 0.00 | nothing |
| s2 fold | 0.00 | 2.81 | 5.61 | 2.81 | s0 fold |
| s1 fold | 0.00 | 5.61 | 8.23 | 5.61 | s0 fold, s2 fold |
| s0 reply | 2.82 | 8.23 | 10.44 | 5.41 | s2 fold, s1 fold |
| s2 reply | 5.61 | 10.44 | 12.27 | 4.83 | s1 fold, s0 reply |
| s1 reply | 8.24 | 12.27 | 17.75 | 4.03 | s0 reply, s2 reply |

All three folds were requested at the same instant, which is the overlap the run refuses to
proceed without: five acquisitions were issued while another stream held the lease.

**The argument held on every point it claims.** No hold ever overlapped another, so the lock is
exclusive and the timeline really is measuring it; within every stream the fold's hold ended
before that stream's reply's hold began; and no acquisition was left ungranted or unreleased.

**What load costs is queueing, and a fold is now among the things a reply queues behind.** Time to
first token went from 4.6 s solo to 10.3 s, 12.0 s and 17.5 s, and the row that matters is `s0
reply`: it asked at 2.82 s, the instant its own fold released, and waited **5.41 s behind two
OTHER streams' folds**. The argument never denied this and it is the load consequence the
default-on knob now carries: with N streams folding at once, every stream's reply waits out up to
N-1 folds that are not its own, on top of the replies ahead of it.

**No turn's context was wrong.** Each stream answered with its own reference and with nobody
else's, over four independent runs of this arm (twelve of twelve), and each session's recap
named only its own. One window instance served all three streams deliberately, since the sink is
handed per call precisely so a shared window stays correct, and each fold's `folding` chip landed
on exactly its own stream (one chip per stream, every run).

**A swap landing mid-fold is the one hypothesis answered from the code rather than measured**, and
it is worth saying which. This stack runs with escalation off, so the manager is
`SingleResidentModelManager` and there is no swap to land. With escalation on the lease belongs to
`SwappingModelManager`, which takes the very same lock and whose swap **waits for the lease to fall
free** rather than preempting, so a fold in flight is a mid-stream round like any other and a fold
that starts as a residency scope opens queues for the scope to end instead of failing. That is a
reading of `residency.py`, not a run, and it is labelled as one.

**Two turns of one session concurrently** is the other shape, and it needs two streams naming one
session because one stream runs its turns one at a time. Both turns appended, both read a history
the other was still growing, both folded, and both wrote a recap under one key: both answered with
the session's own reference, the history ended at the expected 26 messages, and the surviving
recap covered a prefix that really exists (14 of 26). Append-only history is what makes that safe;
a recap of a prefix can go stale and never wrong, so the loser of the write race costs a repeated
fold and never a wrong answer.

### The one thing the run found that was not written down anywhere

**A consumer that stops reading holds the GPU, and now a stranger's fold waits on it.** The
reply's lease is held for the generator's whole lifetime, and the seam's credit bound
(`CORTEX_SEAM_CONVERSE_BUFFER`) suspends generation **inside** that lease when the consumer stops
dequeuing. That is the shipped backpressure behaving exactly as designed, and it predates the
fold. What is new is who pays: measured at a one-credit bound with the reader stalling 12 s, the
stalled stream's reply held the lease **16.52 s** against the 2.2 s to 3.6 s an unstalled reply
holds it, and the next stream's **fold waited 16.51 s** behind it. The trade is real in both
directions (the bound exists to cap a stalled stream's memory, and letting generation run ahead of
the consumer to release the lease sooner is what it refuses to do), so it is recorded as a
deferral rather than changed here.

### Distrust green: both halves proven able to fail

* **A fold that holds the lease across the reply.** A window that opens a model call and never
  closes it, which is precisely what `drain_text` exists to prevent, deadlocked the turn: it did
  not complete inside 30 s, and the same checker that returns an empty list above returned
  `['leak/fold took the lease and never released it', 'leak/reply waited for the lease and never
  got it']`. The arm asserts the NAMES and not merely the timeout, because a test that only
  notices a hang cannot tell a deadlock from a slow model.
* **Streams that do not overlap.** The same two streams run one after the other produced four
  acquisitions and **zero** contentions, so the overlap proof the main arm depends on is
  something that can genuinely come back empty.

### Decision

Nothing changes in the shipped code. The argument that `CORTEX_HISTORY_SUMMARY=true` is safe to
run on the turn's critical path is now a measurement rather than a reading of the call graph, and
what it costs under load is a number: a fold serializes with every other stream's work, and a
reply waits out the folds ahead of it.

### Deferred by this addendum

One, in [session-history](../refinements/index.md#session-history): a stalled consumer holding the
GPU lease across the whole of its reply, with the numbers above.

## Dropped-candidate addendum (2026-08-09): the trail names what the rank left behind

The Deferred section above filed the audit of dropped candidates with a stated obstacle: a
non-picked candidate's `SPREAD`/`SWEEP` key is not well defined, because an MMR objective depends
on the kept set at each step and an unpicked candidate never joined one. That is true and it is not
the whole question. The trigger it named, the first investigation that needs to know why a specific
memory was *not* returned, has grown teeth since: `CORTEX_MEMORY_RECALL` ships as `judge` from the
turn-cost addendum, and the judge is measured returning 1.17 notes where the cosine returned 5, so
the shipped rank drops most of the pool on most turns. The trail was thinnest exactly where the
most is now discarded.

### Re-derived from the tree first, and one claim of the entry needed narrowing

`LoggingRecallSink.record` (`cortex_memory/audit.py`) built its line from `session`,
`query_chars`, `pool`, `k`, `basis`, `keys_comparable`, a `hits` list drawn only from
`audit.ranking.hits`, and `at`. `pool` was a **count**: no candidate id left the recaller unless
the rank kept it. So a memory absent from a line was indistinguishable from a memory the store
never offered, which is the whole of the question an operator arrives with. Nothing text shaped was
in the record already, and nothing text shaped is added here: the existing line logs the query's
length rather than the query, exactly as the tool audit logs a result's size rather than its bytes.

The entry's obstacle survives contact with the code and answers itself. A rank key for a dropped
candidate does not exist for `SPREAD` and `SWEEP`, and it does not exist for `VERDICT` either,
since the judge simply leaves a note out of its order rather than scoring it low. Under `ECHO` and
`EMBER` one could be computed after the fact, which is not the same as having one: a `Ranking`
carries keys for the hits it kept and for nothing else, and only the policy holds the parameters to
work out another. What does exist, for every candidate and under every basis, is the **store's own
cosine**, because the store produced the pool. So the answer is to log the id and that cosine and
to omit the key that does not apply, rather than to invent one.

### Decision

1. **The core computes what was dropped; the sink emits it.** `ranking.py` gains
   `DroppedCandidate` (an `id` and the store's `score`), `DroppedCandidates` (the bounded
   `carried` tuple plus an `omitted` count), and the pure `dropped_candidates(pool, ranking, *,
   limit)`, which is the one answer to "what did this rank leave behind" so no second consumer
   derives it a second way. `RecallAudit` gains a required `dropped` field. `LoggingRecallSink`
   grows two keys, `dropped` and `dropped_omitted`, and decides nothing.
2. **Identity is the memory id, not the object**, so the difference is true of every basis,
   including an empty ranking, where the whole pool is what was dropped. A refusal is the recall
   whose trail most needs to say what was on offer.
3. **No text, structurally.** `DroppedCandidate` has no field that could carry any: an id pairs
   with the `memories` table when content is wanted, under whatever access reading the store
   already requires. This is not restraint on the sink's part, which is the difference from the
   kept hits, where the port hands over the whole `ScoredMemory` and the shipped sink declines to
   log its text.
4. **Bounded at twenty, and the number is sized from what ships.** A recall of `DEFAULT_RECALL_K`
   (5) at the default `CORTEX_MEMORY_RECALL_POOL_FACTOR` (4) is a pool of 20, so a shipped
   deployment never truncates its own trail and `dropped_omitted` reads 0 on every line. The bound
   bites only where a deployment over-fetches wider than what ships, and there an audit line that
   grew with the pool would make the trail the thing worth turning off, which is a defect of its
   own. What a bound cuts is the tail of the store's own order, `MemoryStore.search` promising
   most-similar first, so what survives is what the store rated highest. The count of what was cut
   rides the line rather than being left to arithmetic over `pool` and `hits`, so a truncated list
   is never read as the complete one.
5. **The trail says what was available, never why the rank declined.** A dropped candidate's score
   is the store's cosine and nothing beside it. Under `judge` this is the honest limit of the
   mechanism: the model is asked which notes help and answers with an order, so a note it left out
   carries no verdict at all, and reading its cosine as the reason would be reading geometry the
   rank did not use. The line tells an operator that a memory was a candidate and was passed over.
   Why it was passed over is a question for the rank, and the rank did not say.
6. **Still opt in, and off costs nothing.** `CORTEX_MEMORY_RECALL_AUDIT` is unchanged and still
   defaults to `False`, wiring no sink rather than a sink that drops. The whole `RecallAudit`,
   including the difference between the pool and the ranking, is assembled inside
   `MemoryRecaller.recall`'s `audit is not None` guard, so an unaudited recall walks the pool once
   for the policy and never again. That is pinned rather than asserted: an instrumented pool counts
   its own walks, and the test reads 1 unaudited against 2 audited.

### Consequences

- `RecallAudit` gained a required field, so every construction site says what the rank left
  behind. There is one in production and one in the trail's own tests.
- The `RecallAuditSink` port is unchanged in shape. A sink written against the old value would
  not compile against the new one, which is the intended direction: the port carries more, and no
  adapter is silently left emitting less.
- No cross-tree coupling arrives with this. The bound is one declaration in one tree, and its
  relation to the shipped pool width is a sizing argument rather than an equality any code depends
  on, so `crosscheck.py` has nothing new to hold and the trail stays correct at any bound.

### Distrust green

Seven mutations, each run against the three suites that cover this path, each reddening only what
it should:

| Mutation | Result |
| --- | --- |
| the dropped set keeps the hits the rank kept | 5 failed |
| the bound is removed | 1 failed |
| `omitted` is hard zeroed | 1 failed |
| a dropped candidate's score is not the store's cosine | 4 failed |
| the sink logs no dropped ids | 2 failed |
| the sink logs no omission count | 1 failed |
| the record is assembled whether or not a sink is wired | 1 failed |

The last row is the one the design point about paying nothing depends on, and it is the reason the
walk counting pool exists: no assertion about a value can catch work done for a reader who is not
there.

### Deferred by this addendum

Recorded in [memory](../refinements/index.md#memory) with its line on
[the index](../refinements/index.md):

- **The line can now say a memory was never a candidate, and still cannot say why.** Three causes
  are indistinguishable on it: the memory ranked below the pool cutoff, its scope was not read, or
  it was never written. Two of those are derivable by a reader holding the deployment's config,
  since the scopes follow from `CORTEX_MEMORY_SCOPE` and the `session` already on the line and the
  requested width is `k` times `CORTEX_MEMORY_RECALL_POOL_FACTOR`; logging them would be a
  convenience. The third cause is not derivable at all: `pool_size` is how many candidates came
  back and never how many there were, so a pool filled to the requested width cannot be told from a
  store that held exactly that many. That half is **not** behind the unchanged port, `MemoryStore.search`
  reporting no total, so it wants the port, both adapters, the fake, the contract test and a count
  beside the ranked select. **Trigger:** the first investigation whose memory is not in the pool at
  all, or a deployment that has widened its pool and wants to know whether it is wide enough.

## Harness addendum (2026-08-09): the turn-cost run enters the repo, and reproduces itself

The turn-cost addendum above moved the default on a number that no committed test could
re-derive. Its driver lived in a scratchpad, which made 0.515 s the one measurement in this ADR
resting on prose rather than on a run anyone can repeat, and it was the measurement whose result
shipped. The deferral it left was narrowed the same day by the fold-under-load run, which committed
a seam-spanning driver and thereby settled where such a thing lives, down to two questions: **how a
committed test expresses an arm that needs the brain container restarted with one environment
variable changed**, and **how it reports a distribution with a confidence interval rather than
asserting a bound**. The A/B/A control was the same question in different clothes. This addendum
answers all three and records the reproduction.

### The decision: a division of labour, not one clever test

**The restart lives in a recipe, `just turn-cost`, and never in the test.** An arm here is a brain
container configured one way; changing it is a deployment step, not an assertion. A pytest process
that recreated its own subject would be instrument and operator at once, would have to spell the
whole compose file set a second time inside a test file (a second copy of the deployment recipe,
free to drift from the first), and would take ownership of a stack it neither brought up nor could
restore after a failure. The recipe is committed and versioned exactly like the compose files it
invokes, so nothing about the protocol is left in prose.

**That decision forces the second answer rather than leaving it open**, which is why the entry was
right that the two questions were one. Restarting between arms puts the arms in separate processes.
No single process can then hold the comparison, so each block has to persist its own sample, and
once the sample is a file the arithmetic cannot live in the test either. It lives in
`scripts/contrast.py`, a pure module in the tree that ships in neither artifact and is covered at
100% like everything beside it. The block driver
(`brain/packages/orchestrator/tests/test_turn_cost_live.py`) therefore reports nothing and asserts
only invariants that hold whatever the model says, in the fold run's discipline.

**The A/B/A control needed no separate answer**: it is the recipe running its outer two blocks in
one configuration and its middle block in another. `contrast.py` treats the first sample as the
baseline and every later one as a contrast against it, so the last line of an A/B/A run is a null
whose interval ought to span zero.

Three alternatives were considered and rejected. A test that shells out to `docker compose` itself
was rejected on the ownership argument above. Changing the arm in process, which is what the fold
run did by constructing a `BrainRuntimeConfig`, cannot answer this question at all: it works when
the subject lives inside the brain process and the recall arm is chosen at the composition root
from the environment, so reaching it in process would mean building a second composition root and
measuring something other than what the container runs. Reporting the interval from inside the
test, the way the fold run prints its timings, was rejected because the arms are in different
processes and because the unreproducible half of the original run was never the turns: it was the
resampling, which carried no seed. `contrast.py` prints its seed with every report.

### The statistic, and why this one

Blocked (paired) **by question**, because a turn's time is dominated by how long its answer is,
which is a property of the question and not of the arm. The estimator is the **mean of the
per-question mean differences**, since a user pays the mean and averaging within a question first
weights every question equally however many repetitions it got. The interval is a **percentile
bootstrap over the questions, seeded**, rather than a t interval: the resampling unit is the
question, so n is six, far too small to lean on a normal approximation, and turn times are
right-skewed, bounded below by the model's own floor and unbounded above. **One warmup turn per
block is discarded**, because the turn immediately after a container recreate pays a cold gRPC
channel, a cold asyncpg pool and the model's first prompt eval, and letting that land inside a
measured cell would bias one question's mean in one arm only.

### What had to be built before any of it could run

**No `CORTEX_MEMORY_*` knob reached the dockerized brain.** The memory override set the backend,
the DSN and the embedder endpoint, and nothing else, so the runbook had been telling operators to
set `CORTEX_MEMORY_RECALL=raw` and `CORTEX_MEMORY_RECALL_AUDIT=1` on a container with no way to
receive either. The original run must have driven a brain started some other way. The fix is a
block of **bare pass-through keys** on `docker/docker-compose.memory.yml`, one for every
`MemoryConfig` field the file does not itself set: a mapping key with no value reaches the
container when the host sets the variable and never enters the container's environment otherwise.
The rule is "every field this file does not set" rather than a hand-picked few, so a documented
knob can never again be one the dockerized brain cannot receive. Spelling defaults instead
(`${CORTEX_MEMORY_RECALL:-judge}`) was rejected: it restates a shipped default in a second language
where it can drift, which is the thing `crosscheck.py` exists to catch.

Two of the deferral's own claims did not survive the tree. It said corpus seeding was settled by
the fold run, whose shape is conversation history written through `RedisSessionStore` and removed
with `delete`; a turn-cost corpus is 41 memory notes written through `PgVectorMemoryStore`, each
needing the CPU embedder first and removed with `delete_scope`. What carried over was the
discipline, test-owned ids deleted in a `finally`, and never the mechanism. And `recall_corpus.py`
was importable from another package's tests only by accident of pytest prepending a collected
file's own directory; the workspace now names that directory in `pythonpath` and `extraPaths`, so
the shared corpus is reachable on purpose.

### The protocol, at the size it was run

**The same size as the original**: six questions, one per corpus category, eight repetitions, 48
measured turns an arm, three blocks in A/B/A order (`raw`, `judge`, `raw`), 144 measured turns plus
three discarded warmups. Roughly 14 minutes end to end on the 24 GB card with the resident cortex
(gemma-4-12B). Each turn runs in its own fresh session under `CORTEX_MEMORY_SCOPE=session` whose
scope is pre-seeded with all 41 notes, with `CORTEX_MEMORY_RECALL_AUDIT=1` on throughout.
Repetitions are rep-major, so drift over a block spreads evenly across the questions rather than
pooling inside one. The 41 embeddings are computed once per block and reused, a vector being a pure
function of the note text and a fixed model. Two details the original addendum did not record are
now decided rather than guessed: **which six questions** (the first of each category in `QUESTIONS`
order, a rule rather than a hand pick) and **the seed** (printed with every report).

### The numbers

| | raw (block A) | judge (block B) | raw (block C) |
| --- | --- | --- | --- |
| Time to first token, mean | 3.518 s | 4.057 s | 3.584 s |
| Time to first token, median | 3.530 s | 3.812 s | 3.393 s |
| Time to first token, sd | 0.889 s | 1.468 s | 1.475 s |
| Whole turn, mean | 3.970 s | 4.950 s | 4.114 s |
| Whole turn, sd | 0.921 s | 2.136 s | 1.581 s |
| Rank bases seen | `echo` | `verdict`, `demur` | `echo` |

Every row above except the last is re-derived by running `scripts/contrast.py` over the committed
samples, and the last one is not, which is worth saying plainly in a section claiming the run
reproduces itself. The bases were read from the brain's audit trail with
`CORTEX_MEMORY_RECALL_AUDIT=1` while the blocks ran, and a turn record carries the wire timings
alone, so that row is evidence the arm really changed rather than a figure the samples can be
asked for again. Reproducing it means rerunning the blocks with the audit on and reading the
container's logs before they roll.

Blocked by question and bootstrapped over 20,000 resamples at the printed seed:

- **judge against raw: time to first token +0.539 s** (95% CI +0.054 to +1.111), whole turn
  **+0.979 s** (95% CI +0.098 to +2.313).
- **The null arm, raw against raw: +0.066 s** (95% CI -0.287 to +0.410), an interval spanning zero,
  and on the whole turn +0.144 s (95% CI -0.197 to +0.471), likewise spanning zero.

**The time to first token reproduces the published figure independently.** 0.539 s against 0.515 s,
on a different day, a different container and a driver rebuilt from the prose rather than restored
from the scratchpad. The interval is wider (+0.054 to +1.111 against +0.116 to +0.915) even though
the cost itself came out marginally larger, on a baseline that is faster (3.518 s against 4.296 s).
What widened it is the spread across the blocking unit rather than the size of the effect: the
resampling unit is the question, n is six, and one of those six costs +1.76 s against a mean of
+0.539 s, which is what the per-question layout shows and the next paragraph reads off.

**The whole-turn figure does not reproduce, and the samples say why.** The original published
+0.526 s on the whole turn, essentially the same as its time to first token; this run measured
+0.979 s, nearly twice it. The cause is one cell, and it is the same cell on both metrics. Paired
by question over the whole turn, the unanswerable question costs **+4.13 s** under the judge while
the other five span -0.31 s to +0.97 s; on time to first token, which is the layout `contrast.py`
prints under the interval, that question costs +1.76 s and the other five span -0.33 s to +0.88 s.
Its answers run 675 characters under `judge` against 84 under `raw`. That one cell alone carries
0.688 s of the 0.979 s whole-turn mean, 70% of it. This is the abstention addendum's behavior seen
from the outside. When the rank demurs, the turn has no memory block at all and the model says at
length that it does not know, where the cosine's five nearest misses give it something short and
wrong to say. So the judge's extra cost on a whole turn is partly the rank and partly the length of
an honest refusal, and how much of each a deployment sees depends on how many of its questions
memory cannot answer.

**One question carried three times the mean difference on time to first token and four times it on
the whole turn**, which is why `contrast.py` prints the per-question layout under the interval
rather than the interval alone. An aggregate that hides that would let a reader take a uniform half
second from a number that is nothing of the kind.

### Distrust green

The harness must be able to fail, and each of these was fired before the run was believed.

| Broken on purpose | Result |
| --- | --- |
| the seam endpoint points at a closed port | the block dies on `StatusCode.UNAVAILABLE` naming the address, writes no sample, and still cleans up its scopes |
| the brain runs without `CORTEX_MEMORY_SCOPE=session` | the first turn fails on `held 41 rows against the 41 seeded` and the block stops there, since a scope the brain did not record into is a scope it did not recall from |
| two blocks that asked different questions | `contrast.py` refuses to pair them rather than silently comparing what it has |
| the two arms that should not differ | the null contrast spans zero on both metrics |

The second is the guard worth naming twice. Session scoping being off is the failure that would
quietly invalidate a whole run: recall would range over every scope in the table rather than the
turn's own 41 notes, and every number would still look plausible. It is caught by arithmetic rather
than by reading the config, because the scope a turn recalls from is the scope it records into, so
a turn that really had memory on leaves more rows than it was handed. Firing it costs one stray
note in the global memory space, since the turn is recorded before the count can be read, and the
driver's docstring records that rather than cleaning it up: the only forget primitive `MemoryStore`
offers is `delete_scope`, and the global space is the one scope its own contract says a caller must
never hand it.

### Deferred by this addendum

**Nothing.** The one thing this close had to build on the way, the pass-through block that lets a
`CORTEX_MEMORY_*` knob reach the dockerized brain, was a defect and is fixed rather than filed. The
per-question layout was built rather than deferred, this run having proved in its own numbers that
the interval alone misreads.

## Candidate-count addendum (2026-08-10): the trail says what the pool was drawn from

The dropped-candidate addendum above taught the line to separate "was a candidate and the rank
passed it over" from "was not a candidate", and stopped there, which is exactly what its own entry
had asked for. It opened the next question in the same breath: an id in neither `hits` nor
`dropped` has three possible explanations, and the line could tell them apart for none of them.
The memory ranked below the pool cutoff, or its scope was not read, or it was never written.

### The trigger did not fire, and the work was taken anyway

This is recorded plainly because the bookkeeping is worth more than the appearance. The entry's
trigger was the first investigation whose memory is not in the pool at all, or a deployment that
has widened its pool and wants to know whether it is wide enough. **Neither has happened.** No
investigation has run and no pool has been widened. It was taken because the user asked for the
backlog to be worked and this entry's only blocker was its trigger rather than a cost argument or
an undecided question, and because the same thing that gave the dropped-candidate close its urgency
gives this one its: `CORTEX_MEMORY_RECALL` ships as `judge`, which keeps about one note where the
cosine kept five, so the trail is thinnest exactly where most of the pool now disappears. A
deferral taken ahead of its trigger is a decision like any other and is written down as one.

### Re-derived from the tree first, and one of the entry's own claims did not hold

The entry filed itself small on the ground that two of the three causes are derivable by a reader
holding the deployment's config, so logging them would be convenience rather than information. Read
against the code, one of those two is exactly right and the other is not.

**The scopes claim holds exactly.** `GlobalMemoryScope.read_scopes` returns `None`, which is every
namespace, and `SessionMemoryScope.read_scopes` returns the one `session_id` (`scope.py`). The line
already carries `session`, so `CORTEX_MEMORY_SCOPE` plus that field determines the read scopes with
nothing left over.

**The requested-width claim does not.** The entry says the requested width is `k` times
`CORTEX_MEMORY_RECALL_POOL_FACTOR`. That is true of the judge and the three heuristic policies, and
false of `RawRecallPolicy`, whose `candidate_k(k)` is `k` with no over-fetch at all (`rerank.py`),
which is what `CORTEX_MEMORY_RECALL=raw` still selects as the shipped opt-out. It is false a second
way on a fallback line, where the emitted basis is the fallback's while the width was the judge's,
so a reader deriving the width from the basis derives the wrong one precisely when the model could
not be reached.

That correction turns out not to cost anything, because the fix makes the derivation unnecessary
rather than merely easier. See the decision below.

### The third cause, and why it is the only one worth a field

`pool_size` is how many candidates came back and never how many there were. A pool filled to its
requested width is byte-for-byte the same line as a store that held exactly that many, so a memory
missing from a full line was either cut by the cutoff or absent from the store, and nothing on the
line says which. No reader derives that from any config, because it is a property of the data
rather than of the deployment.

The entry priced this correctly and ahead of time: it is **not** behind the unchanged port.
`MemoryStore.search` returns the top rows and reports no total, so the number has to come out of
the store. That is the port, both adapters, the fake, the contract test, and a count beside the
ranked select in the pgvector one. The shape survived contact with the tree unchanged.

### What the count cost, measured rather than assumed

The obvious worry is that an exact total means a second full scan on the hot path of every recall,
and that a bounded or capped count is therefore the honest design. Measured, that worry is
backwards, and the measurement also rules out the shape that looks cheapest on paper.

Postgres 16 with pgvector, the shipped `memories` schema, 768-dim vectors, `k` 20, timed over six
repetitions per shape at two table sizes:

| Shape | 20k rows | 100k rows |
| --- | --- | --- |
| the ranked `SELECT`, unscoped | 290 ms | 520 ms |
| the ranked `SELECT`, scoped to 3 of 50 namespaces | 19 ms | 88 ms |
| `count(*)`, unscoped | 0.45 ms | 2.0 ms |
| `count(*)`, scoped | 0.12 ms | 0.18 ms |
| `count(*)` capped at 200 | 0.09 ms | 0.09 ms |
| the ranked `SELECT` plus `count(*) OVER ()` | 293 ms | **1480 ms** |

Three readings, and each one decides something.

**The count is not a second scan of what the search scanned.** `EXPLAIN (ANALYZE, BUFFERS)` shows an
Index Only Scan over `memories_scope_idx` with `Heap Fetches: 0`, 21 shared buffers at 20k rows: the
btree that already exists for the scope filter serves the count, and it never touches the 87 MB of
heap the vectors live in. What makes the search expensive is detoasting every row and computing a
768-dimension distance for it, and the count does neither. So the count is not a fraction of the
search's cost by luck; it is cheap for a structural reason that holds as the table grows, which the
two sizes bear out (the ratio stays under one percent).

**A cap buys nothing worth having.** Capping saves at most 2 ms against a 520 ms search, and it
pays for that by turning an exact number into "at least this many", which is the weaker answer to
both halves of the question the entry asked. Exact it is. The honest worst case was measured too:
on a table with 5,000 unvacuumed inserts, where the visibility map is dirty and every row costs a
heap fetch, the unscoped count rose to 22 to 31 ms at 105k rows, still under 6% of the search, and
autovacuum retires it.

**The one-statement shape is the expensive one.** Folding the total into the ranked select as
`count(*) OVER ()` is the design that needs no second round trip and no consistency caveat, and it
costs **2.85x the plain search** at 100k rows. The plan says why: `WindowAgg (actual
time=36.313..1504.610 rows=100000)` sits under the `Limit`, so the whole target list, including
`embedding::text` for every one of the 100,000 rows, is materialized before the top-20 heapsort can
discard it. At 20k rows this is invisible, which is the trap: it would have shipped looking free
and grown into the most expensive statement in the recall path. Two statements it is, and the
consistency caveat is documented rather than papered over.

### Decision

1. **A new port verb, not a wider `search`.** `MemoryStore.count_candidates(*, scopes=None) -> int`
   answers how wide the candidate set is; `search` is untouched and still means "the top `k`". The
   `scopes` argument means exactly what it means for `search`, which is what makes the two describe
   one set. Widening `search`'s return would have made every caller pay for a number only the trail
   reads, and there is one production caller besides.
2. **The store's own count, never a length over rows.** This is the whole distinction the verb
   draws: a count that stops where a search stopped reports the cutoff back to itself and says
   nothing. The pgvector adapter issues `SELECT count(*) AS total FROM memories` with the same
   `WHERE scope = ANY` a scoped search applies; the in-memory twin counts the same filtered list it
   would have ranked.
3. **`RecallAudit` gains a required `available`, and the reading is a comparison.** Equal to
   `pool_size`, the pool WAS the whole readable store, so an id on neither list was never written or
   was written outside the read scopes. Below it, the pool was cut and an absent memory may only
   have ranked under the cutoff. `LoggingRecallSink` grows one key and decides nothing.
4. **The requested width is still not logged, and now for a better reason than the entry's.** The
   entry called it derivable, which is false under `raw` and on a fallback line. It need not be
   derived at all: where the width would matter, meaning the pool was cut, it is exactly
   `pool_size`; where it would not, nothing was cut and it explains nothing. `available` makes the
   width redundant rather than merely inferable, so the correction costs no field.
5. **Counted only when a sink is wired, and counted next to the search.** The call sits inside
   `MemoryRecaller`'s `audit is not None` guard, so an unaudited recall issues no counting query at
   all and the trail stays free when off, which is the dropped-candidate close's design point
   carried forward to the one read here that reaches a database. It runs straight after the search
   rather than after the rank, because these are two reads and not one transaction and a model rank
   sits between them for the best part of a second; adjacent statements are as close as two reads
   get to one moment.
6. **A failed count fails the recall.** It is not swallowed into a `None` or a guessed figure. The
   count travels the same pool and the same connection as the search that just succeeded, so a
   failure there is a real store failure, and the trail's own sink already fails a recall the same
   way. An audit line that invents a number is worse than one that stops.

### Consequences

- `RecallAudit` gained a second required field in two days. Both are the same kind of change and
  the same intended direction: the port carries more, and no adapter is left silently emitting
  less because its value type still compiles.
- The contract test is now run over **both** implementations rather than only the live one.
  `memory_contract.ALL_CHECKS` was driven solely by the integration run against real pgvector,
  while the fake was checked by hand in `cortex_core`'s own tests, so a check added to the shared
  file reached CI only if someone remembered to write it twice.
  `packages/memory/tests/test_memory_store_contract.py` closes that with the arrangement
  `TaskStore` and `ScheduleStore` already use. A count faked as a length over rows is exactly the
  defect that gap would have hidden from everyone without a database.
- The memory area's three fakes (`HashEmbedder`, `InMemoryMemoryStore`, `RecordingRecallSink`) moved
  to `fakes_memory.py` under the line cap as the new verb landed, the `fakes_session.py` precedent.
- No cross-tree coupling arrives. The contract check's size is a floor sized from the shipped pool
  width rather than an equality anything depends on, so `crosscheck.py` has nothing new to hold.

### Distrust green

Eight mutations, six against the CI suites and two against real Postgres, each reddening only what
it should:

| Mutation | Result |
| --- | --- |
| the count stops at the pool cutoff | 1 failed (the contract check, over the fake) |
| the recaller measures `available` off the pool it already holds | 2 failed |
| the count ignores its scope filter | 2 failed |
| the sink drops the `available` key | 1 failed |
| the count is issued whether or not a sink is wired | 1 failed |
| the pgvector count is bounded by a `LIMIT` | 2 failed |
| **live:** the adapter answers with `len(rows)` over a cutoff-limited select | 1 failed |
| **live:** the count ignores the scopes the search filtered on | 1 failed |

The first row is the one that had to be fixed rather than merely watched. The contract check was
written with three memories, which a count capped at anything from three upward passes; it caught
the mutation only once the check held more memories than the widest pool a shipped deployment
fetches. A check whose size lets the defect agree with it by luck is the gate that cannot fail, and
this one was one number away from being it.

### Verified live

The `integration` suite against real Postgres + pgvector in its own `cortex_contract` database:
`1 passed, 39 deselected`, the three new checks included. The two live mutations above were run
against the same store and reddened `check_count_candidates_sizes_the_set_a_search_ranked` on
`20 != 25`.

### Deferred by this addendum

**Nothing.** The two derivable causes are answered by not building them, argued in decision 4
rather than filed, and the count is exact so there is no bound to revisit.

## Cut-fold addendum (2026-08-18): a rejected fold says why, and the earlier "not a signature change" is reversed

A fold whose account `clean_recap` rejects logs one line, "the model returned no usable history
recap; falling back to the plain window", carrying `session_id` and `boundary` and nothing else.
The fallback is silent and self-heals on the next boundary move, both by design, and together
those two properties mean nothing accumulates for a reader to compare: the completion that was
rejected is gone the moment the turn is. So an operator watching a fold that keeps falling back
is left with two fixes that point in opposite directions, raising `RECAP_MAX_TOKENS` or folding
less, versus rewriting `_INSTRUCTION`, and no way to choose between them.

**The behaviour wants nothing, and that has not changed.** `clean_recap` rejects on shape rather
than on transport, and that check is right whichever way this decision goes: it catches a fold the
server cut, a fold the model ended mid-thought, and a fold that arrived mangled, where a stop
reason catches only the first. Rejecting rather than trimming stays load-bearing for the reason
already recorded, that a stored cut account advances `covers` past turns its missing tail never
reached. Nothing here touches any of it. This addendum is entirely about the line beside it.

**What the log now carries, and why it is exactly two fields.** `capped`, taken from a
`StopLedger` the fold hands to `drain_text`, is the only reading that separates a fold the token
budget cut from one the model ended in the wrong shape. Those are the two cases with opposite
fixes, and they produce byte-identical text, so no amount of inspecting the rejected account can
tell them apart. `chars` is the account's length, and it splits the two causes a stop reason
cannot: `0` is a model that said nothing at all, a number past `RECAP_MAX` is one that ran further
than the store will hold, and in between is the bucket where `capped` does the work. That second
half is free and needs no signature at all, which is why it is here rather than filed.

The length is measured through `collapse_recap`, a new one-line public function in
`recap_prompt.py` that `clean_recap` now calls too. That indirection exists for one reason: the
number a rejection is *logged* with must be the number the rejection was *decided* on. A second
spelling of the same normalization would agree with the first everywhere except on a reply sitting
within a few characters of `RECAP_MAX`, which is precisely the reply whose bucket a reader would
be trying to settle.

**The reversal, stated rather than slipped in.** ADR-0005's finish-reason addendum considered this
exact consumer and declined it in writing: making the fold read a stop means changing `drain_text`,
which returns a `str` and has three callers who want exactly that, and "that is worth a log line
and not a signature change". That sentence was right about the cost and wrong about the
alternative, because there is no log line that reaches this without the signature. The stop reason
is the fact, and the fact is not otherwise in the fold's hands: it comes off the completion and
`drain_text` was dropping it. So either the helper carries it or the diagnosis does not exist.

What makes the reversal cheap is that the shape it declined is not the shape that landed. It
priced a result value or an out parameter, either of which would have grown the session title and
the rerank judge a field they ignore. What landed is an **optional collaborator**,
`stops: StopLedger | None = None`, which is not a new pattern here at all: it is exactly how
`ToolLoopContext` threads a ledger into `stream_tool_loop`, and exactly how `cadence` is threaded
beside it. A caller that hands none drops the stop as this helper always has, the return type is
still a bare `str`, and the other two callers are byte-identical. ADR-0005's own text stands as
written; it was true on its date, and this records where it stopped being.

**Consequences.**

- `drain_text` goes from five arguments to six, which is ruff's `max-args` ceiling exactly. It
  passes, and it is now full: a seventh collaborator wants the `ToolLoopContext` move, a bundle,
  rather than another keyword. That is stated in the docstring so the next person meets it before
  the linter does.
- The two callers that want only a string are unchanged, which was the whole objection to the
  earlier shape.
- A quiet backend still reads as uncut. `StopLedger` treats an absent report as "not capped", so a
  build that reports no reason logs `capped=False` and a reader is not sent after a token budget
  that was never the problem. That property is the ledger's, not this consumer's, and it is what
  makes reusing the ledger safe here.

Filed rather than built: `JudgeRecallPolicy` is the other `drain_text` caller with a fallback, and
its three fallback sites log **nothing at all**, so a rank that quietly fell back to geometry
cannot be told from one that never ran. The fold now says why it gave up and the judge still does
not ([R-309](../refinements/tasks/309-a-silent-judge-fallback.md)).

## Unjudged-rank addendum (2026-08-19): the rank that fell back to geometry says which way it did

`JudgeRecallPolicy` is the shipped default recall policy, so its fallback is the path most turns
take when anything is wrong with the model, and until now it took that path in complete silence.
`rerank_judge.py` imported no logger at all. The pool came back ranked by cosine, the ranking
carried the fallback's own basis, and nothing anywhere said the model had been asked and had not
answered. A deployment whose judge had never once answered was indistinguishable from one where it
answers every turn, which is a worse blindness than the fold's: a rejected fold at least logged a
line saying it had been attempted and rejected.

**The behaviour is untouched, again.** Every fallback still falls back to the same policy with the
same basis, the refusal is still believed, and `parse_order` still has its three outcomes. This is
the line beside them.

**Two of the four exits log, and two do not, and which is which is the decision.** A `select` that
returns without a verdict does so in one of four ways, and they are not one event:

- An **empty pool** logs nothing. No candidates means no judgement was possible and none was
  attempted, so there is no fault to report; a line here would fire on every turn a deployment
  recalls nothing on and would dilute the two that mean a rank was lost. This is the same silence
  `SummarizingHistoryWindow` keeps when its inner window dropped nothing.
- An **`InferenceError`** logs `the model could not be asked to rank recall; falling back to the
  unjudged ranking`, carrying the pool it gave up on, the `k` asked of it, and the backend's own
  error as `exc_info`. There is no completion to describe on this path, so the cause is the
  exception rather than a field.
- A **reply no order can be read out of** logs `the model returned no usable recall order; falling
  back to the unjudged ranking`, with the two readings below.
- A **refusal**, the complete `{"order": []}`, logs nothing, and that is how the failure/refusal
  distinction `parse_order` draws survives into the log rather than being flattened back. A refusal
  is the model judging and declining, which is the one thing a judge can do that geometry cannot,
  and it is already on the recall trail as the `demur` basis beside every other per-recall fact. A
  line for it would put a second, ungated per-recall stream next to the one this ADR deliberately
  put behind `CORTEX_MEMORY_RECALL_AUDIT`. So every line from this module means the same thing, the
  configured rank did not run, and a reader counting them counts faults rather than unanswerable
  questions.

**The stop reason is carried here too, and the open question is answered by the precedent rather
than against it.** The bounded-side-calls addendum argued that this path need not consume a stop,
since the judge decodes under `ORDER_ENVELOPE` and a cut envelope is not JSON, so `parse_order`
catches it structurally. That argument is still true about the **behaviour** and says nothing about
the **reading**, which is exactly where the cut-fold addendum reopened the same question for the
recap fold one day earlier. The two `drain_text` callers with a fallback now answer it the same
way. What made it cheap here is that the fold already paid for it: `drain_text` grew
`stops: StopLedger | None = None` then, so this rank threads a ledger and changes no signature at
all.

**What the line carries, and why exactly two readings.** `capped` separates the two causes with
opposite fixes, and they are indistinguishable in the text: a rank cut at `rank_bounds(k)` comes
back `{"order":` (measured), and a model that ended by itself in the wrong shape can come back the
same way. True wants a wider bound or a smaller `k`; False wants the constrained decoding checked.
`chars` splits that second case again for free: `0` is a model that emitted no assistant text at
all, which on this path means a reasoning tier ignoring `thinking=False` and putting the whole
reply where `drain_text` drops it, and any other length is text that arrived and was not the
envelope. Unlike the fold, no normalization stands between the number and the decision:
`parse_order` is handed the same `raw` whose length is logged, so there is no second spelling to
disagree with the first and no `collapse_recap` analogue is needed.

**Both readings ride the message as well as the record.** The brain configures
`logging.basicConfig(level=logging.INFO)` and nothing else, so the shipped handler prints
`levelname:name:message` and no `extra` field reaches an operator's `docker compose logs`. This is
the lesson `LoggingRecallSink` already records for the trail, where the fields ride the record
twice for exactly this reason. The `extra` keys stay, since they are what a structured collector
reads, and the message carries `capped=` and `chars=` so the diagnosis is legible under the handler
this repo actually ships.

**Consequences.**

- The judge's warnings cannot name a session or a turn, because `RecallPolicy.select` carries
  neither: the port takes the pool, the query, the clock's reading and `k`. Every neighbouring
  degradation warning names a session, and so does the recall trail line an operator would want to
  correlate with, so this is a real gap and it is a port change rather than a log change
  ([R-316](../refinements/tasks/316-a-rank-fallback-cannot-name-its-turn.md)).
- The recap fold's own `capped` and `chars` remain `extra`-only, so they are invisible under the
  shipped handler while these are legible. The general fix is a handler that renders the fields
  rather than a second module rendering them by hand
  ([R-317](../refinements/tasks/317-shipped-handler-drops-every-field.md)).
- Nothing about the rank's cost changes: no call is added, and the ledger is a local object with
  one boolean.

### Deferred by this addendum

The two consequences above, both filed rather than built: the session a fallback happened in, which
needs the port to carry one, and the handler that would make every `extra` field in the brain
readable.

## Rendered-fields addendum (2026-08-19): the handler prints what a record carries, and three hand-rolled renderings come out

The addendum above ends by conceding a defect it could only work around: the brain configured
logging with `logging.basicConfig(level=logging.INFO)` and nothing else, so the shipped handler
printed `levelname:name:message` and every `extra` field this repo attaches was written onto a
record and dropped. The rank fallback therefore spelled `capped=` and `chars=` into its own
message, which was the third module to do so. `LoggingRecallSink` had done it first and says so in
its docstring, `LoggingAuditSink` second. Three hand-rolled renderings of fields that were already
on the record is two more than the problem deserves, and the fix was never a fourth.

### Re-derived from the tree first, and the entry's own survey came up one short

Every claim of [R-317](../refinements/tasks/317-shipped-handler-drops-every-field.md) held. Two
process entries configure logging: `cortex_orchestrator.__main__` at a hardcoded INFO, and
`cortex_model_manager.server.main` at a configured level. The fields named as lost are lost: a
rejected fold's `capped` and `chars`, a stranded `handoff`, a retried `task_id`, a forgone recall's
`session_id` and `turn_id`.

The survey the entry did not do turned up a **fourth** rendering family, and it changes the shape
of the answer rather than only its size. The model host's lifecycle lines spell `model=`, `pid=`
and `port=` into their messages for the same stated reason, and so do about twenty other sites
across `residency_*`, `swap_builders` and the model-host adapter. That family is left alone here
and filed as [R-323](../refinements/tasks/323-a-field-spelled-into-its-own-message.md), on two
grounds. Its members double a handful of short tokens rather than a whole JSON object, so the
duplication is legible where the audit sinks' would be unreadable; and the runbook grep patterns
that hunt a swap are written against those message texts, so sweeping them is a documentation
change across the runbooks that read them rather than a formatter change.

The third entry point is genuinely different and stays untouched: `cortex_email` configures no
logging, imports `logging` nowhere, attaches no field anywhere, and does not depend on
`cortex-core`. Giving it a formatter would mean giving a deliberately standalone MCP sidecar a
dependency on the brain's core for a capability it does not exercise.

### Decision 1: plain appended fields ship, JSON lines are the alternate, and the deployment picks

`cortex_core/log_format.py` carries two renderings behind one `build_formatter(style)` seam:

- **`plain`** appends `key=value` pairs, in name order, after the message. The half of the line
  before the fields is byte for byte what `basicConfig` printed, since the formatter builds on
  `logging.BASIC_FORMAT` rather than restating it.
- **`packed`** writes one JSON object per line, with the fields under their own `fields` key so no
  attached field can shadow `level`, `logger` or `message`.

`plain` is the default, and the argument is about who reads these logs rather than about taste.
This is a personal, local-first assistant whose operator reads `docker compose logs brain` in a
terminal, and that stream is **mixed**: uvicorn writes its own access lines into it, llama.cpp
writes raw stderr, and neither will ever be JSON. So a JSON default would not buy a
machine-readable stream, nothing being able to parse the whole of it, while costing the one reader
who exists the ability to read a line at a glance. It would also break every documented reading in
the runbooks at once, since JSON spells `capped=True` as `"capped": true`.

`packed` exists anyway, because which of those a deployment wants is a property of the deployment
and not of this file, and because a rendering that is one `if` away from existing is not a seam
until it does. It is chosen by env like everything else: `CORTEX_LOG_FORMAT` for the brain, and
`CORTEX_MODELHOST_LOG_FORMAT` for the sidecar, whose own env already prefixes its level that way.
A name neither carries raises `UnknownLogFormatError` at the entry, before anything is served,
rather than falling back to a rendering nobody asked for.

**Naming.** The pair is one family: how a record's fields are set down for whoever reads them, laid
out plainly beside the message or packed into one carton for transport. Two alternates were weighed
and declined. `plain`/`json` names one entry for its wire format and the other for its lack of one,
so the family has no shared metaphor and a third rendering would have nowhere to stand.
`loose`/`sealed` is more evocative and costs an operator reading an env file at three in the
morning the ability to guess what they will get.

### Decision 2: the three renderings the entry named come out, and the runbooks survive

**This reverses the unjudged-rank addendum's "both readings ride the message as well as the
record"**, which was right about the handler that shipped that day and wrong the moment one
renders fields. Under `plain` the redundancy stops being harmless: `LoggingRecallSink` would print
its whole JSON payload and then every field of it again. So all three come out. The recall trail and the tool
audit now log a bare `memory.recall` / `tool.invocation` message with `extra` alone, and the rank
fallback's message ends at `falling back to the unjudged ranking`.

The runbooks needed less repair than expected, which is a property of `plain` rather than luck.
`docs/runbooks/memory-pgvector.md` sends an operator to `grep "unjudged ranking"`, and that text is
untouched. Its reading table asks for `capped=True` and for `capped=False chars=0`, and both still
appear, adjacently, because fields render in name order and `capped` sorts before `chars`. The two
things that did change are documented there: the trail line is now `key=value` pairs rather than
one JSON object, and `hits` and `dropped` arrive as compact JSON inside their own field.

### Decision 3: the formatter defends the secret ban itself, by name and by shape

This is the one change in the repo that could turn a careless `extra=` into a leak, since the whole
point of a formatter is that it prints fields nobody enumerated. AGENTS.md bans secrets in logs
outright, so the defence is part of the formatter rather than an obligation on its callers, and it
has two halves because the leak has two shapes.

**By name.** A field whose name contains `token`, `password`, `passwd`, `secret`, `credential`,
`apikey`, `api_key`, `authorization` or `cookie`, case-insensitively, prints `<redacted>` instead
of its value. A **denylist** rather than an allowlist, deliberately: an allowlist would have to be
edited for every new field, which is this very defect wearing a different hat, a field nobody
registered being silently dropped instead of never printed, and a silent drop is the harder of the
two to notice. The match is a substring, so `max_tokens` is withheld too. That is the trade this
direction of error buys: a token count a reader can recover from the message costs less than one
bearer token reaching a terminal. The value is replaced rather than the key removed, so a reader
can tell a withheld field from a missing one.

**By shape.** A credential inside a URL is stripped from the **whole rendered line**, message and
traceback included, rather than field by field. That one arrives in a message and in a stack at
least as often as in a field: `redis://:pw@redis:6379` is what a connection error prints, and both
the session store and the mail bridge are configured as URLs. A bare email address is untouched,
having no scheme in front of it.

The three concrete secrets this deployment holds are all named for what they are, so both halves
are asserted against them: the seam token, the mail bridge's password, and a model host credential.

### Distrust green

Measured in this session, each mutation applied to production code alone with
`packages/core/tests/test_log_format.py`, `packages/memory/tests/test_recall_audit.py` and
`packages/tools/tests/test_audit.py` re-run (34 cases):

- dropping the appended fields from `PlainFormatter.formatMessage` reddens **11**, including both
  audit trails, which is the point: the trails now depend on the formatter and their tests say so;
- dropping the URL redaction from both formatters reddens **2**;
- dropping the secret-name redaction from `record_fields` reddens **3**.

The reserved-attribute set has its own guard, asserted as a difference in both directions, so a
Python release that adds a `LogRecord` attribute reddens a test here rather than printing a new
stdlib field as though a caller had attached it.

### Verified live

`docker compose logs brain` on the shipped stack, which is the only place an operator reads these.
The line the seam server logs at boot carried its two fields for the first time.

### Consequences

- The two audit trails now **depend** on a formatter being installed. That is a real coupling and
  the right one: handler configuration belongs at a process entry, and a library that renders its
  own fields into its message is a library that has given up on the entry doing its job.
- `configure_logging` is the one function in the core that changes process-wide state. It is called
  only from a process entry, and it forces its handler on, an entry point stating what a process
  logs like rather than asking.
- Nothing about a turn's cost changes: the formatter runs once per emitted record, on a path that
  was already formatting a string.

### Deferred by this addendum

Two, both filed rather than built: the wider family of fields spelled into their own messages
([R-323](../refinements/tasks/323-a-field-spelled-into-its-own-message.md)), and the fact that a
field's rendered value is unbounded, so an `extra` carrying a large or conversational value would
print in full ([R-324](../refinements/tasks/324-a-rendered-field-has-no-bound.md)).

## Twice-printed-field addendum (2026-08-19): a message stops spelling the fields its own record carries

The addendum above installed the formatter, took out the three hand-rolled renderings it had come
for, and filed the wider family it found beside them rather than sweeping it. This is that sweep.
Every site in it had the same history: the field was on the record and invisible, so the call site
wrote it into the message too, and the moment a formatter rendered records the workaround became
the same value printed twice, `started a model process: model=cortex pid=41 port=8081 model=cortex
pid=41 port=8081`. Nothing was wrong with the fields; what was wrong was the second copy.

### Re-derived from the tree first, and the entry's count was half the real one

The entry said "about twenty". An AST pass over every `logging` call in `brain/packages/*/src`
found **31**, across 13 files. The entry's file list was right as far as it went and named eleven
files; two more carry a site of the same family and are what the re-derivation added,
`swap_conductor.py` (the refused escalation) and `swap_recovery.py` (the boot line that says no
handoff can ever run). The count matters only in that it is the second time this ADR's entry
survey undercounted a family, which is the argument for re-deriving one from the tree before
believing it.

By package: 16 in `cortex_model_manager` (`supervisor.py` 4, `adapter.py` 5, `api.py` 2,
`device_memory.py` 3, `children.py` 1, `server.py` 1), 12 in `cortex_core` (`residency_sweep.py` 3,
`residency_moves.py` 3, `residency_regain.py` 2, `residency_watch.py` 2, `swap_conductor.py` 1,
`swap_recovery.py` 1) and 3 in `cortex_orchestrator` (`swap_builders.py`). `cortex_email` is
untouched for the reason the addendum above gave: it configures no logging and attaches no field.

### Decision 1: the message is a constant sentence and every value on the line is a field

A value the record carries is not interpolated into the message. What is left is a constant string,
so the message half of a line no longer varies (with the two exceptions decided below) and the
varying half is entirely on the right, in name order. Seven of the 31 needed more than a deleted token, because the value was a
word of the sentence rather than a token appended to it, and each was rewritten to say the same
thing without it. `no device memory reading is available from %s` became `no device memory reading
is available`, the binary being the `binary` field the line already carried; `the device memory
query exited with code %s` became `exited with a non-zero code`, which is the branch's own
condition, with the code in `returncode`; and the five `%r` clauses in the residency and swap paths
name generically what they used to interpolate (`does not serve this model at all`, `does not serve
the deep model`) with the id in `model=`.

**The gain is a grep that matches every instance of a line rather than one.** `docker compose logs
brain | grep "a model-host request failed"` now finds all of them however many models and errors
they name, where before a pattern either carried a value or stopped at the colon. That is also the
cost, stated honestly: a runbook that used to quote a line with a placeholder in it, as
`model-swap.md` did three times with `'<tier>'` and `'<deep model>'`, now quotes the whole sentence,
and the id it used to show inside the quote is read off the field beside it.

### Decision 2: two shapes keep a value in their prose, each for its own reason

- **A message that is also a raised exception's text.** Six sites build one string, log it, and
  raise it as a typed error. The string has to read on its own where no formatter runs (in a reply,
  in a traceback, in the runbook that quotes it), so it keeps its numbers, and the fields beside it
  repeat them. That is a real second reading of one value and it is deliberate; the alternatives,
  two strings per site or dropping the log call, are weighed in
  [R-325](../refinements/tasks/325-a-raised-message-is-also-a-logged-one.md).
- **A word that is the sentence's own predicate.** `residency_sweep._unanswered` keeps
  `a tier of the standing residency could not be %s`, where the verb is `started`. It is not a
  field, is not attached as one, and therefore cannot print twice; and `model-swap.md` sends an
  operator to grep that whole sentence. Attaching it as `verb=` would have cost the runbook its
  grep and the sentence its predicate, to gain a field nothing selects on.

### Distrust green

Each mutation was applied to production code alone, with the package's own suite re-run:

- dropping `extra=` from the two supervisor lifecycle lines reddens exactly
  `test_the_lifecycle_log_lines_name_the_tier_and_the_pid_they_are_about` (1 of 136);
- dropping `extra=` from the adapter's FAILED line reddens exactly
  `test_a_failed_state_is_a_normal_answer_and_is_logged_with_its_detail` (1 of 136);
- dropping `model` from the sweep's unhosted-tier line reddens exactly
  `test_a_tier_the_roster_never_had_is_recorded_once_and_never_asked_again`;
- dropping `error` from boot recovery's deep-tier line reddens exactly
  `test_a_deep_tier_the_daemon_does_not_serve_is_a_config_fault_not_an_amber_boot`;
- dropping `worst_s` from the deadline-pairing line reddens exactly the assertion that reads it off
  the rendered line, which is the one that moved.

The mutations matter more here than the count does. A test that asserted a field through
`getMessage()` would have gone on passing with the field deleted from the record entirely, which is
the failure this change had to avoid: a field silently lost is worse than a field printed twice,
and every assertion that depended on the message now reads the rendered line instead.

### Verified live

`docker compose --project-directory . -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml
logs model-host` against the real sidecar on this machine, twice: once from a build of the tree as
it stood before this addendum, and once from the tree after it, the same daemon starting the same
tier off the same mount both times. Before:

```text
model-host-1  | INFO:cortex_model_manager.server:model host configured: models=['cortex'] boot_model=cortex boot_model=cortex models=["cortex"]
model-host-1  | INFO:cortex_model_manager.supervisor:started a model process: model=cortex pid=8 port=8080 model=cortex pid=8 port=8080
model-host-1  | WARNING:cortex_model_manager.api:a model-host request failed: model=brain error=unknown model 'brain'; this host serves cortex error="unknown model 'brain'; this host serves cortex" model=brain
```

After:

```text
model-host-1  | INFO:cortex_model_manager.server:model host configured boot_model=cortex models=["cortex"]
model-host-1  | INFO:cortex_model_manager.supervisor:started a model process model=cortex pid=8 port=8080
model-host-1  | WARNING:cortex_model_manager.api:a model-host request failed error="unknown model 'brain'; this host serves cortex" model=brain
```

Every field appears once, none of them was lost, and the third line is the one worth reading twice:
the error the daemon returns is a sentence with its own punctuation, so the doubled copy ran two
readings of it together where the rendered field quotes it as one value.

### Consequences

- **Every runbook that quoted one of these lines moved with the code**, in the same commit:
  `model-swap.md` (three quotes and the log-reading pointer), `local-dev-wsl.md` (the reading rules
  gain the one this addendum adds), and `brain-model-manager.md`'s claim that the daemon's
  lifecycle lines still spell their tier and pid into the message, which was true when it was
  written and is now the opposite of what they do.
- **A line's message is now stable enough to be a grep pattern**, which is what these runbooks were
  already treating it as.
- Nothing about a turn's cost changes: this is a shorter format string and one fewer interpolation
  per emitted record.

### Deferred by this addendum

Two, both filed rather than built: the six messages that are logged and raised
([R-325](../refinements/tasks/325-a-raised-message-is-also-a-logged-one.md)), and the other end of
the same question, the lines that attach no field at all, headed by a quarantine line that names
the record it moved in prose only
([R-326](../refinements/tasks/326-a-line-that-names-nothing-it-happened-to.md)).

## Named-subject addendum (2026-08-19): a line that reports a failure says what it failed on

The addendum above took the values out of messages that carried them twice. This one is the other
end of the same question: the lines that carry no value at all. Most of them are honest, and the
two kinds that are not are fixed here, so a line saying something went wrong can be followed to
the record or the session it went wrong for.

### Re-derived from the tree first, and this time the count held

An AST pass over every `logger.*` call in `brain/packages` (91 of them, tests and generated stubs
excluded) found **17** that attach no `extra`, the number
[R-326](../refinements/tasks/326-a-line-that-names-nothing-it-happened-to.md) recorded. Nine of the
seventeen are honest and were left exactly as they are, which is the more interesting half of the
answer:

- **A pass guard has no subject.** `ticker.run`, `residency_heal.run` and the ticker's own
  done-callback each report that a whole pass or a whole loop failed. There is no id in scope
  because the failure is not about an item; the traceback is the diagnosis.
- **Two candidate subjects are worse than none.** `residency_moves` restoring the cortex and
  `swap_recovery` during boot each wrap two host calls naming two different models, so a `model`
  field on the failure would name the wrong one about half the time. Narrowing those try blocks so
  each failure names its own model is filed as
  [R-329](../refinements/tasks/329-a-failure-with-two-candidate-subjects.md) rather than guessed at
  here.
- **A traceback beside a store that could not be read.** `swap_conductor`'s two handoff-store
  failures and `swap_recovery`'s stranded-record read fail before there is an id to name, which is
  the entry's own example of an honest line.
- **The pump's own failure.** `converse_stream._pump` fails for the client stream, not for a turn:
  no session is in hand there, and the three turn failures below are the ones that hold one.

### Decision 1: the quarantine line's two values become fields

`quarantine` logged `quarantining corrupt schedule record %r to %r`, spelling the item id and the
dead-letter key into the message and attaching neither, so the one record of an item leaving the
working set could be grepped as a sentence and never selected on: `item_id=` matched nothing, and
`CORTEX_LOG_FORMAT=packed` put the id inside `message` instead of under `fields`. It now logs the
constant sentence `quarantining a corrupt schedule record` with `item_id` and `dead_key` attached,
which is the addendum above pointing the other way. The exception line one frame up, `undecodable
schedule record on the claim path`, carries `item_id` too: it is the same item, and a traceback
that names nothing cannot be joined to the quarantine that follows it.

### Decision 2: a mid-turn failure names the session, and nothing it does not honestly hold

`converse_stream`'s three turn failures (session store, inference, and the broad catch-all) attach
`session_id`. That is the whole of what the handler holds. **The `turn_id` is not available**: it
is minted inside the engine and only ever leaves it on a `TurnComplete` event, so a failed turn has
no id to name and reaching through the engine to manufacture one is exactly the layer-crossing this
repo does not do. What that costs, and what it would take to close, is
[R-328](../refinements/tasks/328-a-failed-turn-cannot-name-itself.md).

**The turn's text is not attached, deliberately.** It is the user's own words, and the formatter's
defence is a name denylist plus URL-credential stripping, neither of which can recognize user
content. The rule for this family is therefore: ids, counts and reasons ride as fields; anything a
person typed, a model generated, or a tool returned does not. The test asserts the absence, not
just the presence.

The fourth line in that module, the ignored client event, carries `session_id` and `kind`. `kind`
is `None` for the event a client sends with no payload set, which is not much; it is attached for
the other shape, a payload added to `ClientEvent` and not to the dispatcher, where the field prints
the new member's own name and is the only thing that would say so.

### Decision 3: the ticker's failures read their id off the claim beside them


`run_once` reported a failed fire by filtering the exceptions out of `asyncio.gather`'s results,
which threw away the one thing that identifies them: `gather` answers in the order it was asked, so
the claim beside a failure is the item that failed. The results are now zipped with the claims
(`strict=True`) and the line carries `reminder_id`. The release failure in the `finally` below
carries the same field off the claim it was releasing.

**`reminder_id` rather than `item_id`, which is a judgement call.** A claim can be a `TASK` as well
as a `REMINDER`, so the generic name reads more honestly; but `_deliver` already spends
`reminder_id` for both kinds (it is the seam's own field name on `notify`), and one id under two
names in one file is worse for the operator than one name that is slightly too specific. The
session adapter keeps `item_id`, which is what that module has always called it.

### Distrust green

Three mutations, each applied to production code alone with the package's own suite re-run:

- dropping `extra=` from the quarantine line reddens exactly
  `test_the_quarantine_lines_carry_the_id_and_the_key_as_fields` (1 of 117);
- dropping `session_id` from the inference failure reddens exactly the `_inference_failure` case of
  `test_a_turn_that_failed_names_the_session_it_was_serving` and neither of its two siblings, which
  is what pins the field to its own line rather than to the family (1 of 22);
- restoring the filtered `gather` results in place of the zip reddens exactly
  `test_both_pass_degradation_lines_name_the_item_they_are_about` (1 of 29).

### Verified live

The stack was brought up with scheduling on (`CORTEX_SCHEDULE_BACKEND=redis`), a corrupt record was
planted where a corrupted writer would have left one, and the ticker's next pass quarantined it:

```text
$ docker compose --project-directory . -f docker/docker-compose.yml exec redis \
    redis-cli SET cortex:schedule:poison-live "not json"
$ docker compose --project-directory . -f docker/docker-compose.yml exec redis \
    redis-cli ZADD cortex:schedules:due 1700000000 poison-live
$ docker compose --project-directory . -f docker/docker-compose.yml logs brain
brain-1  | ERROR:cortex_session.schedule_claims:undecodable schedule record on the claim path item_id=poison-live
brain-1  | ERROR:cortex_session.schedule_claims:quarantining a corrupt schedule record dead_key=cortex:schedules:dead item_id=poison-live
```

`grep -o item_id=poison-live` counts one occurrence on each line, so nothing doubled. The same
pass under `CORTEX_LOG_FORMAT=packed` is the claim the entry made, answered:

```text
brain-1  | {"fields": {"dead_key": "cortex:schedules:dead", "item_id": "poison-packed"}, "level": "ERROR", "logger": "cortex_session.schedule_claims", "message": "quarantining a corrupt schedule record"}
```

The id is under `fields` where `jq .fields.item_id` reaches it, and the message is a constant.

### Consequences

- **`docs/runbooks/scheduling.md` gains the grep** for the quarantine, which it could only describe
  as "logged loudly" while the id was prose.
- **Nine lines were left alone on purpose**, and the reasons are written above so a later sweep
  does not read them as an oversight and attach something invented.
- The convention this ADR has now stated twice is one rule: constant words in the message, varying
  values as fields, and no user content in either.

### Deferred by this addendum

The two the decisions name:
[R-328](../refinements/tasks/328-a-failed-turn-cannot-name-itself.md), a failed turn that can name
its session but not itself, and
[R-329](../refinements/tasks/329-a-failure-with-two-candidate-subjects.md), the two model-host
failures that wrap two calls and so name neither model.

## Narrowed-block addendum (2026-08-19): a failure names the model it was acting on

The addendum above left two lines carrying nothing and wrote down why: each wrapped two host calls
about two different models, so a `model` field would have named the wrong one about half the time,
and a wrong field is trusted where a missing one is not. This closes both of them the only way that
keeps the field honest, which is to make each block wrap calls about one model rather than to guess
better.

### Both blocks, decided per block rather than by symmetry

[R-329](../refinements/tasks/329-a-failure-with-two-candidate-subjects.md) asked whether both
blocks wanted the treatment or only one, on the ground that boot recovery already names its model
on the `ModelNotHostedError` arm while the swap back names nothing anywhere. Read against the code,
that asymmetry argues for narrowing both rather than for leaving one alone. `_clear_deep` catches
`ModelNotHostedError` itself, so that arm was already reachable only from `_settle_cortex` and its
`plan.cortex_model` was already right; it was right by a fact a reader has to go one function away
to confirm. The swap back has no such arm and exactly the same two subjects, so leaving it would
have kept the file the entry described as reading like naming a model was never considered. Neither
block is left as it stands.

### Decision 1: boot recovery clears and settles under two blocks

`converge_residency` wrapped `_clear_deep(host, plan.brain_model)` and `_settle_cortex(host, plan)`
in one `try`, whose `ModelHostError` arm said `the model host was unreachable during boot recovery`
and named nothing. It is now two blocks. The clearing's own arm says `the model host failed while
clearing the deep model at boot` with `model` set to the deep tier; the settling keeps the old
sentence and carries `plan.cortex_model`. Both still answer `False` and neither raises, so the
boot verdict and its amber dot are exactly what they were.

The second gain is the one that was not asked for. The 404 arm now wraps one call, so the cortex it
names is the model of the call it guards rather than a conclusion drawn from what another function
swallows, and a later edit to `_clear_deep` cannot quietly make it wrong.

### Decision 2: the swap back evicts and restarts under two blocks

`restore_standing` wrapped `_stop_what_was_swapped_in(host, model)`, `host.start(plan.cortex_model)`
and the gate in one `try` and logged `the model host failed while restoring the cortex`. The
eviction is now its own block, saying `the model host failed while taking the swapped-in model off
the card` with the handoff's own model on it. The start and the gate stay together, both being
about the cortex, and that block keeps the old sentence with `plan.cortex_model` attached. Both
arms answer the same `False` the retry policy reads, so the retry, the give-up and the
`ResidencyRestoreError` an operator is sent to the runbook with are untouched.

### Distrust green

Six mutations, each applied to production code alone with the whole brain workspace re-run
(2752 tests), so the counts are what actually reddened rather than what was expected to:

| Mutation | Reddens | Which |
| --- | --- | --- |
| boot clearing's field names the cortex | **2** | both boot cases that fail at the deep model |
| boot settling's field names the deep model | **1** | the cortex case added for this branch |
| boot recovery back to one `try` | **2** | the same two deep-model cases |
| swap back's eviction field names the cortex | **1** | the eviction case added for this branch |
| swap back's restore field names the swapped-in model | **1** | the retry case, which fails at the cortex |
| swap back to one `try` | **1** | the eviction case |

The third row is the interesting one. Collapsing boot recovery back into one `try` leaves the
cortex case green, because a cortex that fails last is the model the collapsed arm happens to
name; what reddens is the pair that fail at the deep model, which then read as the cortex having
gone. That is the fault this addendum exists to remove, so the pair is where it has to be caught,
and a suite that had only the new case would have let the collapse back in.

### Not verified live, deliberately

Every other decision in this ADR was checked against a running stack, and this one is not, because
there is nothing on a stack to check. Both blocks are pure policy in the core over the injected
`ModelHost` port, the change is which `try` a call sits in, and the fake and the real supervisor
adapter answer the same contract suite. A bring-up would re-run the same branch through a slower
host and prove the same thing the sweep above proves.

### Consequences

- **Five sentences an operator can grep where there were three**, and every one of them carries the
  model it is about. `docs/adr/ADR-0030-brain-handoff.md`'s boot table said an unreachable sidecar
  prints one particular line; it now says which of the two it prints and that both name a model.
- **The failure branches each file tests went up by one**, which is what the entry priced and why
  it was not folded into a logging sweep. Both files stay well under the line cap (276 and 226).
- **The residue is at the caller, not in these blocks.** `restore_standing` still answers a bool,
  so `restore_with_retries` cannot tell the two failures apart and its retry line names the cortex
  either way. That is filed rather than fixed, since it is a signature change.

### Deferred by this addendum

[R-330](../refinements/tasks/330-a-bool-loses-which-model-failed.md), the bool that loses which of
the two models a restore attempt failed on, and with it the question of whether the give-up error
should name the refused tier.

## Restore-verdict addendum (2026-08-20): the swap back answers which model it failed on

The addendum above narrowed the swap back's two failures into a block each, so the log line at the
site names the model it was acting on, and recorded that the residue sat one level up:
`restore_standing` still answered a bool, so `restore_with_retries` could not tell the two failures
apart and every sentence it wrote named the cortex whichever tier the host had actually refused.
This closes that, and answers the paired question the entry attached to it in the same sitting.

### Decision 1: an attempt answers the model it failed on, and nothing means success

`restore_standing` returns `str | None` rather than `bool`. `None` is the standing residency being
back; anything else is the id of the model this attempt failed on, which is the swapped-in resident
when the eviction refused and the cortex when its start refused or its gate never reported ready.

The inversion is the point rather than a cost. A bool has a value that means success, so a caller
that forgets which one reads the verdict backwards and still compiles; with `None` the only thing
that means success is the absence of an answer, and every other value carries a fact. The name at
the call site is `failed`, so the sentence there reads as what refused rather than as whether it
worked.

The entry priced this as "a signature change to a function three modules call". It is not:
`restore_standing` has exactly one production caller, `residency_restore.py`, and the other two
mentions the entry counted are prose in a test module and in the model host's shared contract
suite. The change is a return type, one call site and the two sentences below it.

### Decision 2: the give-up names the tier, in the field and in the exception's own text

The retry line keeps its message, `restoring the cortex failed; retrying`, because the entry's own
reading of it holds: the subject of that sentence is the operation, what is being retried is the
restore, and the restore is of the cortex. What was wrong was the field beside it. Both that line
and the give-up now carry two model fields, and they are two different facts: `model` stays what it
has always been here and everywhere the runbook reads it, the cortex being restored, while
`failed_model` is the tier this attempt failed on and may be the deep model the swap back could not
take off the card.

The paired question was whether `ResidencyRestoreError` should name the refused tier too, and the
answer is yes, more strongly than for the log line. That string is what an operator carries to
`docs/runbooks/model-swap.md`, it is read on a stream where no formatter runs, and
`could not restore 'cortex'` on its own sends a reader to a tier whose `start` never ran at all. It
now reads `could not restore 'cortex' after 2 attempts, the last of which failed on 'brain'; manual
recovery is needed`. The phrasing is "failed on" rather than "refused" because one of the three
paths is a cortex that never gated, where the host refused nothing and the model still did not come
up.

The runbook gains the paragraph that makes the second tier actionable: when `<tier>` is the deep
model, the cortex was never asked for, what is holding the card is the tier that would not stop,
and the recovery is the first half of its step 2 rather than the second.

### Distrust green

Six mutations, each applied to production code alone with the whole brain workspace re-run (2753
tests), so the counts are what actually reddened:

| Mutation | Reddens | Which |
| --- | --- | --- |
| the eviction answers the cortex | **2** | the eviction retry case, and the give-up that never evicts |
| the cortex's start answers the swapped-in model | **2** | the retry case, and the give-up that never starts |
| a stalled gate answers the swapped-in model | **1** | the gate case, the one path where nothing refused |
| the retry line's `failed_model` pinned to the cortex | **1** | the eviction retry case |
| the give-up line drops `failed_model` | **2** | both give-up cases |
| the give-up message drops the tier | **3** | all three give-ups |

The fourth row is the one worth reading. Only the eviction case can catch that mutation, because it
is the only test in the workspace where the two models differ; every other restore failure is the
cortex failing about the cortex, and a suite without that case would have let the field be pinned
to the wrong subject and stayed green. That is the same lesson the narrowed-block sweep recorded
one entry earlier, arriving at the caller this time.

### Not verified live, deliberately, and for the same reason as before

Both files are pure policy in the core over the injected `ModelHost` port, the change is a return
type and two sentences, and the fake and the real supervisor adapter answer the same contract
suite. A bring-up would drive the same three branches through a slower host.

### Consequences

- **`residency_moves.py` is at 285 lines and `residency_restore.py` at 135**, both under the cap.
- **The give-up's text changed**, so `docs/runbooks/model-swap.md` and the tier-scale host task
  that quotes it move with the code. The measurement records in
  `docs/adr/ADR-0030-brain-handoff.md` are left as they were written: they record what a run
  printed on a date, and rewriting them would make them say something no run ever printed.
- **A restore that gives up while the deep model is still on the card now says so.** That was
  always the truth of it, and nothing at any level could name it.

## Raised-and-logged addendum (2026-08-20): the trace that decides one site of six

The twice-printed-field sweep left six sites building one string, logging it, and raising it as a
typed error's text, so each of them prints its numbers once in the prose and once in the fields
beside them. The entry that recorded them named the alternative worth weighing first: leave the
`raise` alone and drop the **log** at all six, "since the exception is already logged wherever it
is finally caught", and said the question it turns on is whether every one of the six really is.

Traced against the code, it is not. The premise holds at exactly one of the six. That trace is the
substance of this addendum; the code change is small on purpose.

### The trace

| Site | What it raises | Where that is caught | Does the catch print the sentence? |
| --- | --- | --- | --- |
| `residency_moves`, a card that reports nothing | `SwapFailedError` | `swap_conductor`'s `_swap` | **no** |
| `residency_moves`, a card that is short | `SwapFailedError` | the same | **no** |
| `residency_watch`, a daemon that would not converge | `SwapFailedError` | the same | **no** |
| `residency_watch`, a worst stop the deadline no longer clears | `SwapFailedError` | the same | **no** |
| `swap_builders`, the deadline pairing the root refuses to serve on | `ControlDeadlineError` | **nowhere** | it never runs |
| `supervisor`, a child that survived SIGKILL | `SupervisorError` | the API, and the shutdown sweep | **yes, both** |

The four `SwapFailedError` sites share one catch, and that catch is deliberately silent: it settles
the handoff record as failed and answers `note_for(err)`, which is a mapping from an error type to
one of three fixed user-facing sentences and never reads `str(err)` at all. So the numbers on those
four lines exist in the log and nowhere else; dropping the log there would not move them, it would
delete them.

The composition root's refusal is worse still. `check_control_deadline` is called unguarded, and
the brain's entry point runs the wiring straight under `asyncio.run`, so `ControlDeadlineError` is
never caught by anything: what an operator would get instead of a structured line naming both
knobs is an interpreter traceback. Dropping that log downgrades a designed boot refusal into a
crash.

Only the supervisor's is a genuine double. Both callers of `stop` log what they catch: the control
API puts the whole sentence on its refusal line's `error` field, and the shutdown sweep logs the
exception with its traceback. The event was written twice at one end and once at each of two
others.

### Decision 1: one log call comes out, five stay

The supervisor raises the survived-SIGKILL sentence and no longer prints it. The five others keep
both, with the reason above written at the sites rather than left to be rediscovered: a value
appearing twice on one line is the smaller harm, and the larger one is a number that reaches
nobody.

### Decision 2: the surviving line owes the level, so it takes it

Dropping the supervisor's line would otherwise have cost the severity. The API's refusal line was
`WARNING` for everything, which is right for a caller asking after a tier this daemon never had and
wrong for a child holding GPU memory nothing can free, and with the `ERROR` line gone the two would
have read identically. The level now follows the status code, which is already this module's
judgement about whose fault a refusal is: 5xx at `ERROR`, 4xx at `WARNING`.

That is not a tidy-up. It is the path that made the drop safe to make at all: a swap's eviction
meets this same 503 through the brain's `ModelHost` port, the brain turns it into a user-facing
note without logging its text, and the sidecar's own line is therefore the only record of it
anywhere.

**Narrowed 2026-08-21.** The last clause is true of the swap in and of no other caller of those
routes. The unrostered preflight, the swap back, the peer restart, the peer sweep, the regain pass
and boot recovery all write the daemon's own sentence into the brain's log themselves, so the
sidecar's line is the only record on one caller of seven rather than everywhere. The level rule
this paragraph argues for is unaffected, and the survey behind the correction is in
[ADR-0030](ADR-0030-brain-handoff.md)'s refusal-reach addendum.

**Narrowed again 2026-08-22.** The one caller now writes it down too: a swap that fails settles
the reason onto its handoff record and logs it once beside that write, so the sidecar's line is a
second copy on all seven rather than the only record on any. The level rule is still unaffected,
and rests where the correction above put it, on what a 5xx means. The decision is
[ADR-0030](ADR-0030-brain-handoff.md)'s failed-reason addendum.

### Distrust green

Five mutations, each applied to production code alone with the whole brain workspace re-run:

| Mutation | Reddens | Which |
| --- | --- | --- |
| every refusal back to one `WARNING` | **1** | the 503 case |
| every refusal at `ERROR` | **3** | the 404 parameterization |
| the refusal drops its `error` field | **1** | the 503 case |
| the raise logs itself again | **2** | the supervisor case and the 503 case |
| the shutdown sweep stops logging what it caught | **1** | the stop-all case |

The last row is the one that keeps the argument honest rather than the code: it is the assertion
that the sentence really does reach an operator on the path the API never touches, which is the
half of the premise a test could otherwise leave unstated.

### Consequences

- **The written trace is most of what this bought**, and it is the reason the entry could not be
  closed by applying its own proposal. Five sixths of it was refuted by reading the catches.
- **`docs/modules/brain-model-manager.md` gains both halves**, the level rule on the API's table
  and the raised-not-logged note on the supervisor's.
- The `ERROR` line an operator greps for a wedged child is now the API's, not the supervisor's.
  Its message is the constant `a model-host request failed`, which is what the log-format sweep
  already made the greppable form of every refusal this daemon answers.

### Deferred by this addendum

The five that keep both spellings, carried forward with the narrower question that is left now
that dropping their logs is refuted:
[R-331](../refinements/tasks/331-five-raised-messages-keep-their-numbers-in-prose.md).

## Bounded-value addendum (2026-08-20): a field says how much of itself it spent

The rendered-fields work put the two per-line defences in the formatter, one for a field named for
a secret and one for a credential inside a URL, and left the third question beside them on purpose:
neither notices a field that is merely enormous. The entry recording that gap named the shape a fix
would take, a per-value character bound applied in `render_value`, and asked for two things this
addendum owes: a number measured against what `docker compose logs` really does rather than picked,
and a deliberate answer to the awkward half, since cutting a structure's JSON leaves text that no
longer parses.

### Re-derived from the tree first, and the entry's premise is false

The entry filed rather than fixed this on the reading that no field carries anything large today:
"every field the tree attaches is an id, a count, a flag, an endpoint or a short error detail".
`LoggingAuditSink` refutes it. It attaches `arguments`, the whole argument object of every tool
call, verbatim, and one shipped tool takes its arguments from the model: `spawn_subagents` carries
an `instruction` and a `context` per subtask, both written by the cortex, both bounded by nothing
but the model's own output cap. So the unbounded field is not a future adapter's mistake. It is on
the audit trail this repo already writes, and it is the one field on it whose size no call site
chose.

### The measurement, on the shipped image

Run against `cortex-brain` under the base compose stack, one record per line through the real
`configure_logging`, read back with `docker compose logs`. A container's log driver ends a message
at 16 KiB and starts another, so what the reader gets depends on which reading they take:

| rendered line | `docker compose logs` | `docker compose logs -t` |
| --- | --- | --- |
| 16,382 characters | one line | one entry, one timestamp |
| 16,383 characters | one line | one entry, one timestamp |
| 16,384 characters | one line | **two entries, a timestamp spliced into the value** |
| 16,385 characters | one line | two entries |
| a 65 KB line | one line of 65,573 | five entries |
| a 100 KB line | one line of 100,120 | seven entries |

So the cliff is exact and it is the newline that decides it: a rendered line of 16,383 characters
plus its terminator fills one 16 KiB message, and one character more is split. The plainest
reading hides this, because `docker compose logs` concatenates the pieces back, and a packed line
of 16,442 characters still parses as one JSON object after arriving in two. The two readings a
runbook actually sends an operator to are the ones that break. `-t` stamps every piece, so an
RFC3339 timestamp lands in the middle of the value. `--tail` counts entries rather than lines: over
a log whose last record was a 100 KB line, `--tail 3` returned **one fragment of 34,517 characters
of the value itself**, with no message, no fields and nothing naming what it belonged to.

### Decision 1: the bound is 2,048 rendered characters, and the number comes from the cliff

`VALUE_CHARS` is the measured 16 KiB message divided by eight, which leaves room for **seven**
fields at the bound rather than eight. (This paragraph first claimed eight, and that was
arithmetically false: eight come to 16,384 characters against a cliff of 16,383, one over before a
single `key=`, separator, marker or word of the message is counted. Corrected, with the
measurement, in the cut-defeats-withholding addendum below.) It
has to clear the widest value that ships, and that is the recall trail's own `dropped` list at the
shipped pool of twenty: 1,458 to 1,475 characters over 200 draws of `uuid4` ids and cosine scores.
A bound of 1,024 would have cut the trail this ADR built two addenda ago, which is the check that
turns a plausible power of two into the wrong one.

### Decision 2: the bound is spent on the rendered text, not on the value

The cut is the last thing done to a rendering rather than the first thing done to a value, because
escaping is what a line pays for: a string of quotes renders at twice its length, an emoji at six
times its own, so a bound on the input bounds nothing. Both of `render_value`'s ways out pass
through `_bound_value` on the way out, so the scalar branch and the compact-JSON branch cannot
drift to two different bounds.

### Decision 3: a cut structure stops parsing, and the marker sits outside the value's syntax

The entry framed the awkward half as a trade between cutting the rendered string, which costs
pasteability, and dropping whole elements with a count riding along the way `dropped_omitted` does.
The second is not available here, and the reason is structural rather than a matter of taste.
`dropped_omitted` works because `LoggingRecallSink` owns the whole line: the count is a sibling
field beside the list it describes. `render_value` renders a value it does not own, so a count
would have to go inside the caller's own structure, under a key the caller may already use. And the
shape most at risk is a long string, which has no elements to drop at all, so element dropping
would need the string bound anyway and the module would carry two rules where one will do.

So a cut rendering is left unterminated and `CUT` (`<cut 900 chars>`) says how much went. A
truncated line that no longer parses fails loudly at whatever reads it; a truncated list that still
parses is read as the whole of it, which is the quieter and worse failure. The marker cannot be
read as the field's own text, and that holds by the rendering's own grammar rather than by hoping:
a value printed bare carries no whitespace, by the very rule that lets it go unquoted, and the
marker carries two spaces, so a bare rendering can never contain one. A quoted or JSON rendering
that was cut has lost its closing quote or bracket, so the marker only ever follows text that has
already stopped mid-syntax, while a field whose own text spells `<cut 7 chars>` lands inside a
quote that closes. The suite asserts that shape directly rather than the sentence.

### Decision 4: the packed rendering keeps its values whole, and that asymmetry is recorded

Only the plain rendering passes through `render_value`. `PackedFormatter` hands the fields to
`json.dumps` as they were attached, so the bound does not reach it, and the secrets defence stays
the only rule both renderings share. That is not an oversight left unnamed: the whole value of a
rendering meant to be collected is that the object parses, and a bound inside it either corrupts
the object or lies about its shape, which is the same argument as above running the other way. The
exposure is real, since a collector reading entries meets the same 16 KiB split, and it is carried
as its own entry rather than settled here.

### Distrust green

Six mutations, each applied to `log_fields.py` alone with the suite re-run:

| Mutation | Reddens | Which |
| --- | --- | --- |
| the scalar way out stops passing the bound | **5** | including the whole-line and rendered-text cases |
| the compact-JSON way out stops passing the bound | **5** | the same five, since both ways out feed them |
| the bound becomes exclusive | **1** | the value exactly at the bound |
| the cut lands on the value rather than on its rendering | **4** | led by the escaped-quotes case |
| the marker stops naming how many characters went | **2** | both counting cases |
| the marker loses its whitespace | **2** | the case that tells a cut marker from a field spelling one |

### Verified live

The same two records, one carrying a 100,000-character reply and one carrying a
`spawn_subagents`-shaped `arguments` object, through the real image under `docker compose`, before
and after:

| | rendered line | entries under `-t` | what `--tail 3` returns |
| --- | --- | --- | --- |
| before | 100,120 and 100,060 characters | seven each | one 34,517-character fragment of the value |
| after | 2,161 and 2,119 characters | one each | the three lines that were logged |

Both bounded lines end in the marker naming what went, `<cut 97970 chars>` on the audit line and
`<cut 97952 chars>` on the other, and both still carry every field that follows the cut one, since
the fields print in name order and the bound is per value rather than per line.

### Consequences

- **A line stays one entry, so `--tail` and `-t` stay usable.** That is the whole point: those two
  readings are what the runbooks send an operator to, and they were the two the split broke.
- **`docs/modules/brain-core.md` gains the bound**, the marker, and the packed asymmetry.
- A deployment that wants the whole value has the same answer it always had for a secret: the
  record is not the store. An id in the trail pairs with the thing itself.

### Deferred by this addendum

- The packed rendering's own volume question, which cannot be answered by this bound:
  [R-336](../refinements/tasks/336-packed-values-keep-their-whole-length.md).
- The line, as opposed to the value, is still unbounded, and the eight-fields headroom is an
  argument rather than a check: [R-337](../refinements/tasks/337-a-bounded-value-leaves-the-line-unbounded.md).

## Named-recall addendum (2026-08-20): the rank that fell back says which conversation it was for

**Status:** Accepted. Closes "a rank fallback cannot name its turn" from
[docs/refinements/index.md#memory](../refinements/index.md#memory), which the unjudged-rank
addendum above opened as the one thing its two new warnings could not say.

The addendum above gave `JudgeRecallPolicy` its two fallback warnings and found, in writing them,
that neither could name where it happened. `RecallPolicy` was `candidate_k(k)` plus `select(hits,
*, query, now, k)`, and no conversation identity crossed it. Everything beside those two lines
names one: `SummarizingHistoryWindow` logs a session with its boundary, `_report_forgone_memory`
logs a session and a turn, and `LoggingRecallSink` writes a session on the very trail line an
operator would pair a fallback with. So a burst of fallbacks on a brain serving several
conversations could not be attributed to any of them, which is the blindness the warnings existed
to end, one level up.

### Decision

1. **The port grows an optional keyword-only `session_id`, and nothing else.** `select(hits, *,
   query, now, k, session_id=None)`. This is the shape `HistoryWindow.select` took for `progress`
   and `drain_text` took for `stops`: a collaborator only some implementations have a use for,
   handed per call rather than per construction, defaulted so a caller that has none passes none. A
   required positional would have been a field four of the five policies ignore, forced on every
   caller and every fake for one policy's benefit.
2. **It is an id and never content.** The pool and the `query` are the two other things a policy is
   handed and both are conversation text, which no line of these logs has ever carried and none may
   start carrying on the one path that fires when something is already wrong. That is why this is a
   separate parameter rather than a wider `query`, and it is pinned by a test that renders both
   warnings through the shipped formatter and asserts the question and the recalled note are on
   neither line.
3. **`MemoryRecaller.recall` already held one, so nothing is plumbed.** The method is called with
   the session it is recalling for and hands that on. No store read, no new field on any value
   type, no seam change.
4. **The field is spelled `session`, matching the trail rather than the core's other lines.** Five
   log sites in the brain spell a conversation `session_id` and the recall trail spells it
   `session`; a fallback is paired with the trail line for the same recall, sitting beside it in
   the same stream, so it takes the trail's spelling. The divergence itself is real and is filed
   rather than settled here.
5. **Every fallback is handed the id too.** All three exits that consult one forward it, including
   the empty pool that is no fault, because `fallback` takes any `RecallPolicy` and a judge nested
   under a judge would otherwise be blinded by the policy wrapping it.
6. **A caller that named nothing logs `session=None`.** An absent field and an unnamed caller are
   different facts, and the formatter's own rule for a withheld value is the same one: the key
   stays so a reader can tell the two apart.

**This reverses the unjudged-rank addendum's "the judge's warnings cannot name a session or a
turn".** Half of it: they now name a session, and the turn stays out of reach, because
`MemoryRecaller.recall` takes no turn id either and reaching one means widening that method as
well, for a pairing target that has no turn id of its own.

### What this does not do, and where that is recorded

- **A fallback still cannot be tied to one recall inside a conversation.** A session with twenty
  turns produces twenty recalls, and the trail line beside a fallback names the same session as the
  nineteen others. Recorded as
  [docs/refinements/tasks/338-a-named-recall-is-not-a-named-turn.md](../refinements/tasks/338-a-named-recall-is-not-a-named-turn.md).
- **The brain's logs now spell a conversation two ways**, `session` on the recall trail and these
  two warnings, `session_id` on the five other sites, so an operator grepping one misses the other.
  Recorded as
  [docs/refinements/tasks/339-two-spellings-of-one-conversation.md](../refinements/tasks/339-two-spellings-of-one-conversation.md).
- **Nothing about the rank's cost or behaviour changes.** No call is added, no ranking moves, and
  the four policies that ignore the parameter delete it in their first statement.

### Distrust green

Seven mutations, each applied to production code alone with the core suite re-run.

| mutation | reddens |
| --- | --- |
| `MemoryRecaller.recall` stops passing the id | **1**, the recaller's own case |
| the unreachable-model line stops naming the session | **3**, the naming, unnamed and no-content cases |
| the unreadable-reply line stops naming the session | **2**, the naming and no-content cases |
| the question rides either line beside the id | **1**, the no-content case, which is the point of it |
| the fallback after an empty pool is not told the id | **1** |
| the fallback after an unreachable model is not told the id | **1** |
| the fallback after an unreadable reply is not told the id | **1** |

The fourth row is the one worth stating: it is the leak this parameter exists to avoid being, and
nothing about the port's shape prevents a later call site from writing it, so the refusal is a test
rather than a type.

## Named-turn addendum (2026-08-20): a turn is named by whoever schedules it

The line-fields sweep gave the three mid-turn failures in `converse_stream` a `session_id` and
recorded honestly that this was the whole of what that handler held: the `turn_id` was minted
inside `TurnEngine` and left it only on the `TurnCompleted` a failed turn never emits. The entry
that recorded it declined to pick between two ways of closing that, and picking is the substance
here.

### The cost, restated from the reading rather than from the code

A session that failed three turns prints three lines under one `session_id`, and on a brain
serving one user that field never varies, so the three lines are indistinguishable. Nothing on
them says whether that is one repeating fault or three unrelated ones, and nothing ties any of
them to the tool-invocation lines the same turn wrote. It is exactly the reading the fields were
printed to end.

### Re-derived first, because two things had moved

The cortex-cut arm added since then logs a warning **from inside the engine** carrying
`session_id`, `turn_id` and `capped`. That is not a counter-example, and it is the clearest
statement of the problem: the engine can name a turn on every path it survives, and the only
paths it cannot name are the ones where it does not survive, which are precisely the three the
stream reports. An id whose sole holder is the code that dies with the turn is unreachable
exactly when it is needed.

Reading the escalating wrapper turned up the same defect one level in, which the entry did not
mention. `EscalatingTurnEngine` could not name its own turn either: it accumulated the inner
runner's events, waited for the inner `TurnCompleted`, and read `completed.turn_id` off it to
claim the handoff and to emit the real completion. So the identity of an escalating turn was
derived from an event, and a torn-down inner turn left the wrapper with nothing.

### Decision 1: the stream mints the turn id and hands it to `handle_turn`

`TurnRunner.handle_turn(session_id, text, *, turn_id)`. `TurnEngine` loses `turn_id_factory`
entirely and answers under the id it was given; `EscalatingTurnEngine` holds the id from its
first statement and uses it for both the handoff claim and the completion; `ConverseStream` mints
one per turn through an injectable `TurnIdFactory` defaulting to the core's new `new_turn_id`.

The argument is not that this is tidier. **Identity belongs to whoever can observe the whole of
the thing.** The stream accepts the `UserTurn`, queues it, starts it, cancels it, reports its
completion and reports its failure. A runner sees only the middle of a *successful* turn. An id
born in the runner is therefore born too late and dies too early, and the failure path is not an
edge case of that arrangement, it is the whole of what the arrangement excludes.

Two consequences follow that are worth stating as facts rather than as tidiness. The turn id is
now single-sourced: `TurnCompleted.turn_id` is an echo of what the caller already knew, so the
line an operator reads and the id the client is told agree by construction rather than by both
calling the same factory. And what a turn id *looks like* stayed in the core (`new_turn_id`,
beside the `Message.turn_id` it fills) while **when** one is minted moved out, which is the split
the port's docstring now carries.

### Why not the cheaper shape

The alternative was for the engine to surface the id early, as a first event or a started-turn
record in the session store, keeping the port's shape. Three things are wrong with it, in
ascending order of seriousness.

It adds a domain event with no wire counterpart. Every `TurnEvent` today maps onto exactly one
`ServerEvent` through `to_server_event`, whose last branch is an unguarded
`return ServerEvent(turn_complete=TurnComplete(turn_id=event.turn_id))`. A second event carrying
a `turn_id` narrows to that same branch and **typechecks**, so a started event that ever reached
the mapper would be sent to the client as a completion. The fence would have to be a filter in
the stream, and nothing about the types would hold it there.

It makes the id optional in the one place optionality is invisible. The stream would hold
`turn_id: str | None`, `None` until the event arrived, and every implementation of the port would
have to remember to emit it. A runner that forgot would leave the field missing on the failure
lines and nowhere else, which is the one path nobody exercises by hand.

And it does not fix the wrapper. `EscalatingTurnEngine` would still be reading its own turn's
identity out of its inner runner's event stream.

### What the larger shape actually cost, measured

86 `handle_turn` call sites and 61 `turn_id_factory` keyword arguments across six test files. The
churn is mechanical and the tests came out better: `handle_turn("s", "hello", turn_id="t-1")`
says which turn is running at the place the turn runs, where
`TurnEngine(..., turn_id_factory=lambda: "t-1")` said it once per engine and left the call sites
mute. The three orchestrator suites that pinned ids now pin them where they are minted, through
`converse(..., turn_id_factory=...)`, which is the same fact in the right place.

### Decision 2: minted when the turn starts, not when it is queued

`ConverseStream` names the turn in `_turn_task`, not in `_enqueue_turn`. A `UserTurn` that
arrives mid-turn waits in `_pending`, and a `Cancel` drops the queue outright; a turn dropped
there never ran, never persisted a user message, and has nothing to be named for. The id is
therefore a fact about a turn that happened, which is what makes its absence from a log
meaningful rather than ambiguous.

### Decision 3: the paired question is answered yes, and it is its own change

The entry was right that neither shape should be picked without asking whether the turn id
belongs on the tool-audit lines, since half the value here is joining them. Traced: it does not
today. `LoggingAuditSink` prints `tool`, `ok`, `arguments`, `trust`, `at` and either
`result_chars` or `error`, and `ToolInvocation` carries no conversation identity at all, neither
turn nor session. So the join this addendum buys is between the three failure lines and the
history the store grouped, and **not** yet between a failure and the tool calls that preceded it.

The answer is yes, and the shape is cheap: `TurnStamp` already carries `session_id` and is the
value built per dispatch from the `ToolLoopContext`, which holds `turn_id`; it was designed to
take a field without touching call sites. What makes it a separate change rather than a second
half of this one is the decision it forces and this one does not: the audit trail records the
dispatches of subagent runs and of the schedule ticker as well as of conversation turns, and
neither of those is a turn. Naming that field is a naming decision about the trail, taken with
the trail's own tests, and it is filed as
[R-342](../refinements/tasks/342-the-audit-trail-cannot-name-the-turn.md).

### What did not change, deliberately

The user's turn text is still attached to no log line and must not be. The formatter prints
fields nobody enumerated and withholds by field *name*, which cannot recognize a conversation, so
the standing rule is a rule about call sites. The three cases that assert its absence assert it
against the rendered line with the traceback included, and they were re-run against the new
fields rather than left alone.

### Distrust green

Five mutations, each applied to production code alone with the core and orchestrator suites
re-run, then restored:

| Mutation | Reddens |
| --- | --- |
| the failure lines mint a fresh id instead of reporting the turn's | 5 |
| the failure lines drop the `turn_id` field | 5 |
| the user's own text is attached beside it | 3 |
| the engine names its own turn again, ignoring the id it was handed | 27 |
| the escalating wrapper completes under whatever id its inner runner claimed | 1 |

The first row is the one that keeps the field honest rather than merely present: a line carrying
an id that names no turn would satisfy every assertion that only checks the field exists. It is
caught by asserting the logged id against the `turn_id` the store grouped the dead turn's user
message under, which is the join an operator actually makes.

### Consequences

- Three failures in one session are three lines an operator can tell apart, and each joins to
  the history rows the turn wrote.
- `TurnEngine` no longer has a `turn_id_factory`, so there is exactly one place a turn is named.
- `EscalatingTurnEngine` no longer derives its own turn's identity from an event.
- `docs/modules/brain-core.md` and `docs/modules/brain-orchestrator.md` both carry the split
  between what a turn id looks like and when one is minted.

### Deferred by this addendum

The other half of the join, the tool-audit lines:
[R-342](../refinements/tasks/342-the-audit-trail-cannot-name-the-turn.md).

**2026-08-21:** landed, and the decision it forced was taken where the trail lives, in the
[ADR-0009](ADR-0009-tools-mcp.md) named-work addendum: a field per kind rather than one field for
the unit of work, so the line carries `session_id`, `turn_id` and `task_id` and a delegated call
names both its task and the turn that spawned it. Decision 3 above traced correctly that
`ToolInvocation` carried no conversation identity; what it read too cheaply is that the stamp
carried no turn id either, the turn id living on the loop context that builds the stamp. So the
join cost a field on `TurnStamp` and an attribution on the stored `SubagentTask` before it cost
anything on the audit line.

## Cut-defeats-withholding addendum (2026-08-20): the order of the two is the defence

The bounded-value addendum above added a third rule to a formatter that already had two, and put
it in the wrong place with respect to one of them. An independent audit of that change found the
result: on the shipped `plain` rendering, the bound defeats the URL withholding for any field the
bound cuts. The reproduction is one line of the live audit trail.

### The defect

`_USERINFO` is `(?<=://)[^/\s@]*@`, and the `@` is not incidental to it. The pattern *ends* on the
character that closes a URL's userinfo, which is what lets it leave a bare email address and a
credential-free URL alone. `redact_urls` was spent once, over the whole formatted line, in
`PlainFormatter.format`, which runs after `formatMessage` has already rendered and cut every
field. So a cut landing anywhere between a URL's `://` and its `@` deletes the one character the
pattern is anchored on, and the pass that follows finds nothing to match:

```
$ python -c "..."   # a field of {'a': 'x'*(VALUE_CHARS-30) + 'postgres://admin:hunter2@db/x'}
INFO:cortex.tools.audit:tool.invocation arguments={"a":"xxx...xpostgres://admin:hunter2<cut 7 chars>
```

The credential prints in full, in a terminal, on the default rendering. The carrier is not
hypothetical and it is the same one that motivated the bound: `LoggingAuditSink` attaches every
tool call's `arguments` verbatim, and `spawn_subagents` takes its `instruction` and `context` from
the model, so a field of arbitrary size and arbitrary content is on a trail this repo writes today.
A connection URL reaching such a field is exactly the shape the withholding exists for.

`PackedFormatter` is unaffected, having no cut to defeat the pattern with. The exposure is the
default rendering's alone, which is the one an operator reads.

### Decision 1: a rendering is withheld before it is cut, and the whole-line pass stays

`_bound_value` now takes a rendering, withholds every URL credential in it, and cuts what is left.
Both of `render_value`'s ways out already passed through that one function, so both inherit the
order and neither branch has an ordering of its own to drift from the other.

The whole-line pass in `PlainFormatter.format` is kept, and keeping it is not belt and braces. It
covers what `render_value` never sees: the message text and a traceback, which is where
`redis://:pw@redis:6379` arrives at least as often as in a field. The two passes overlap on a
field's value, and the overlap is free because the substitution is idempotent: `://<redacted>@`
re-matches and re-substitutes to itself.

Withholding first also makes the marker's count honest. The bound is spent on what will actually
print rather than partly on a credential that will not, so `<cut 13 chars>` names 13 characters the
reader could have seen.

### Decision 2: the other defence was checked and needs no such ordering

The addendum above named both defences and then tested the bound against neither, which is how the
interaction was missed. So the name rule was re-derived rather than assumed safe. It is immune,
and immune structurally rather than by luck: `record_fields` replaces a secret-named field's value
with `REDACTED` *before* anything renders it, and what the bound then meets is a ten-character
constant it can never reach inside. A cut cannot shorten `<redacted>` into something that leaks,
because there is nothing left of the value to leak.

The arrangement that would break it is the mirror of the defect just fixed, a bound spent on the
way to the substitution rather than after it, so the suite now pins the order with a 100,000
character `api_key` that renders as `api_key=<redacted>` and nothing else.

### Decision 3: a rendering the bound will cut is quoted rather than left bare

The same audit found a second, quieter fault in the same function, latent today because no bare
value in the tree exceeds the bound. `_BARE` exists so that an unquoted value carries no
whitespace and cannot be read into the pair beside it. The marker carries two spaces. Appending it
to a bare rendering therefore writes a field boundary inside a field:

```
endpoint=http://aaa...aaa<cut 9 chars> next=1
```

which reads as a plausible whole endpoint followed by two stray tokens. `render_value`'s own
docstring promised the opposite ("written so the pair it sits in can still be told from the next
one"), and a test docstring asserted the opposite of what its own assertion showed.

Two fixes were available. A marker with no whitespace, `<cut:9:chars>`, was rejected: the
whitespace is precisely what makes the marker unspellable by a bare value, so removing it trades a
separation fault for an attribution one, and it would change every rendering to repair one.

What landed instead: bare is the reward a value earns for printing whole, and a rendering the
bound will cut has not earned it, so it is quoted. This makes one rule of what were two. **Every
cut rendering now ends mid-syntax**, its closing quote or bracket among the characters that did
not print, which is what a cut structure already did and what the addendum above argued for on the
grounds that a truncated line failing loudly beats a truncated one read as whole. The marker's
attribution follows from the same single rule rather than from two arguments that met at a shape
neither covered: it only ever follows a rendering that stopped, while a field whose own text
spells it carries the marker's whitespace and so lands inside a quote that closes.

The visible cost is that a cut field now spends two more characters on its quotes and says so in
its count.

### Decision 4: the bound is spent on the withheld rendering, which can be the longer one

`REDACTED` is ten characters and a userinfo can be shorter, so withholding can *lengthen* a
rendering: `http://a@h` becomes `http://<redacted>@h`, nine characters more. The length that
decides whether a rendering prints as it stands is therefore the withheld one, or a value sitting
at the bound would cross it on the way to the line. Pinned by a case that grows from exactly
`VALUE_CHARS` to `VALUE_CHARS + 9` and is cut accordingly.

### Correction: seven fields at the bound, not eight

Decision 1 of the addendum above justified `VALUE_CHARS` with a claim that is arithmetically
false, and it is corrected in place there and here. Eight fields at the bound come to
8 x 2,048 = 16,384 characters against a measured cliff of 16,383: one over, before a single
`key=` prefix, separator, `<cut N chars>` marker, word of the message or `INFO:logger:` prefix is
counted. Measured through the shipped `PlainFormatter`, with six-character keys and a cut on every
field:

| fields at the bound | rendered line | against the 16,383 cliff |
| --- | --- | --- |
| 5 | 10,394 | under by 5,989 |
| 6 | 12,465 | under by 3,918 |
| 7 | **14,536** | **under by 1,847** |
| 8 | 16,607 | over by 224 |
| 9 | 18,678 | over by 2,295 |

So the headroom is seven, and the bound itself is unchanged: nothing measured argues for moving
it, the division by eight still lands on the power of two that clears the widest value the tree
attaches, and moving a bound to rescue a sentence would be the wrong repair. What is withdrawn is
the sentence. That seven is enough remains an argument rather than a check, because nothing
measures the widest line the tree can build, which is the open entry on the line as opposed to the
value and not this constant's to answer.

### Distrust green

The audit's reproduction was re-run against the shipped code first, and the security case was
written before the fix and confirmed red on it, failing on `'hunter2' is contained here:
://cortex:hunter2<cut 17 chars>`. Six cases redden in total on the unfixed source. Five mutations
were then applied to `log_fields.py` alone, each read back from disk before the suite was trusted:

| Mutation | Reddens | Which |
| --- | --- | --- |
| the bound stops withholding before it cuts | **1** | the credential the cut falls across |
| the withholding runs after the cut instead of before it | **1** | the same one, which is the point: the order is the defence, not the call |
| a rendering the bound will cut stays bare | **6** | every cutting case |
| the bare decision is made on the value as attached | **1** | the value that grows under withholding |
| the way out reverts to what shipped | **6** | every cutting case |

The second row is the one worth keeping. A mutation that merely deletes the call proves the call
is reachable; a mutation that keeps the call and moves it after the cut proves the ordering is
what the suite holds.

### Consequences

- **A credential in a field survives no cut.** The default rendering is the one an operator reads,
  and it was the only one exposed.
- **One rule where there were two.** A cut rendering ends mid-syntax whatever it renders from, so
  the marker's attribution has a single argument behind it.
- `docs/modules/brain-core.md` carries the ordering, the quoting and the corrected headroom.
- A field cut at the bound is two characters shorter in content than before, spending them on the
  quotes that make it legible, and its count says so.

### Deferred by this addendum

- A userinfo the pattern cannot reach at all, which predates the bound and is untouched by it:
  [R-343](../refinements/tasks/343-a-userinfo-the-pattern-cannot-reach.md).

## Close-out-review addendum (2026-08-20): two claims these changes left wider than the tree

A close-out review of the run this record documents found two sentences that outrun what the code
supports. Neither is a fault in behaviour, and both are the kind that get cited rather than
re-derived, so both are filed rather than left in the reading of whoever hits them next.

**A refusal that is not the only record of itself.** The change that stopped the model host daemon
logging a wedged child's sentence twice put the level on the line that survives, and argued for it
with reach: a swap's eviction meets the 503 through the brain's own port, the brain makes a note of
it without logging its text, so the daemon's line is the only record of it anywhere. True of that
path. False of the swap back, where `restore_standing` logs both of its failures with
`_logger.exception` and the `ModelHostError` in the traceback was built out of the daemon's own
response body, so the daemon's sentence reaches the brain's log intact. The level stays right and
the argument stays too wide, filed as
[R-345](../refinements/tasks/345-a-refusal-that-is-not-the-only-record.md).

**A turn nobody escalated is still completed under a foreign id.** The change that moved the turn id
out of the engine fixed `EscalatingTurnEngine` one level in, so an escalated turn completes under
the id the wrapper was asked to serve. Its other exit was left alone: when the cortex asked for
nothing, the inner runner's own completion object is yielded through unchanged, so the id the client
reads there is whatever the inner runner put on it. The two agree today because the wrapper passes
the id down and the one engine behind the factory echoes it, which makes this an invariant resting
on an agreement between two files, in the arm that runs on every turn that is not escalated. The
case added with that change covers the escalating arm only. Filed as
[R-347](../refinements/tasks/347-a-transparent-turn-keeps-the-inner-id.md).
