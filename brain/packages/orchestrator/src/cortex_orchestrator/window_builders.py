"""The turn's history window, picked from config (ADR-0014, ADR-0038 decision 9)."""

from cortex_core import CharBudgetHistoryWindow, Clock, InferenceBackend, SessionStore

# Windowing's newer public names are reached through their own modules rather than the
# `cortex_core` barrel, which is at its 300-line cap (docs/refinements/repo-gates.md).
from cortex_core.summarizing import SummarizingHistoryWindow
from cortex_core.windowing import HistoryWindow


def build_history_window(
    char_budget: int,
    *,
    summarize: bool,
    sessions: SessionStore,
    backend: InferenceBackend,
    model: str,
    clock: Clock,
) -> HistoryWindow | None:
    """The turn's history window, or None when windowing is disabled (ADR-0014/ADR-0038)."""
    if char_budget < 1:
        return None
    window = CharBudgetHistoryWindow(char_budget)
    if not summarize:
        return window
    return SummarizingHistoryWindow(window, sessions, backend, model, clock)
