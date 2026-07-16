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
- **Bounded backpressure on the `Converse` output queue landed 2026-07-03.** The per-turn
  output queue (`converse.py`) is now credit-bounded (`CORTEX_SEAM_CONVERSE_BUFFER`, default
  256): a consumer that stops reading suspends generation at the bound, while the terminal
  `SeamError` and teardown bypass the credits so failure never blocks behind a full buffer.
  The `Converse` stream contract is unchanged; design in
  [brain-orchestrator.md](../modules/brain-orchestrator.md).
