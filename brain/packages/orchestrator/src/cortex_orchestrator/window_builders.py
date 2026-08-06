"""The turn's history window, picked from config (ADR-0014, ADR-0038 decision 9).

Split out of ``builders.py`` for the line cap when the summarizing window arrived (the
``memory_builders``/``subagent_builders`` precedent). One builder, called only by
``wiring.run_from_env``: which window a deployment gets is a composition-root decision, and
the core never reads an environment variable to make it.
"""

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
    """The turn's history window, or None when windowing is disabled (ADR-0014/ADR-0038).

    A positive budget caps what one turn sends to the model at the newest whole turns
    fitting it; 0 (`CORTEX_HISTORY_CHAR_BUDGET=0`) disables windowing, so the model gets
    the full stored history, the pre-ADR-0014 behavior. Persistence is untouched either way.

    `summarize` (`CORTEX_HISTORY_SUMMARY`, default off) wraps that budget window in the
    summarizing one, which recaps the turns the budget drops instead of losing them. It is
    off by default because it spends a cortex generation on the turns where the window's
    boundary moves, straight onto time-to-first-token, and it is meaningless without a budget
    to drop anything: with windowing disabled there is no dropped prefix to recap, so the
    flag is ignored rather than building a wrapper that can never fire.
    """
    if char_budget < 1:
        return None
    window = CharBudgetHistoryWindow(char_budget)
    if not summarize:
        return window
    return SummarizingHistoryWindow(window, sessions, backend, model, clock)
