"""SubagentRunner: run one delegated task as a stateless function over the store."""

import logging

from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import SubagentAdmissionError
from cortex_core.placement import PlacementTarget
from cortex_core.ports import Clock, TaskStore
from cortex_core.progress import ProgressSink
from cortex_core.roster import SubagentResources, SubagentRoster
from cortex_core.subagent_attempt import PlacedAttempt
from cortex_core.subagent_outcome import AttemptFailure, AttemptOutcome, reran_on_cpu
from cortex_core.subagents import UNBOUNDED_ATTEMPT, AttemptBounds, SubagentResult, SubagentTask
from cortex_core.tool_budget import DispatchBudget

_REFUSED_TEMPLATE = (
    "refused before running: {reason}. The subtask was never attempted; answer without "
    "delegating this subtask, and say what you could not do."
)

_logger = logging.getLogger(__name__)


class SubagentRunner:
    """Run a delegated task to a persisted result: resolve, admit, place, run."""

    def __init__(
        self,
        store: TaskStore,
        roster: SubagentRoster,
        clock: Clock,
        *,
        tools: ToolDispatcher | None = None,
        constrain_output: bool = False,
        bounds: AttemptBounds = UNBOUNDED_ATTEMPT,
    ) -> None:
        self._store = store
        self._roster = roster
        self._tools = tools
        self._attempt = PlacedAttempt(
            clock, tools, constrain_output=constrain_output, bounds=bounds
        )

    @property
    def roster(self) -> SubagentRoster:
        """The roster this runner resolves against."""
        return self._roster

    @property
    def tools_enabled(self) -> bool:
        """Whether subagents have tools at all, decided when this runner is wired."""
        return self._tools is not None

    async def run(
        self,
        task_id: str,
        *,
        budget: DispatchBudget | None = None,
        progress: ProgressSink | None = None,
    ) -> SubagentResult:
        """Load the task, resolve the model, admit it, place it, run it, and persist the result."""
        task = await self._store.get_task(task_id)
        if task is None:
            return await self._failed(task_id, "task not found")
        name = self._roster.resolve(
            task.model, tainted=task.tainted, tools_enabled=self.tools_enabled
        )
        if name is None:
            return await self._failed(task_id, f"unknown subagent model {task.model!r}")
        res = self._roster.entries[name].resources
        try:
            async with res.scheduler.admit(res.request):
                outcome = await self._placed(task, res, budget=budget, progress=progress)
                return await self._persist(
                    SubagentResult(
                        task_id=task.id,
                        output=outcome.text,
                        ok=outcome.ok,
                        detail=outcome.detail,
                        tainted=outcome.tainted,
                    )
                )
        except SubagentAdmissionError as err:
            # Turned into a result rather than raised: an exception here would cross the
            # spawn tool and fail the whole turn, discarding the batch's other subagents.
            # The warning is here because nothing else keeps a lasting record of a refusal.
            _logger.warning(
                "a spawn was refused before it ran",
                extra={"task_id": task_id, "model": res.request.model, "reason": str(err)},
            )
            return await self._failed(task_id, _REFUSED_TEMPLATE.format(reason=err))

    async def _placed(
        self,
        task: SubagentTask,
        res: SubagentResources,
        *,
        budget: DispatchBudget | None,
        progress: ProgressSink | None,
    ) -> AttemptOutcome:
        """Place and run, re-running once on the CPU when a GPU-placed backend did not reply."""
        placement = res.placer.place(res.request)
        try:
            outcome = await self._attempt.run(
                task,
                res.request.model,
                res.backends[placement.target],
                budget=budget,
                progress=progress,
            )
        finally:
            res.placer.release(placement)
        if placement.target is not PlacementTarget.GPU or outcome.failure is not (
            AttemptFailure.INFERENCE
        ):
            return outcome
        _logger.warning(
            "a GPU-placed subagent did not answer; re-running it once on the CPU",
            extra={"task_id": task.id, "model": res.request.model, "detail": outcome.detail},
        )
        retried = await self._attempt.run(
            task,
            res.request.model,
            res.backends[PlacementTarget.CPU],
            budget=budget,
            progress=progress,
        )
        return reran_on_cpu(outcome, retried)

    async def _failed(self, task_id: str, detail: str) -> SubagentResult:
        """Persist the fail-closed empty result for a task that never reached a backend."""
        return await self._persist(
            SubagentResult(task_id=task_id, output="", ok=False, detail=detail)
        )

    async def _persist(self, result: SubagentResult) -> SubagentResult:
        """Write the result to the store and hand it back to the caller."""
        await self._store.put_result(result)
        return result
