# Session history & context

Deferred refinements from Slice 3's cortex chat and session work; the windowing decision and the summarization alternatives it weighs live in [ADR-0014](../adr/ADR-0014-history-windowing.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** 1, and it is not the one this line named a few hours ago (**restated 2026-08-08, twice in one day**). The morning's restatement split "the recap measurement rests on one corpus" into a **permanent caveat** (the corpus is hand built by the author of the feature, which no run this repo can make retires, since any corpus an agent builds is built by the same interested party) and one real item, that nothing had been measured **about a cortex under load**. That item closed the same day, measured against three overlapping `Converse` streams, and the caveat stands unchanged and un-counted. What is open now is what the run turned up on its way past: **a consumer that stops reading holds the GPU lease across its whole reply**, so a stalled stream now blocks a stranger's fold, which is the shipped backpressure behaving as designed and nobody having written down who pays for it. The unbounded fold and the fold's silence were both closed 2026-08-06, when the summary moved to on by default.

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
- **The measurement is one corpus, and half of what it did not measure has now been measured
  (2026-08-06).** It shows the mechanism works and is not a benchmark: a single hand-built
  conversation, by the author of the feature, with the needed fact placed where a summary would
  keep it. Two of the three things it did not cover were taken on the re-run below. **Fold quality
  after several boundary moves is no longer unmeasured, and it is the weak one:** over three
  independent sessions of five folds each, the opening fact survived into the final account 2 of 3
  times, the round that lost it losing the whole opening (no reference, no hotel, no card) while
  keeping the recent filler. **Repetition is covered too**, the single-fold arm having answered 3
  of 3 with the control failing 3 of 3. What is still one corpus is the conversation itself: still
  hand-built, still by the author, still with the fact placed where a summary would keep it, and
  still nothing about a cortex under load. **The retention half of that trigger was answered
  2026-08-06** and is now 3 of 3 over the same three staged sessions (the cheap-fold entry below),
  which is what let the default move; the corpus half was not, and the default moved anyway.
  **Trigger:** now the standing one, since the feature ships on: a real conversation, and anything
  about a cortex under load, before this measurement is quoted as evidence about either.
  **Split 2026-08-08 into a caveat and an item, because the two halves of that trigger are not the
  same kind of not-done.** "A real conversation" is an **authorship** objection, and authorship is
  not something a run can fix: every corpus this repo can produce is written by the party whose
  conclusion it tests, so a wider or more adversarial one moves the evidence and never the caveat.
  It is therefore recorded here as a **permanent caveat** on these numbers rather than carried as
  work, and it retires only through use, when the shipped feature meets conversations nobody staged.
  "Anything about a cortex under load" is a different claim entirely: it is about hardware and
  concurrency, the card is here, and a fold contending with a reply for one non-reentrant lease is
  exactly the kind of thing a staged run can show. **That half stays the area's one open item**, and
  it is what the count means now. Nothing about the measured results changes; what changes is that
  the entry stops asking for a corpus that would not settle it.
- **The recap pass is unbounded and unthrottled, and its trigger has fired (2026-08-06).** Every
  boundary move spends a full cortex generation over the newly dropped turns, serialized ahead of
  the reply, and the fold's prompt is whatever those turns say. Two knobs were consciously not
  built: a minimum number of newly dropped messages before a fold is worth paying for, and a token
  cap on the recap request (the reply is bounded at `RECAP_MAX` characters after the fact, not
  before). The re-run put numbers on both halves. A fold costs 14.5 s to 30.8 s typically, with
  outliers of 77.3 s and **224.5 s**, and the server's own counters say where it goes: that 224.5 s
  fold decoded 6286 tokens against a 370-token prompt, a typical one decodes 400 to 850, and the
  account actually stored is 330 to 650 characters, which is 80 to 160 tokens. So most of every
  fold is reasoning `drain_text` discards, and the missing token cap is what leaves the tail
  unbounded. It is the first of the four things a default move waits on
  ([ADR-0038](../adr/ADR-0038-ranked-recall.md) re-measured-behind-the-fence addendum), and the
  second is not here but in [inference-model-manager.md](inference-model-manager.md): a fold is the
  clearest case yet for the disable-thinking lever, since unlike a reply nobody ever sees the
  thinking it pays for. **Closed 2026-08-06** by the cheap-fold entry below, which built both
  knobs and that lever together.
