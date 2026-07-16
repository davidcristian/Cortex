# Session history & context

Deferred refinements from Slice 3's cortex chat and session work; the windowing decision and the summarization alternatives it weighs live in [ADR-0014](../adr/ADR-0014-history-windowing.md). Extracted from the ROADMAP's deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed entries are the historical record of what each deferral became, and the index at [index.md](index.md) carries the recommended pickup order.

**Open items:** Session-history summarization

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
  itself.** A summarizing window cannot be behavior-validated on the 8 GB dev GPU, where the cortex
  tier (gemma-12B) does not fit, and the cache-versus-recompute-per-turn decision this entry named is
  unresolved (a design choice, not a wrapper). So the honest slice waits for the model manager's real
  GPU lifecycle to give user-tier hardware, and lands the async widening together with the
  summarizer rather than the widening alone as an empty async layer.
- **Bounded backpressure on the `Converse` output queue landed 2026-07-03.** The per-turn
  output queue (`converse.py`) is now credit-bounded (`CORTEX_SEAM_CONVERSE_BUFFER`, default
  256): a consumer that stops reading suspends generation at the bound, while the terminal
  `SeamError` and teardown bypass the credits so failure never blocks behind a full buffer.
  The `Converse` stream contract is unchanged; design in
  [brain-orchestrator.md](../modules/brain-orchestrator.md).
