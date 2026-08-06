# ADR-0014: Session-history windowing as a char-budget tail behind a `HistoryWindow` seam

- **Status:** Accepted (Slice 3 deferred refinement, landed 2026-07-03)
- **Date:** 2026-07-03

## Context

`TurnEngine` reads a session's **full** history from the `SessionStore` every turn and hands
all of it to the backend. That is correct under the one hard rule (the store is the sole source of
truth), but unbounded toward the model: a long-lived conversation eventually exceeds the
resident cortex's context window (`CORTEX_CTX_SIZE`, 16K tokens on the deployed gemma-4-12B,
ADR-0004/0007), at which point llama-server truncates or errors and the turn degrades
unpredictably. The gap was recorded at Slice 3 in the ROADMAP deferred-refinements list
("windowing / truncation / summarization"). This is distinct from **memory** (ADR-0008),
which is durable *cross-session* recall. This ADR is about the *in-context* history of the
current session only.

## Decision

1. **A pure `HistoryWindow` seam in the core (`windowing.py`), injected via
   `TurnCapabilities.window`.** `select(history) -> Sequence[Message]` returns the slice of
   the stored history one turn sends to the model; `None` (the default) keeps today's
   full-history behavior byte for byte. The window applies at **inference-message assembly
   only**. Persistence is untouched: the store keeps every message, the window is derived
   fresh each turn, never stored, nothing to rehydrate (the one hard rule is unaffected).
   Like `memory` and `tools`, the capability slot keeps the engine's constructor within its
   dependency ceiling, and any future policy (summarization above all) drops into the same
   seam without touching `SessionStore` or `TurnEngine`.
2. **The shipped policy is `CharBudgetHistoryWindow(max_chars)`, which is a turn-aligned contiguous
   tail.** Selection groups messages into turns (consecutive `turn_id`), walks from the
   newest turn backward, and stops at the first turn that would overflow the budget:
   - **turns are kept or dropped whole**, so the model never sees an assistant reply without
     the user message it answered;
   - **the kept slice is a contiguous tail** because the walk stops at the first overflow rather
     than sieving old small turns past a big one, because a gap mid-history confuses the
     model more than honest truncation;
   - **the newest turn is always kept**, oversized or not, because the current user message must
     reach the model (the window never returns an empty slice for a non-empty history).
3. **Characters stand in for tokens.** The budget is counted in characters of message text
   (roughly 4 chars/token for English) so the core needs no tokenizer and no I/O. It is a
   deliberately conservative heuristic, not an exact fit. Deployments size it well under
   the model context.
4. **Config: `CORTEX_HISTORY_CHAR_BUDGET`, default `48000`, `0` disables.** Read by
   `BrainRuntimeConfig` and wired by `build_history_window` at the composition root. It is
   **on by default**: the deferral is a correctness gap under long sessions, and a knob
   nobody sets fixes nothing. 48K chars ≈ 12K tokens of history against the 16K-token
   cortex context, leaving ~4K tokens of headroom for the security preamble (ADR-0013),
   recalled memories (ADR-0008), tool schemas and in-turn tool steps (ADR-0009), and the
   reply itself.

## Alternatives rejected

- **Token-exact windowing.** Exact counting needs the model's tokenizer, an adapter/engine
  concern (llama-server's `/tokenize`) that would put I/O or a model-specific vocabulary
  inside the pure core, for precision the headroom margin buys more cheaply. If exactness is
  ever needed, a tokenizer-backed `HistoryWindow` adapter fits the same seam.
- **Last-N-turns.** Simpler to state but its unit is disconnected from the real constraint:
  N turns of one-liners and N turns of pasted logs differ by orders of magnitude in tokens.
- **Summarization (compress old turns instead of dropping them).** The richer option and the
  original deferral names it. But it changes content (a lossy model pass inside turn
  assembly), needs inference and therefore the GPU path, and deserves its own design.
  **Still deferred**, recorded in the ROADMAP (Slice 3 block); it will land behind this same
  `HistoryWindow` seam.

## Consequences

- Long sessions stop growing toward the context wall; what the model loses is the oldest
  turns, wholesale and predictably, while the stored history (and Slice 5 memory) keeps
  everything, so recall can still surface dropped context.
- A single oversized newest turn is sent whole and can still overflow the model context because
  the window bounds history, not one turn's size (a per-turn input cap would be a UX
  decision at the overlay, not silent truncation here).