- **Nothing tells the user a turn is folding (opened 2026-08-06).** The fold is serialized ahead of
  the reply, so on the turn where the boundary moves the user waits the fold plus the reply with
  nothing on screen that distinguishes it from a slow model: the overlay's whisper starts breathing
  its accent mist the moment they press enter, and the chip that would say otherwise renders only
  when a `StatusUpdate` or `ToolActivity` has landed. None does. The seam is not the obstacle:
  `SeamProgressSink` is per Converse stream and emits onto that stream's own queue rather than
  through the turn generator, and `build_history_window` is already called inside the per-stream
  `capabilities` closure that holds one, so an event emitted during selection would surface while
  `assemble_inference_messages` is still running. What is missing is the port: `HistoryWindow.select`
  takes a history and a session id and no sink, so the window has nothing to emit onto. Deliberately
  not built here, on a knob that is staying off. **Closed 2026-08-06** by the cheap-fold entry
  below, which widened exactly that port and found this reading of the obstacle correct.
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
- **A fenced recap's usefulness was measured 2026-08-06 and the fence is not what costs
  ([ADR-0038 re-measured-behind-the-fence addendum](../adr/ADR-0038-ranked-recall.md)); the
  default stays off all the same, on the user's decision, against numbers the same run
  falsified.** The question was whether a cortex told the recap is quoted data would still quote a
  booking reference out of it. It does: three runs of the recorded live test, and behind the fence
  the reply is "Your booking reference is QH7-4412." exactly as it read unfenced, with the shipped
  window failing to answer all three times. **The control is now asserted rather than printed**,
  which is the trap this repo has fallen into twice: an arm that answers anyway has measured
  nothing, so the test fails instead of reporting a comparison with no contrast in it. So is the
  absence of fence markers from the reply, a defect that would have been visible only by reading
  the output. **What the fence costs is characters, not the answer:** the same 484-character
  account reaches the model as a 1022-character message once its standing preface and two markers
  are around it, so the recap message roughly doubled while the account inside it did not change.
  The fold also got slower, 11.0 s unfenced against 15.2 s and 23.6 s here, which is partly the
  larger prompt and partly run variance, and is dwarfed by what follows. **What stopped the default
  is the case a default runs in**, and it is written up as its own finding on the two entries above:
  five folds compound, retention was 2 of 3, and a fold reached 224.5 s. The user had decided to
  turn the summary on and accepted 11 s per boundary move; that premise is what this run
  falsified, so the knob stays one env variable away rather than shipping against its own numbers.
  The live test now carries both arms, the single fold and the staged one
  (`packages/inference/tests/test_history_recap_live.py`, integration-marked), and reports
  retention as a rate rather than asserting it, since asserting a probabilistic model behaviour
  pins the model rather than the code. Remaining from this deferral: nothing of its own, the four
  things a default move waits on being the two entries above, the disable-thinking lever in
  [inference-model-manager.md](inference-model-manager.md), and the fold's silence, opened above.
