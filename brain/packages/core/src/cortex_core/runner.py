"""SubagentRunner: run one delegated task as a stateless function over the store (ADR-0010/0012).

The runner is a subagent's body. It admits against the CPU/RAM budget, places itself on GPU or CPU
against the VRAM budget, loads the task from the ``TaskStore`` **by id** (not cortex memory --
everything it needs is in the store), runs the shared bounded infer-tool loop on the placed backend
with its tool subset, and persists a ``SubagentResult``. It holds no state between calls, so a
restart or model swap mid-delegation loses nothing: the task is re-readable from the store. A failed
inference becomes an ``ok=False`` result the cortex consumes, not an exception -- the tool contract.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError
from cortex_core.placement import PlacementRequest, PlacementTarget
from cortex_core.ports import Clock, InferenceBackend, SubagentPlacer, SubagentScheduler, TaskStore
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.untrusted import TaintLedger, new_nonce, security_preamble_message


@dataclass(frozen=True, slots=True)
class SubagentResources:
    """One subagent tier's placement machinery, bundled so the runner takes it as a unit (ADR-0012).

    ``backends`` maps each target to its ``InferenceBackend`` (the GPU sidecar and the CPU one);
    ``scheduler`` is the soft CPU/RAM budget; ``placer`` is the VRAM-budget accountant; ``request``
    is this tier's resource ask (its ``model`` is the subagent id). Mirrors ``TurnCapabilities`` --
    collaborators that always travel together.
    """

    backends: Mapping[PlacementTarget, InferenceBackend]
    scheduler: SubagentScheduler
    placer: SubagentPlacer
    request: PlacementRequest


def _task_messages(task: SubagentTask) -> list[Message]:
    """The subagent's prompt: the instruction as the user ask, context as system framing."""
    messages = [Message(role=Role.USER, text=task.instruction, at=task.at, turn_id=task.id)]
    if task.context:
        framing = Message(role=Role.SYSTEM, text=task.context, at=task.at, turn_id=task.id)
        messages.insert(0, framing)
    return messages


class SubagentRunner:
    """Run a delegated task to a persisted result -- admitted, placed, then streamed (ADR-0012)."""

    def __init__(
        self,
        store: TaskStore,
        resources: SubagentResources,
        clock: Clock,
        *,
        tools: ToolDispatcher | None = None,
    ) -> None:
        self._store = store
        self._resources = resources
        self._clock = clock
        self._tools = tools

    async def run(self, task_id: str) -> SubagentResult:
        """Admit (CPU/RAM), place (VRAM), route to the placed backend, then persist the result.

        Admission is outer and may wait; placement is inner, synchronous, and never blocks, so no
        VRAM is ever reserved while queuing -- the "reserved VRAM then no CPU slot" leak is
        impossible. The placement's VRAM is always returned in the ``finally``.
        """
        res = self._resources
        async with res.scheduler.admit(res.request):
            placement = res.placer.place(res.request)
            try:
                return await self._run_placed(task_id, res.backends[placement.target])
            finally:
                res.placer.release(placement)

    async def _run_placed(self, task_id: str, backend: InferenceBackend) -> SubagentResult:
        """Load the task by id and stream it to a persisted result on the placed backend."""
        task = await self._store.get_task(task_id)
        if task is None:
            return await self._persist(
                SubagentResult(task_id=task_id, output="", ok=False, detail="task not found")
            )
        working = _task_messages(task)
        # A tools-enabled subagent reads untrusted content too, so it gets the same standing rule
        # and its own taint ledger. A subagent that reads a malicious file taints its result,
        # which propagates to the cortex that spawned it (ADR-0013).
        if self._tools is not None:
            working.insert(0, security_preamble_message(task.at, task.id))
        taint = TaintLedger()
        context = ToolLoopContext(
            dispatcher=self._tools,
            clock=self._clock,
            turn_id=task_id,
            taint=taint,
            nonce=new_nonce(),
        )
        parts: list[str] = []
        try:
            async for delta in stream_tool_loop(
                backend, self._resources.request.model, working, context
            ):
                # Append incrementally (not a comprehension) so text produced before a
                # mid-stream failure survives into the ok=False result below.
                parts.append(delta)  # noqa: PERF401
        except InferenceError as err:
            return await self._persist(
                SubagentResult(
                    task_id=task_id,
                    output="".join(parts),
                    ok=False,
                    detail=str(err),
                    tainted=taint.tainted,
                )
            )
        return await self._persist(
            SubagentResult(task_id=task_id, output="".join(parts), tainted=taint.tainted)
        )

    async def _persist(self, result: SubagentResult) -> SubagentResult:
        """Write the result to the store and hand it back to the caller."""
        await self._store.put_result(result)
        return result