- The `EchoInferenceBackend` reply counter counts user messages in the *windowed* history,
  so the `"reply {n}"` script diverges from the stored count only past the budget, which is
  unreachable in CI-sized tests, irrelevant on the real backend.
- The seam invites exactly the follow-ons planned: summarization, or a tokenizer-backed
  exact window, each a drop-in `HistoryWindow` with no engine change.

## Addendum (2026-07-16): summarization audited, the async widening priced and the lease hazard re-derived

The **Summarization** alternative above and its refinement entry
([docs/refinements/session-history.md](../refinements/session-history.md)) both defer a model pass
in turn assembly behind two costs: the sync `HistoryWindow.select` must go async, and `backend.py`
holds a non-reentrant GPU lease for a stream's lifetime. Audited against the code, both are milder
than they read, but a third cost binds, so the entry stays deferred with a sharper blocker. This is
one design problem with the **model-based reranker** ([ADR-0008 reranker-audit
addendum](ADR-0008-memory-v1.md)): both wait on the same sync-to-async `select` change and the same
lease discipline.

**The async widening is clean and contained, not a call-chain migration.** `HistoryWindow.select`
has exactly one production caller, `TurnEngine._inference_messages` (`engine.py`), which is already
an `async` method awaited by `handle_turn`. Widening `select` to `async` therefore adds one `await`
at that call site and propagates no async colour upward to any synchronous boundary; the only
implementer is `CharBudgetHistoryWindow`. An `async def select` whose body stays synchronous is
gate-clean here, because the `unused-async` lint (`RUF029`) is a preview-only rule and this repo runs
ruff without preview, so every existing heuristic selector satisfies the async port by wrapping its
body unchanged. The port change is real work (the protocol, the implementer, the fake, and the
selection tests all move to `async`), but it is bounded and mechanical.

**The lease hazard is navigable, not structural.** `SingleResidentModelManager` guards a
non-reentrant `asyncio.Lock` (`model.py`) that the inference adapter holds across the whole stream
generator (`backend.py`, the `async with acquire(...)` wraps the entire SSE read). But selection runs
inside `_inference_messages`, which `handle_turn` awaits to completion **before** it opens the reply
stream (`stream_tool_loop`), so at selection time the turn does not yet hold the lease. A summarizing
window that fully drains its own model call therefore acquires and releases the lock sequentially,
then the reply acquires it, exactly the discipline the title generator already uses (`generate_title`,
run at turn end). Confirmed against the real manager: a drained acquire followed by a second acquire
succeeds, while a summarizer call held open across the reply's acquire deadlocks. So the hazard is the
abandoned-stream case the entry named, a discipline requirement on the future selector, not the reply
already holding the lease.

**What binds, and what unblocks it.** A summarizing window is a model pass, and it cannot be
behavior-validated on the 8 GB dev GPU, where the cortex tier (gemma-12B) does not fit; the
cache-versus-recompute-per-turn question the entry named is also unresolved and is a design choice,
not a wrapper. So the honest slice waits for the model manager's real GPU lifecycle to give user-tier
hardware, and lands the async widening together with the summarizer rather than the widening alone as
an empty async layer. Recorded at
[docs/refinements/session-history.md](../refinements/session-history.md).

## Addendum (2026-07-19): summarization is blocked by an undecided design, not by the dev GPU

