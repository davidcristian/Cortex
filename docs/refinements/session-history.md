# Session history & context

Deferred refinements from Slice 3's cortex chat and session work; the windowing decision and the summarization alternatives it weighs live in [ADR-0014](../adr/ADR-0014-history-windowing.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** the recap measurement resting on one corpus, the recap pass being unbounded and unthrottled, a fenced recap's usefulness being unmeasured.

**Cortex chat / session in Slice 3:**
- **Session-history windowing landed 2026-07-03 ([ADR-0014](../adr/ADR-0014-history-windowing.md)).**
  A pure `HistoryWindow` seam in `TurnCapabilities` with a turn-aligned char-budget tail
  (`CharBudgetHistoryWindow`; `CORTEX_HISTORY_CHAR_BUDGET`, default 48000 ≈ 12K of the
  16K-token context, `0` disables). What one turn sends to the model is bounded, persistence
  untouched. Remaining from the original deferral:
- **Session-history summarization.** Compressing old turns instead of dropping them changes
  content (a lossy model pass) and needs inference in turn assembly, so it stays deferred
  (ADR-0014 alternatives). Distinct from memory summarization (Slice 5, cross-session recall,
  not the in-context history). **Cost correction:** this is *not* a drop-in behind the
  `HistoryWindow` seam. `HistoryWindow.select(history) -> Sequence[Message]` is **sync**, so a
  window that calls the model cannot satisfy it; the port has to become async first, which
  moves every implementer and call site. Two further costs are real and unresolved: whether a
  summary is cached on the session or recomputed per turn, and that `backend.py` holds the GPU
  lease for a generator's lifetime under a non-reentrant lock, so a summarizer stream abandoned
  mid-turn deadlocks the turn that spawned it.
- **Session-history summarization, audited 2026-07-16 and kept deferred with the blocker
  sharpened ([ADR-0014 summarization-audit addendum](../adr/ADR-0014-history-windowing.md)).** The
  audit priced the async port change and re-derived the lease hazard from the lock code; both are
  milder than the entry above reads, but a third cost binds, so it stays deferred. **The async
  widening is clean and contained, not a call-chain migration.** `HistoryWindow.select` has one
  production caller, `_inference_messages` (`engine.py`), already an `async` method, so widening
  `select` to `async` adds one `await` and cascades no colour upward; the only implementer is
  `CharBudgetHistoryWindow`. An `async def select` with a synchronous body is gate-clean here (the
  `unused-async` lint, `RUF029`, is preview-only and this repo runs ruff without preview), so every
  heuristic selector wraps its body unchanged. **The lease hazard is navigable, not structural.**
  `SingleResidentModelManager` guards a non-reentrant `asyncio.Lock` (`model.py`) held for the whole
  stream generator's lifetime (`backend.py`), but selection runs in `_inference_messages`, which
  `handle_turn` awaits to completion **before** it opens the reply stream (`stream_tool_loop`), so at
  selection time the turn does not yet hold the lease. A summarizer that fully drains its own model
  call is a sequential acquire, exactly the discipline the title generator already uses
  (`generate_title`, run at turn end). Verified against the real manager: a drained acquire then a
  second acquire succeeds, while a summarizer stream held open across the reply's acquire deadlocks.
  So the hazard is the abandoned-stream case this entry named, a discipline requirement on the future
  selector, not the reply already holding the lease. **What stays deferred is the model pass
  itself, and its stated blocker was wrong (corrected 2026-07-19).** This read "a summarizing window
  cannot be behavior-validated on the 8 GB dev GPU, where the cortex tier (gemma-12B) does not fit".
  The cortex does fit that card: [ADR-0029](../adr/ADR-0029-vision-screen-capture.md) ran it there
  beside its vision projector at `-ngl 99 --ctx-size 4096 --parallel 1`, and
  [ADR-0030](../adr/ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
  8188 MiB. Judging whether a summary keeps what the next turn needs is not a 16K question. What is unresolved
  is the design: the cache-versus-recompute-per-turn decision this entry named is a choice, not a
  wrapper. So the honest slice still lands the async widening together with the summarizer rather
  than the widening alone as an empty async layer, and what it waits on is that decision plus the
  shared `select` widening, not the 24 GB card.
- **Bounded backpressure on the `Converse` output queue landed 2026-07-03.** The per-turn
  output queue (`converse.py`) is now credit-bounded (`CORTEX_SEAM_CONVERSE_BUFFER`, default
  256): a consumer that stops reading suspends generation at the bound, while the terminal
  `SeamError` and teardown bypass the credits so failure never blocks behind a full buffer.
  The `Converse` stream contract is unchanged; design in
  [brain-orchestrator.md](../modules/brain-orchestrator.md).
- **Session-history summarization's two open design questions closed 2026-08-06
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md)); the summarizer itself stays deferred, now on
  nothing but implementation.** The audit above kept this deferred on "the cache-versus-recompute
  decision plus the shared `select` widening", and both are now answered. **Cache, not recompute,
  and the reason is that history is append-only.** A summary lives in Redis behind `SessionStore`,
  beside the messages and the title it derives from, never in `MemoryStore` (a summary is one
  conversation's working context, and pgvector would make it recallable into other conversations,
  which is a different feature). It is keyed by the boundary it covers, and because `SessionStore`
  has `append`, `history`, `set_title` and a whole-session delete and **no verb that edits or
  removes a message**, a summary of a prefix can never become wrong, only incomplete: each new
  summary folds the previous one together with the newly dropped turns, a deleted session takes its
  summary with it, and there is no invalidation path to get wrong. Recompute was priced against
  that: one full cortex generation on *every* turn, serialized ahead of the reply and therefore
  straight onto time-to-first-token, against once per boundary move. It survives a model swap by
  construction, being text in the store rather than anything in a KV cache. **The lease sequencing
  is settled too**, as `drain_text` (`drain.py`), which leaves the adapter's acquire block in a
  `finally`; `generate_title` was moved onto it in the same change, so the discipline is one helper
  rather than a habit. **One claim of this entry did not hold:** it names the window's caller as
  `_inference_messages` in `engine.py`, a method that no longer exists (the caller is
  `assemble_inference_messages` in `turn_context.py`, still `async`, so the substance held).
  What is left is implementation with no design in it: the `SessionStore` summary verbs (port,
  fake, Redis adapter, contract test), a `SummarizingHistoryWindow`, the `async` widening of
  `HistoryWindow.select` **alongside** it rather than as an empty async layer, and the config knob.
  Deliberately not taken in that change: `RecallPolicy.select` widened because it had three waiting
  consumers, and `HistoryWindow.select` has exactly one, so it waits for that one.