- **The recap pass is bounded and floored, the fold is no longer silent, and the default moved to
  on, 2026-08-06 ([ADR-0038 cheap-fold addendum](../adr/ADR-0038-ranked-recall.md)).** The two
  entries above named four things a default move waited on and all four landed together. **The
  diagnosis held on every point** it was checked against the tree: `drain_text` called
  `backend.stream(model, messages, schema=schema)` and `_build_payload` put nothing else on the
  wire, so the request carried no `max_tokens` and no `chat_template_kwargs`; `RECAP_MAX` was
  applied by `clean_recap` to text the model had already finished; and `drain_text` keeps only
  `TextChunk`, so the whole `ReasoningChunk` stream was decoded, paid for and dropped unread.
  **Thinking is now off per request**, through a new `GenerationBounds` on
  `InferenceBackend.stream` that the llama.cpp adapter renders as
  `chat_template_kwargs: {"enable_thinking": false}`, verified against the shipped build before
  anything was written; per request rather than per server because one resident cortex both
  answers the user, where the compose file deliberately leaves deliberation on, and folds a recap,
  where it is thrown away. **The request is capped** at 512 tokens, which is `RECAP_MAX` said in
  the request's own unit and roughly six times the account the prompt produces, and the cap and
  the switch ship together because a cap alone is a trap this repo measured: the identical prompt
  at `max_tokens` 160 and 256 with thinking on came back `finish_reason: "length"` with 624 and
  988 characters of reasoning and an EMPTY reply, and even at 512 it is a coin flip. **Hitting a
  bound degrades to the plain window rather than to half a sentence:** `clean_recap` refuses a
  reply that does not end a sentence and one longer than `RECAP_MAX`, because storing a truncated
  account would advance `covers` past turns the missing tail never reached and the next fold reads
  from `covers` forward, so those turns would be lost for good rather than for a turn. **A fold
  floor** (`CORTEX_HISTORY_RECAP_MIN_CHARS`, default 2000, clamped to the character budget at the
  composition root) stops a small boundary move from spending a pass; deferring is not skipping,
  since the next fold reads from the unmoved `covers` and picks up everything deferred, and what
  it costs meanwhile is a gap smaller than the floor sitting in neither the window nor the account.
  **Measured against the request that shipped**, on the identical prompt through the real adapter:
  378, 531 and 602 decoded tokens at 13.6 s, 18.9 s and 21.5 s became 88, 87 and 88 at 3.9 s, 3.8 s
  and 3.9 s, and the account got slightly LONGER (369 to 382 characters against 345 to 367). Across
  the staged five-fold arm a fold decodes 61 to 163 tokens for 2.9 s to 6.2 s with no tail at all.
  Remaining from this deferral: nothing of its own.
- **Nothing telling the user a turn is folding closed 2026-08-06 ([ADR-0038 cheap-fold
  addendum](../adr/ADR-0038-ranked-recall.md)).** The entry's reading of the obstacle held exactly:
  the seam was never the problem and the port was. `HistoryWindow.select` now takes
  `progress: ProgressSink | None`, handed per CALL rather than held on the window, matching the
  dispatch stamp's discipline (a sink belongs to one `Converse` stream while a window is a policy,
  so passing it in keeps a shared window correct for every stream rather than relying on one being
  built per stream). `CharBudgetHistoryWindow` ignores it; the summarizing window emits one
  `StatusUpdate(state="folding", detail="summarizing the earlier part of this conversation")`
  before the pass and only when a pass is really about to happen, so a cache hit and a deferred
  fold stay silent rather than putting a chip on screen for work that is not happening.
  `assemble_inference_messages` passes `caps.progress`, and because the sink writes onto the
  stream's own queue rather than through the suspended turn generator, the chip lands before the
  reply's first token, which a converse-level test asserts by event order. **No overlay change was
  needed**, a generic status already rendering as a chip, which the overlay's own suite pins.
  Remaining from this deferral: nothing.
- **The default moved to on, 2026-08-06, on the user's standing decision now carried by numbers
  ([ADR-0038 cheap-fold addendum](../adr/ADR-0038-ranked-recall.md)).** The previous pass refused
  to ship it over its numbers; these are the numbers that let it ship on them. **Retention moved
  from 2 of 3 to 3 of 3** over the same three staged sessions of five compounding folds, and the
  final accounts now carry the reference, the hotel, the card, the adapter, the museums and the
  transit advice together instead of keeping recent filler. A fold costs 2.9 s to 6.2 s with a
  chip on screen saying why, against 14.5 s to 224.5 s in silence. At the shipped floor the same
  conversation folded **once** over five boundary moves for 3.4 s of model time in total, still
  3 of 3. `CORTEX_HISTORY_SUMMARY=false` is the same one switch it always was, pointing the other
  way, and the new default is pinned by a test that reddens when it is flipped back. **What the
  run also showed honestly:** at the floor, the account covered 10 of the 20 dropped messages and
  the other 10 sat in neither the window nor the account, under the floor, which is the gap the
  budget clamp exists to bound. Remaining from this deferral: nothing of its own; the one-corpus
  entry above is now the only thing between this feature and a claim about real conversations.
