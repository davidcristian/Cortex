"""The turn's history window, picked from config (ADR-0014, ADR-0038 decision 9).

Split out of ``builders.py`` for the line cap when the summarizing window arrived (the
``memory_builders``/``subagent_builders`` precedent). One builder, called only by
``wiring.run_from_env``: which window a deployment gets is a composition-root decision, and
the core never reads an environment variable to make it. It takes the runtime config whole,
the ``build_memory``/``build_subagents`` shape, because the window now reads four values off
it and threading them one by one was already at the argument ceiling.
"""

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
) -> HistoryWindow | None:
    """The turn's history window, or None when windowing is disabled (ADR-0014/ADR-0038).

    A positive ``history_char_budget`` caps what one turn sends to the model at the newest
    whole turns fitting it; 0 (`CORTEX_HISTORY_CHAR_BUDGET=0`) disables windowing, so the
    model gets the full stored history, the pre-ADR-0014 behavior. Persistence is untouched
    either way.

    `history_summary` (`CORTEX_HISTORY_SUMMARY`) wraps that budget window in the summarizing
    one, which recaps the turns the budget drops instead of losing them, and
    `history_recap_min_chars` (`CORTEX_HISTORY_RECAP_MIN_CHARS`) is how much newly dropped
    conversation is worth the model pass a fold costs. The wrapper is meaningless without a
    budget to drop anything: with windowing disabled there is no dropped prefix to recap, so
    the flag is ignored rather than building a wrapper that can never fire.

    **The floor is clamped to the budget here**, which is the one place both numbers are in
    hand. A fold's cost is flat (one model pass) so an absolute floor is the right shape for
    deciding whether the pass is worth it, but what a deferred fold costs is text sitting in
    neither the window nor the account, and that is only bearable while it is small next to
    the window. A floor above the budget would let more conversation go unaccounted for than
    the model can see at all, which is exactly when its absence is felt, so it is capped rather
    than trusted; a deployment that shrinks the budget therefore tightens the floor with it
    instead of silently turning the recap off.
    """
    if runtime.history_char_budget < 1:
        return None
    window = CharBudgetHistoryWindow(runtime.history_char_budget)
    if not runtime.history_summary:
        return window
    return SummarizingHistoryWindow(
        window,
        sessions,
        backend,
        runtime.cortex_model,
        clock,
        min_dropped_chars=min(runtime.history_recap_min_chars, runtime.history_char_budget),
    )
