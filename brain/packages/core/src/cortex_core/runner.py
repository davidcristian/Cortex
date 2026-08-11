"""SubagentRunner: run one delegated task as a stateless function over the store (ADR-0010/0012).

The runner is a subagent's body. It loads the task from the ``TaskStore`` **by id** (not cortex
memory, as everything it needs is in the store), resolves which roster entry runs it (the ADR-0017
boundary lives in ``SubagentRoster.resolve``: an untrusted-content path is pinned to the robust
default whatever the task requested, per ADR-0018), admits against the CPU/RAM budget, places itself
on GPU or CPU against the VRAM budget, runs the shared bounded infer-tool loop on the placed
backend with its tool subset, and persists a ``SubagentResult``. It holds no state between calls,
so a restart or model swap mid-delegation loses nothing: the task is re-readable from the store. A
failed inference becomes an ``ok=False`` result the cortex consumes, not an exception, per the tool
contract.

The run itself lives in ``subagent_attempt.py``, because there can be two of them: a GPU-placed
attempt whose backend did not answer is re-run once on the CPU (ADR-0012's deferred re-place,
scheduled by ADR-0030). This file owns the composition around that; that one owns the streaming.
"""

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

# What the cortex reads when the scheduler refuses a spawn outright. Phrased like the
# dispatcher's refusal messages: say it was refused rather than attempted, and say what to do
# instead. Three causes reach here, and the reason carries which: the impossible charge
# (permanent, a resource-budget misconfiguration, ADR-0012 admission-wall addendum), the drain
# window (transient, a model handoff quiescing the pool, ADR-0030), and a queue that outlasted
# the admission bound (ADR-0012 bounded-admission-wait addendum). A full budget still queues, so
# this means "busy" only after the bound has actually been spent waiting, never on first sight
# of a full budget, which is why the reason rather than this template says whether to retry.
_REFUSED_TEMPLATE = (
    "refused before running: {reason}. The subtask was never attempted; answer without "
    "delegating this subtask, and say what you could not do."
)

_logger = logging.getLogger(__name__)


class SubagentRunner:
    """Run a delegated task to a persisted result, resolving, admitting, placing (ADR-0012/0018)."""

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
        """The roster this runner resolves against. The spawn tool advertises from it."""
        return self._roster

    @property
    def tools_enabled(self) -> bool:
        """Whether subagents hold tools (ADR-0017 rule 2b), structural at wiring time."""
        return self._tools is not None

    async def run(
        self,
        task_id: str,
        *,
        budget: DispatchBudget | None = None,
        progress: ProgressSink | None = None,
    ) -> SubagentResult:
        """Load, resolve (ADR-0017), admit (CPU/RAM), place (VRAM), run, persist.

        Admission is outer and may wait; placement is inner, synchronous, and never blocks, so no
        VRAM is ever reserved while queuing. The "reserved VRAM then no CPU slot" leak is
        impossible. The placement's VRAM is always returned in the ``finally``. An unknown
        requested model fails closed as an ``ok=False`` result, mirroring "task not found", and so
        does a spawn the scheduler refuses outright (a charge no budget could ever fit, a pool
        draining for a model handoff, ADR-0030, or a queue that outlasted the admission bound).

        ``budget`` is the spawning turn's dispatch pool (ADR-0009 turn-wide addendum), handed
        down by ``SpawnSubagentsTool`` off the dispatch stamp so this run's tool calls come out
        of the turn's allowance rather than a fresh one. ``None`` means this run is its own root
        (the schedule ticker's fire, a direct caller) and it gets its own pool. ``progress`` is
        the spawning stream's side channel, also off the stamp: this run surfaces each of its
        audited tool steps onto it (ADR-0010 progress addendum). ``None`` (the ticker, a direct
        caller with no overlay) drops the steps, exactly as before this addendum.
        """
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
            # The scheduler's refusals: the impossible charge (ADR-0012 admission-wall addendum)
            # and the drain window of a model handoff (ADR-0030). Only `admit` raises it
            # (neither the placer nor the tool loop touches a scheduler), and it does so before
            # yielding, so nothing was placed or run. Degrading it to a value here keeps the
            # runner's contract that every outcome is a `SubagentResult`: an escaping exception
            # would cross the spawn tool, which only `ToolError` is caught past, and fail the
            # whole turn, discarding the batch's other subagents along with it.
            return await self._failed(task_id, _REFUSED_TEMPLATE.format(reason=err))

    async def _placed(
        self,
        task: SubagentTask,
        res: SubagentResources,
        *,
        budget: DispatchBudget | None,
        progress: ProgressSink | None,
    ) -> AttemptOutcome:
        """Place and run, re-running once on the CPU when a GPU-placed backend did not answer.

        ADR-0012 deferred this to the real GPU-placed runtime and ADR-0030 schedules it as "a
        single CPU re-run after a GPU-placed failure, recorded in the result's detail". Three
        properties make it safe rather than a retry loop:

        - it fires **only** on ``AttemptFailure.INFERENCE`` from a **GPU** placement, so a model
          that answered outside its grammar is not re-loaded to answer the same way, one still
          talking at its deadline (``TRUNCATED``, ADR-0005 total-cap addendum) is not re-loaded to
          talk past it again on the slower tier, and a CPU-placed failure has nowhere better to go;
        - the GPU reservation is released **before** the re-run, in the ``finally`` that already
          existed, so a CPU re-run never misreports headroom to a concurrent spawn (the ledger is
          a live-resource count, ADR-0012 decision 7);
        - it re-uses the same admission and the same dispatch budget, so a re-run buys no second
          CPU/RAM charge (the charge is target independent by design) and cannot spend past the
          turn's allowance. The one bound it does **not** re-use is the attempt's own deadline,
          which is armed fresh per attempt: a re-run handed what a failed attempt left of one
          would be refused before it began, and the failure a re-place exists for is exactly the
          one where nothing was produced to spend a deadline on. A task can therefore hold its
          admission for two deadlines rather than one, and only along the path a dead backend
          opens, since neither of the failures a deadline itself produces is re-placed.
        """
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