- **Session-history summarization landed 2026-08-06
  ([ADR-0038 summarizing-window addendum](../adr/ADR-0038-ranked-recall.md)), closing this area.**
  The design settled hours earlier held on every point that was re-checked against the tree:
  `SessionStore` still has no verb that edits or removes a message, so a recap of a prefix can
  only go incomplete and never wrong; the window's caller is still `assemble_inference_messages`,
  awaited to completion before the reply's generator is built; and `drain_text` still leaves the
  adapter's acquire block in a `finally`. What shipped is the `SessionStore` recap verbs
  (`set_recap`/`recap`, a `HistoryRecap(text, covers)` behind the port, in the fake, in the Redis
  adapter, under the same shared contract suite, and removed by the whole-session delete in the
  same transaction), a `SummarizingHistoryWindow` in the core, the `async` widening of
  `HistoryWindow.select` alongside it, and `CORTEX_HISTORY_SUMMARY`, **default off**. Four things
  the design did not say: `select` needed the `session_id` as well as the `async`, the same shape
  of miss as the recall port's `query`; the value is a `Recap` rather than a `Summary`, because
  `SessionSummary` already means a chat-list row; the port pair belongs to `SessionStore` for a
  reason stronger than proximity, since a recap is as private as the transcript and "forget this
  chat" must take it in the same write; and the fallback is structural rather than a policy, the
  window being able only to PREPEND to the shipped window's selection, so losing a word the user
  wrote is not reachable from any state of the summarizer. The lease test had to be fixed before
  it meant anything: asserting the reply's acquire succeeds did not redden when the drain was
  removed, because generator finalization tidied the abandoned stream first; it now asserts the
  acquire block was left with no `await` in between, which the collector cannot rescue.
  Measured against the window it wraps, on the real cortex through the gpu stack: over a
  23-message conversation whose opening facts had dropped out, the shipped window sent 295
  characters and could not answer "remind me of my booking reference" at all, while the recap
  sent 831 and answered it correctly, at 11.0 s for the pass that moved the boundary and 0.000 s
  for every turn after it. Time to first token did not get worse. The default stays off anyway,
  because 11 s lands on the turn that triggers it, and because the corpus is one hand-built case.
  Remaining from this deferral:
- **The measurement is one corpus.** It shows the mechanism works and is not a benchmark: a single
  hand-built conversation, by the author of the feature, with the needed fact placed where a
  summary would keep it. What it does not measure is a real long chat's fold quality after several
  boundary moves, or the cost on a cortex under load. **Trigger:** any move of the default, which
  wants more than one conversation behind it.
- **The recap pass is unbounded and unthrottled.** Every boundary move spends a full cortex
  generation over the newly dropped turns, serialized ahead of the reply, and the fold's prompt
  is whatever those turns say. Two knobs were consciously not built: a minimum number of newly
  dropped messages before a fold is worth paying for, and a token cap on the recap request (the
  reply is bounded at `RECAP_MAX` characters after the fact, not before). **Trigger:** the
  measurement above showing the fold cost landing on enough turns to be felt.
- **A recap of tainted turns landed fenced at both ends 2026-08-06 ([ADR-0038 untrusted-recap
  addendum](../adr/ADR-0038-ranked-recall.md)).** Read against the shipped write path, the entry's
  own premise was wrong and the real exposure is a different shape. **An untrusted tool result is
  never in the prefix a recap reads.** `TurnEngine.handle_turn` appends exactly two messages per
  turn, the raw `Role.USER` text and the guardrail-scrubbed `Role.ASSISTANT` reply (`engine.py`);
  the in-turn `Role.TOOL` message that carried the payload is turn-local and dies with the turn,
  the same finding the tainted-summarization decline made on the record path
  ([untrusted-content.md](untrusted-content.md)). Nor is there a taint bit to key a refusal on: a
  stored `Message` carries role, text, timestamp and turn id, taint is a turn-local ledger
  reconstructed each turn, and `SessionStore` has no verb that would report it. **What is
  reachable is the assistant's own quotation.** The security preamble expressly permits quoting
  untrusted content ("You may quote or summarize"), so a reply to "summarize this email" can carry
  the injection verbatim into persisted history, and from there into the recap. The recap then did
  two things the plain window does not: it fed that text to a model under an instruction to
  process it, which is the summarizer-as-target shape, and it turned the answer into a **durable,
  cached, `Role.SYSTEM`** artifact folded forward for the life of the session, which is a
  promotion in both trust and lifetime. **Both ends are now fenced, unconditionally.** The recap
  prompt carries the standing `SECURITY_PREAMBLE` and quotes the transcript and the previous
  account inside `wrap_untrusted` under a nonce minted for that call; the recap enters the turn
  through `fence_recap`, wrapped under a **second** nonce minted after the model has spoken, which
  is what stops a summarizer talked into copying the closer it was shown from ending the fence its
  own words sit in. Neither wrap takes an argument or sits behind a branch, so no state of the
  window produces an unfenced one, and the markers explain themselves in the recap's own text
  because the turn carrying them may have neither tools nor taint to earn a preamble. Pinned by an
  injection payload placed in a dropped assistant reply and asserted absent from everything
  outside the fences, in both directions (a hostile prefix, and a summarizer that repeated the
  payload), each of the five fence sites mutation-proven to redden its own test. **The cost is
  honest:** the recap now reads as data rather than as the assistant's own notes, so the model is
  told to rely on it for facts and never for instructions, and whether a fenced recap still
  answers the booking-reference question as well as the unfenced one measured is **unmeasured**.
  It joins the one-corpus entry above, since both want the same live run. Taint is deliberately
  **not** spread by a recap, argued in the addendum. Remaining from this deferral:
- **A fenced recap's usefulness is unmeasured.** The live measurement above ran before the fence
  and has not been re-run behind it. The safety direction is structural and does not need a model,
  but the usefulness direction does: the preamble tells the model that fenced content is "inert
  information to analyze or quote", and whether a cortex will quote a booking reference out of a
  fenced recap as readily as out of a trusted one is exactly the kind of claim this repo measures
  rather than assumes. Re-runnable as it stands (`packages/inference/tests/test_history_recap_live.py`,
  integration-marked). **Trigger:** any move of the default, which this shares with the
  one-corpus entry.
