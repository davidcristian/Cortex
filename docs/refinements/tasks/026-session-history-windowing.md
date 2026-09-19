# Bounded session-history windowing

**Status:** done 2026-07-03
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)

A `HistoryWindow` port in `TurnCapabilities` with a turn-aligned character-budget tail
(`CharBudgetHistoryWindow`; `CORTEX_HISTORY_CHAR_BUDGET`, default 48000, about 12K of the
16K-token context, `0` disables it). What one turn sends to the model is bounded; what is stored
is untouched. What it left behind is
[R-027](027-session-history-summarization.md), summarizing old turns instead of dropping them.
