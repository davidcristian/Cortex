"""The turn's history window, picked from config."""

from cortex_core import (
    CharBudgetHistoryWindow,
    Clock,
    HistoryWindow,
    InferenceBackend,
    SessionStore,
    SummarizingHistoryWindow,
)
from cortex_orchestrator.config import BrainRuntimeConfig


def build_history_window(
    runtime: BrainRuntimeConfig,
    *,
    sessions: SessionStore,
    backend: InferenceBackend,
    clock: Clock,
    model: str,
) -> HistoryWindow | None:
    """The turn's history window, whose recap ``model`` writes, or None when windowing is off."""
    if runtime.history_char_budget < 1:
        return None
    window = CharBudgetHistoryWindow(runtime.history_char_budget)
    if not runtime.history_summary:
        return window
    return SummarizingHistoryWindow(
        window,
        sessions,
        backend,
        model,
        clock,
        min_dropped_chars=min(runtime.history_recap_min_chars, runtime.history_char_budget),
    )