- **The cortex-under-load half was measured 2026-08-08 and the sequencing argument held
  ([ADR-0038 fold-under-load addendum](../adr/ADR-0038-ranked-recall.md)); this entry closes and
  its authorship half stays a caveat.** The entry above split into a caveat and an item that
  morning, and the item said nothing had been measured about a fold contending with a reply for
  one non-reentrant lease. It has been, by
  `packages/orchestrator/tests/test_fold_under_load_live.py`: the shipped `converse` use case over
  the real adapter, the real Redis store and the real resident cortex, with every model call's
  lease timestamped at request, grant and release. **The argument re-derived first, since this
  file's own warning demands it**, and every clause of it still matched the tree: the lease is
  taken on the adapter generator's first `__anext__` and held to the end of its `async with`, a
  fold takes it through `drain_text` which leaves that block in a `finally`, and `handle_turn`
  awaits the whole of `assemble_inference_messages` several statements before it first iterates the
  reply. **What was proven, rather than assumed, is that the streams overlapped**: the run collects
  every moment one stream asked for the lease strictly inside a different stream's hold and fails
  when it finds none, because concurrent streams that never really contend produce a clean green
  that means nothing, which is the null result this backlog has recorded twice. Three folds were
  requested at the same instant and five acquisitions were issued under someone else's hold. **The
  argument held on every point it claims**: no two holds ever overlapped, every stream's fold
  released before that stream's reply acquired, nothing was left ungranted or unreleased, and no
  answer or stored recap carried another session's booking reference (twelve of twelve over four
  runs, one window instance shared by all three streams, one `folding` chip landing on each
  stream's own wire). **What load costs is queueing**: time to first token went from 4.6 s solo to 10.3 s,
  12.0 s and 17.5 s, and one reply waited 5.41 s behind two folds that were not its own, which is
  the interleaving the argument never denied and nobody had priced. Two turns of ONE session
  concurrently were run too, since append-only history is the whole reason a racing pair of folds
  is safe: both answered with the session's own reference and the surviving recap covered a prefix
  that really exists, the loser of the write race costing a repeated fold and never a wrong answer.
  **The harness was proven able to fail before it was believed**: a window that opens a model call
  and never closes it, which is exactly what `drain_text` prevents, deadlocked the turn and the
  same checker named it (`fold took the lease and never released it`, `reply waited for the lease
  and never got it`), and the same two streams run one after the other reported zero contentions.
  Remaining from this deferral: the stalled-consumer entry below, and the corpus caveat above,
  which no run retires.
- **A consumer that stops reading holds the GPU for the whole of its reply (opened 2026-08-08).**
  *Fix when it bites.* The reply's lease is held for the adapter generator's whole lifetime, and
  the credit bound above (`CORTEX_SEAM_CONVERSE_BUFFER`) suspends generation INSIDE that lease when
  the consumer stops dequeuing, so a stalled reader does not merely stall itself. Measured on the
  run above at a one-credit bound with the reader stalling 12 s: the stalled stream's reply held
  the lease **16.52 s** against the 2.2 s to 3.6 s an unstalled reply holds it, and the next
  stream's **fold waited 16.51 s** behind it. This predates the summary and is not caused by it;
  what the default-on fold changes is who pays, since a fold is now among the things that queue.
  Neither obvious direction is free: the bound exists to cap a stalled stream's memory (the entry
  that landed it is above), and letting generation run ahead of the consumer to release the lease
  sooner is the exact thing it refuses to do. A real fix is likelier to be a bound on how long a
  suspended generation may hold the lease, which means the adapter learning to abandon a stream the
  seam is no longer draining, and that is a port-shaped change rather than a knob. **Trigger:** a
  deployment with more than one live consumer, or any report of one slow client stalling turns that
  are not its own; at one overlay on one machine there is one consumer and it reads as fast as it
  can.