The addendum above says a summarizing window "cannot be behavior-validated on the 8 GB dev GPU,
where the cortex tier (gemma-12B) does not fit". The card holds the cortex.
[ADR-0029](ADR-0029-vision-screen-capture.md) measured it resident there on 2026-07-17 at
`-ngl 99 --ctx-size 4096 --parallel 1` beside its vision projector, which is the
heavier configuration, and ran a real vision turn through the shipped adapter on 2026-07-18;
[ADR-0030](ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
8188 MiB. What that card cannot serve is the 16K production context this ADR names for the deployed cortex, and
whether a summary keeps what the next turn needs can be judged well below 16K.

**What this changes.** The blocker, not the decision. What actually holds the slice is stated in
the same addendum and stands on its own: the cache-versus-recompute-per-turn question is undecided,
and `HistoryWindow.select` should widen together with the summarizer rather than land as an empty
async layer. So this reopens on that design work. Corrected the same day in
[docs/refinements/session-history.md](../refinements/session-history.md) and its
[index](../refinements/index.md).

No code changed here; this is a records correction at the origin ADR.

## Addendum (2026-08-06): summarization's two open questions are answered; the code is not written

The summarization-audit addendum above kept the slice deferred on two things, and
[ADR-0038](ADR-0038-ranked-recall.md) settles both.

**Cache, not recompute, and the reason is local to this system.** A session summary lives in Redis
behind `SessionStore`, beside the messages and the title it derives from, keyed by the boundary it
covers. `SessionStore` has `append`, `history`, `set_title` and a whole-session delete and **no verb
that edits or removes a message**, so a summary of a prefix can never become wrong, only incomplete:
a new summary folds the previous one together with the newly dropped turns, and a deleted session
takes its summary with it. There is no invalidation path to get wrong, which is exactly why caching
is safe here and would not be in a system with an edit verb. Recompute was priced against that at
one full cortex generation on every turn, serialized ahead of the reply and so straight onto
time-to-first-token, against one per boundary move. It survives a swap by construction, being text
in the store.

**The lease discipline is a helper rather than a habit.** `drain_text` (`drain.py`) runs one model
call and leaves the adapter's acquire block in a `finally`; `generate_title` moved onto it in the
same change, so the "sequential acquire" this ADR's audit addendum described as the title
generator's practice is now stated in one place a future selector can simply use.

**What is still deferred, and it is implementation only:** the `SessionStore` summary verbs (port,
fake, Redis adapter, contract test), a `SummarizingHistoryWindow`, the `async` widening of
`HistoryWindow.select` alongside it rather than as an empty async layer, and the config knob. That
widening was deliberately **not** taken with the recall one: `RecallPolicy.select` had three waiting
consumers and this port has one, so it waits for that one. Recorded in
[docs/refinements/session-history.md](../refinements/session-history.md) and its
[index](../refinements/index.md).

One claim of the audit addendum did not survive re-derivation and is corrected here: it names the
window's production caller as `_inference_messages` in `engine.py`, a method that no longer exists.
The caller is `assemble_inference_messages` in `turn_context.py`, still `async`, so the substance
(one caller, already async, one `await` to add) held.

## Addendum (2026-08-06): summarization is written

The addendum above left the slice on implementation only, and it landed the same day, recorded in
full in [ADR-0038's summarizing-window addendum](ADR-0038-ranked-recall.md). What arrived behind
this ADR's seam: `HistoryWindow.select` is now
`async select(history, *, session_id) -> Sequence[Message]`, `CharBudgetHistoryWindow` unchanged
in behaviour behind it, and `SummarizingHistoryWindow` wrapping it so the turns the budget drops
come back as a cached, model-written recap. The seam's contract gained one clause: a window
returns a subsequence of the history in order and may additionally PREPEND derived context of its
own, but may never drop or alter a message the wrapped window kept. That clause is what makes the
summarizer safe to run on the turn's critical path, since every one of its failure paths returns
the char-budget selection this ADR shipped, byte for byte.

The `async` widening cost one `await` at one caller, as this ADR's audit predicted, plus the
`session_id` the audit did not: a recap cached per session has to know which session it is
windowing. `CORTEX_HISTORY_SUMMARY` is the knob and it is off by default, against a shipped window that
could not answer a question the recap could. The cost first read as 11 s per boundary move; the
re-run behind the fence found 14.5 s to 30.8 s typically and 224.5 s at worst, with the fact
surviving five compounding folds 2 times in 3, which is why the default did not move
([ADR-0038](ADR-0038-ranked-recall.md) re-measured-behind-the-fence addendum).
