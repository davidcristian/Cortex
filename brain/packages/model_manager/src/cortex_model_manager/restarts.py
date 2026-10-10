"""How often the supervisor starts a model again after its process exits without being asked."""

from collections.abc import Callable, Collection
from dataclasses import dataclass

# Three attempts cover a crash and two failed loads; a model that fails more often than that has
# a cause a restart cannot fix, and is left `failed` for whoever asks next.
DEFAULT_RESTART_LIMIT = 3

# Lets the driver release the exited process's device memory before the next load claims it.
DEFAULT_RESTART_DELAY_S = 2.0

# Longer than a tier-scale load, so only a process that loaded and then served counts as stable.
DEFAULT_STABLE_AFTER_S = 600.0


@dataclass(frozen=True, slots=True)
class RestartPolicy:
    """Which models are started again after an unrequested exit, and how many times in a row."""

    models: Collection[str] = ()
    limit: int = DEFAULT_RESTART_LIMIT
    delay_s: float = DEFAULT_RESTART_DELAY_S
    stable_after_s: float = DEFAULT_STABLE_AFTER_S


class RestartBudget:
    """Counts the restarts each model has had since a start was asked for or it ran stably."""

    def __init__(self, policy: RestartPolicy, clock: Callable[[], float]) -> None:
        self._policy = policy
        self._clock = clock
        self._started: dict[str, float] = {}
        self._used: dict[str, int] = {}

    def covers(self, model: str) -> bool:
        """Whether ``model`` is started again when its process exits unasked."""
        return model in self._policy.models

    @property
    def delay_s(self) -> float:
        """How long to wait after an exit before the restart."""
        return self._policy.delay_s

    def started(self, model: str) -> None:
        """Record that a process for ``model`` began now."""
        self._started[model] = self._clock()

    def reset(self, model: str) -> None:
        """Give ``model`` its whole budget back, as an explicit start does."""
        self._used[model] = 0

    def take(self, model: str) -> int | None:
        """Spend one restart and return its number, or ``None`` once the budget is spent."""
        lived_s = self._clock() - self._started[model]
        if lived_s >= self._policy.stable_after_s:
            self._used[model] = 0
        used = self._used.get(model, 0)
        if used >= self._policy.limit:
            return None
        self._used[model] = used + 1
        return used + 1
