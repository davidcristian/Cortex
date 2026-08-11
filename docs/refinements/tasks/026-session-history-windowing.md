# Bounded session-history windowing

**Status:** landed 2026-07-03
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)

A pure `HistoryWindow` seam in `TurnCapabilities` with a turn-aligned char-budget tail
(`CharBudgetHistoryWindow`; `CORTEX_HISTORY_CHAR_BUDGET`, default 48000 ≈ 12K of the
16K-token context, `0` disables). What one turn sends to the model is bounded, persistence
untouched. Remaining from the original deferral:
