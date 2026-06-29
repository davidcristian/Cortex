"""SubagentRunner: run one delegated task as a stateless function over the store (ADR-0010).

The runner is a subagent's body. It admits against the CPU budget, loads the task from the
``TaskStore`` **by id** (never from cortex memory, since everything it needs is in the store), runs
the shared bounded infer↔tool loop on the subagent model with its tool subset, and persists a
``SubagentResult``. It holds no state between calls, so a restart or model swap mid-delegation
loses nothing: the task is re-readable from the store. A failed inference becomes an ``ok=False``
result the cortex consumes, not an exception, mirroring the tool-result contract.
"""

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError
from cortex_core.ports import Clock, InferenceBackend, SubagentScheduler, TaskStore
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tool_loop import stream_tool_loop


def _task_messages(task: SubagentTask) -> list[Message]:
    """The subagent's prompt: the instruction as the user ask, context as system framing."""
    messages = [Message(role=Role.USER, text=task.instruction, at=task.at, turn_id=task.id)]
    if task.context:
        framing = Message(role=Role.SYSTEM, text=task.context, at=task.at, turn_id=task.id)
        messages.insert(0, framing)
    return messages


class SubagentRunner:
    """Run a delegated task to a persisted result, under a CPU-budget slot (ADR-0010)."""

    def __init__(
        self,
        store: TaskStore,
        backend: InferenceBackend,
        scheduler: SubagentScheduler,
        clock: Clock,
        *,
        subagent_model: str,
        tools: ToolDispatcher | None = None,
    ) -> None:
        self._store = store
        self._backend = backend
        self._scheduler = scheduler
        self._clock = clock
        self._subagent_model = subagent_model
        self._tools = tools

    async def run(self, task_id: str) -> SubagentResult:
        """Admit, load the task, run the tool loop, and persist + return the result."""
        async with self._scheduler.admit():
            task = await self._store.get_task(task_id)
            if task is None:
                return await self._persist(
                    SubagentResult(task_id=task_id, output="", ok=False, detail="task not found")
                )
            working = _task_messages(task)
            parts: list[str] = []
            try:
                async for delta in stream_tool_loop(
                    self._backend,
                    self._subagent_model,
                    working,
                    dispatcher=self._tools,
                    clock=self._clock,
                    turn_id=task_id,
                ):
                    # Append incrementally (not a comprehension) so text produced before a
                    # mid-stream failure survives into the ok=False result below.
                    parts.append(delta)  # noqa: PERF401
            except InferenceError as err:
                return await self._persist(
                    SubagentResult(
                        task_id=task_id, output="".join(parts), ok=False, detail=str(err)
                    )
                )
            return await self._persist(SubagentResult(task_id=task_id, output="".join(parts)))

    async def _persist(self, result: SubagentResult) -> SubagentResult:
        """Write the result to the store and hand it back to the caller."""
        await self._store.put_result(result)
        return result
