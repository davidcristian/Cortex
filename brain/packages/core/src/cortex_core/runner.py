"""SubagentRunner: run one delegated task as a stateless function over the store (ADR-0010/0012)."""

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError
from cortex_core.ports import Clock, InferenceBackend, TaskStore
from cortex_core.roster import SubagentResources, SubagentRoster
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tool_loop import ReasoningDelta, ToolLoopContext, stream_tool_loop
from cortex_core.untrusted import TaintLedger, new_nonce, security_preamble_message


def _task_messages(task: SubagentTask) -> list[Message]:
    """The subagent's prompt: the instruction as the user ask, context as system framing."""
    messages = [Message(role=Role.USER, text=task.instruction, at=task.at, turn_id=task.id)]
    if task.context:
        framing = Message(role=Role.SYSTEM, text=task.context, at=task.at, turn_id=task.id)
        messages.insert(0, framing)
    return messages


class SubagentRunner:
    """Run a delegated task to a persisted result, resolving, admitting, placing (ADR-0012/0018)."""

    def __init__(
        self,
        store: TaskStore,
        roster: SubagentRoster,
        clock: Clock,
        *,
        tools: ToolDispatcher | None = None,
    ) -> None:
        self._store = store
        self._roster = roster
        self._clock = clock
        self._tools = tools

    @property
    def roster(self) -> SubagentRoster:
        """The roster this runner resolves against. The spawn tool advertises from it."""
        return self._roster

    @property
    def tools_enabled(self) -> bool:
        """Whether subagents hold tools (ADR-0017 rule 2b), structural at wiring time."""
        return self._tools is not None

    async def run(self, task_id: str) -> SubagentResult:
        """Load, resolve (ADR-0017), admit (CPU/RAM), place (VRAM), run, persist."""
        task = await self._store.get_task(task_id)
        if task is None:
            return await self._failed(task_id, "task not found")
        name = self._roster.resolve(
            task.model, tainted=task.tainted, tools_enabled=self.tools_enabled
        )
        if name is None:
            return await self._failed(task_id, f"unknown subagent model {task.model!r}")
        res = self._roster.entries[name].resources
        async with res.scheduler.admit(res.request):
            placement = res.placer.place(res.request)
            try:
                return await self._run_placed(task, res, res.backends[placement.target])
            finally:
                res.placer.release(placement)

    async def _run_placed(
        self, task: SubagentTask, res: SubagentResources, backend: InferenceBackend
    ) -> SubagentResult:
        """Stream the loaded task to a persisted result on the placed backend."""
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
            turn_id=task.id,
            taint=taint,
            nonce=new_nonce(),
        )
        parts: list[str] = []
        try:
            async for delta in stream_tool_loop(backend, res.request.model, working, context):
                if not isinstance(delta, ReasoningDelta):
                    parts.append(delta)  # noqa: PERF401
        except InferenceError as err:
            return await self._persist(
                SubagentResult(
                    task_id=task.id,
                    output="".join(parts),
                    ok=False,
                    detail=str(err),
                    tainted=taint.tainted,
                )
            )
        return await self._persist(
            SubagentResult(task_id=task.id, output="".join(parts), tainted=taint.tainted)
        )

    async def _failed(self, task_id: str, detail: str) -> SubagentResult:
        """Persist the fail-closed empty result for a task that never reached a backend."""
        return await self._persist(
            SubagentResult(task_id=task_id, output="", ok=False, detail=detail)
        )

    async def _persist(self, result: SubagentResult) -> SubagentResult:
        """Write the result to the store and hand it back to the caller."""
        await self._store.put_result(result)
        return result
