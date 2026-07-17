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
"""

import json

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError, SubagentAdmissionError
from cortex_core.events import ToolActivity
from cortex_core.inference import JsonSchema
from cortex_core.ports import Clock, InferenceBackend, TaskStore
from cortex_core.progress import ProgressSink
from cortex_core.roster import SubagentResources, SubagentRoster
from cortex_core.subagents import SubagentResult, SubagentTask
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, ToolStep, stream_tool_loop
from cortex_core.untrusted import TaintLedger, new_nonce, security_preamble_message

# The fixed one-field reply envelope a constrained subagent is decoded into (ADR-0028): there is
# no grammatical position for an appended footer, link, or section, so a jailbroken weak model
# cannot format-launder. The runner unwraps ``reply`` before persisting the result.
_REPLY_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}

_MALFORMED_ENVELOPE_MSG = "subagent produced a malformed constrained reply"

# What the cortex reads when the scheduler refuses a spawn outright. Phrased like the
# dispatcher's refusal messages: say it was refused rather than attempted, and say what to do
# instead. Two causes reach here, and the reason carries which: the impossible charge (permanent,
# a resource-budget misconfiguration, ADR-0012 admission-wall addendum) and the drain window
# (transient, a model handoff quiescing the pool, ADR-0030). A transient full budget still
# queues, so this never means "busy, try later".
_REFUSED_TEMPLATE = (
    "refused before running: {reason}. The subtask was never attempted; answer without "
    "delegating this subtask, and say what you could not do."
)


def _task_messages(task: SubagentTask) -> list[Message]:
    """The subagent's prompt: the instruction as the user ask, context as system framing."""
    messages = [Message(role=Role.USER, text=task.instruction, at=task.at, turn_id=task.id)]
    if task.context:
        framing = Message(role=Role.SYSTEM, text=task.context, at=task.at, turn_id=task.id)
        messages.insert(0, framing)
    return messages


def _unwrap_envelope(text: str) -> str | None:
    """The ``reply`` string from a constrained envelope, or ``None`` if it is malformed.

    A constrained stream should always yield ``{"reply": "..."}``, but a mid-stream failure or a
    weak model that slips the grammar could leave a partial or wrong-shaped payload; that degrades
    to an ``ok=False`` result rather than persisting raw JSON as the answer. A non-object payload
    or a missing key raises (``TypeError``/``KeyError``), which is caught alongside a decode error.
    """
    try:
        reply = json.loads(text)["reply"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return reply if isinstance(reply, str) else None


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
    ) -> None:
        self._store = store
        self._roster = roster
        self._clock = clock
        self._tools = tools
        # Constrain a tool-less subagent's reply to the fixed envelope (ADR-0028), killing
        # format-laundering on the weak-model niche. Gated to the tool-less path in `_run_placed`
        # so the JSON grammar never fights llama.cpp's tool-calling grammar (ADR-0028 decision 3).
        self._constrain_output = constrain_output

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
        does a spawn the scheduler refuses outright (a charge no budget could ever fit, or a pool
        draining for a model handoff, ADR-0030).

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
                placement = res.placer.place(res.request)
                try:
                    return await self._run_placed(
                        task,
                        res,
                        res.backends[placement.target],
                        budget=budget,
                        progress=progress,
                    )
                finally:
                    res.placer.release(placement)
        except SubagentAdmissionError as err:
            # The scheduler's refusals: the impossible charge (ADR-0012 admission-wall addendum)
            # and the drain window of a model handoff (ADR-0030). Only `admit` raises it
            # (neither the placer nor the tool loop touches a scheduler), and it does so before
            # yielding, so nothing was placed or run. Degrading it to a value here keeps the
            # runner's contract that every outcome is a `SubagentResult`: an escaping exception
            # would cross the spawn tool, which only `ToolError` is caught past, and fail the
            # whole turn, discarding the batch's other subagents along with it.
            return await self._failed(task_id, _REFUSED_TEMPLATE.format(reason=err))

    async def _run_placed(
        self,
        task: SubagentTask,
        res: SubagentResources,
        backend: InferenceBackend,
        *,
        budget: DispatchBudget | None,
        progress: ProgressSink | None,
    ) -> SubagentResult:
        """Stream the loaded task to a persisted result on the placed backend."""
        working = _task_messages(task)
        # A tools-enabled subagent reads untrusted content too, so it gets the same standing rule
        # and its own taint ledger. A subagent that reads a malicious file taints its result,
        # which propagates to the cortex that spawned it (ADR-0013).
        if self._tools is not None:
            working.insert(0, security_preamble_message(task.at, task.id))
        # Constrain output only on the tool-less path (ADR-0028 decision 3): a tools-enabled
        # subagent is already forced to the robust model and would make the JSON envelope fight
        # llama.cpp's tool-calling grammar. Structurally, `self._tools is None` is exactly the
        # niche a weak model is reachable (ADR-0017).
        constrain = self._tools is None and self._constrain_output
        taint = TaintLedger()
        context = ToolLoopContext(
            dispatcher=self._tools,
            clock=self._clock,
            turn_id=task.id,
            taint=taint,
            nonce=new_nonce(),
            # A subagent run has no originating chat of its own: SubagentTask carries no
            # session, and the only session_id consumer is cortex-only by construction
            # (ADR-0027). The field grows onto the task when a consumer exists.
            session_id="",
            schema=_REPLY_ENVELOPE if constrain else None,
            # The spawning turn's pool when there is one, so this run's dispatches count
            # against the turn's total (ADR-0009 turn-wide addendum). A run with no spawning
            # turn is its own root and gets the default allowance, as every run did before.
            budget=DispatchBudget() if budget is None else budget,
        )
        parts: list[str] = []
        try:
            async for delta in stream_tool_loop(backend, res.request.model, working, context):
                # Only reply text joins the answer. A reasoning delta is ephemeral status (the
                # subagent tier runs thinking-off per ADR-0010, so none is expected, but drop one
                # defensively). A tool step is this subagent's audited dispatch about to run: it
                # surfaces onto the spawning stream's progress sink so the overlay's chip shows
                # the delegated work (ADR-0010 progress addendum), never joining the answer. Both
                # of its fields are registry-authored (copied off the matched ToolSpec), so no
                # untrusted-derived text ever rides the sink and it needs no guardrail pass, the
                # same argument the cortex's own ToolActivity makes. Append text incrementally
                # (not a comprehension) so text produced before a mid-stream failure survives.
                if isinstance(delta, str):
                    parts.append(delta)
                elif isinstance(delta, ToolStep) and progress is not None:
                    await progress.emit(
                        ToolActivity(tool_name=delta.tool_name, summary=delta.summary)
                    )
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
        text = "".join(parts)
        if constrain:
            # Unwrap the envelope so the cortex sees an answer, never raw JSON (ADR-0028). A
            # malformed payload (a slipped grammar, a partial stream) degrades to ok=False.
            reply = _unwrap_envelope(text)
            if reply is None:
                return await self._persist(
                    SubagentResult(
                        task_id=task.id,
                        output=text,
                        ok=False,
                        detail=_MALFORMED_ENVELOPE_MSG,
                        tainted=taint.tainted,
                    )
                )
            text = reply
        return await self._persist(
            SubagentResult(task_id=task.id, output=text, tainted=taint.tainted)
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
