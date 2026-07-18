"""One placed attempt at a delegated task, and what it produced (ADR-0010/0012/0028)."""

import json
from dataclasses import dataclass
from enum import Enum

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError
from cortex_core.events import ToolActivity
from cortex_core.inference import JsonSchema
from cortex_core.loop_events import ToolStep
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.progress import ProgressSink
from cortex_core.subagents import SubagentTask
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.untrusted import TaintLedger, new_nonce, security_preamble_message

# The fixed one-field reply envelope a constrained subagent is decoded into (ADR-0028): there is
# no grammatical position for an appended footer, link, or section, so a jailbroken weak model
# cannot format-launder. The attempt unwraps ``reply`` before reporting its text.
REPLY_ENVELOPE: JsonSchema = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}

MALFORMED_ENVELOPE_MSG = "subagent produced a malformed constrained reply"

# What the store records about a re-placed run. ADR-0030 asks for the re-place to be recorded in
# the result's detail, and a bare copy of either attempt's reason would hide that two loads were
# spent on one task, which is the whole thing an operator reading a slow spawn wants to see.
_RERAN_AND_ANSWERED = "the GPU attempt failed ({first}); re-ran on the CPU, which answered"
_RERAN_AND_FAILED = "the GPU attempt failed ({first}); the CPU re-run failed too ({second})"


class AttemptFailure(Enum):
    """Why an attempt did not answer, or that it did. The retry decision reads exactly this."""

    NONE = "none"
    INFERENCE = "inference"
    MALFORMED = "malformed"


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    """What one attempt produced: its text, why it failed if it did, and whether it read taint."""

    text: str
    failure: AttemptFailure = AttemptFailure.NONE
    detail: str = ""
    tainted: bool = False

    @property
    def ok(self) -> bool:
        """Whether this attempt answered, which is what the persisted result's ``ok`` becomes."""
        return self.failure is AttemptFailure.NONE


def reran_on_cpu(first: AttemptOutcome, retried: AttemptOutcome) -> AttemptOutcome:
    """Fold a GPU attempt that did not answer, plus its one CPU re-run, into one outcome."""
    detail = (
        _RERAN_AND_ANSWERED.format(first=first.detail)
        if retried.ok
        else _RERAN_AND_FAILED.format(first=first.detail, second=retried.detail)
    )
    return AttemptOutcome(
        text=retried.text,
        failure=retried.failure,
        detail=detail,
        tainted=first.tainted or retried.tainted,
    )


def task_messages(task: SubagentTask) -> list[Message]:
    """The subagent's prompt: the instruction as the user ask, context as system framing."""
    messages = [Message(role=Role.USER, text=task.instruction, at=task.at, turn_id=task.id)]
    if task.context:
        framing = Message(role=Role.SYSTEM, text=task.context, at=task.at, turn_id=task.id)
        messages.insert(0, framing)
    return messages


def _unwrap_envelope(text: str) -> str | None:
    """The ``reply`` string from a constrained envelope, or ``None`` if it is malformed."""
    try:
        reply = json.loads(text)["reply"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return reply if isinstance(reply, str) else None


class PlacedAttempt:
    """Streams one task on one already-placed backend to an outcome, storing nothing."""

    def __init__(
        self, clock: Clock, tools: ToolDispatcher | None, *, constrain_output: bool
    ) -> None:
        self._clock = clock
        self._tools = tools
        # Constrain a tool-less subagent's reply to the fixed envelope (ADR-0028), killing
        # format-laundering on the weak-model niche. Gated to the tool-less path below so the JSON
        # grammar never fights llama.cpp's tool-calling grammar (ADR-0028 decision 3).
        self._constrain_output = constrain_output

    async def run(
        self,
        task: SubagentTask,
        model: str,
        backend: InferenceBackend,
        *,
        budget: DispatchBudget | None,
        progress: ProgressSink | None,
    ) -> AttemptOutcome:
        """Stream ``task`` on ``backend`` as ``model`` and say what came back."""
        working = task_messages(task)
        # A tools-enabled subagent reads untrusted content too, so it gets the same standing rule
        # and its own taint ledger. A subagent that reads a malicious file taints its result,
        # which propagates to the cortex that spawned it (ADR-0013).
        if self._tools is not None:
            working.insert(0, security_preamble_message(task.at, task.id))
        # Structurally, `self._tools is None` is exactly the niche a weak model is reachable in
        # (ADR-0017), which is the niche the envelope defends.
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
            schema=REPLY_ENVELOPE if constrain else None,
            # A run with no spawning turn is its own root and gets the default allowance, as
            # every run did before the turn-wide pool existed.
            budget=DispatchBudget() if budget is None else budget,
        )
        parts: list[str] = []
        try:
            async for delta in stream_tool_loop(backend, model, working, context):
                if isinstance(delta, str):
                    parts.append(delta)
                elif isinstance(delta, ToolStep) and progress is not None:
                    await progress.emit(
                        ToolActivity(tool_name=delta.tool_name, summary=delta.summary)
                    )
        except InferenceError as err:
            return AttemptOutcome(
                text="".join(parts),
                failure=AttemptFailure.INFERENCE,
                detail=str(err),
                tainted=taint.tainted,
            )
        text = "".join(parts)
        if not constrain:
            return AttemptOutcome(text=text, tainted=taint.tainted)
        # Unwrap the envelope so the cortex sees an answer, never raw JSON (ADR-0028).
        reply = _unwrap_envelope(text)
        if reply is None:
            return AttemptOutcome(
                text=text,
                failure=AttemptFailure.MALFORMED,
                detail=MALFORMED_ENVELOPE_MSG,
                tainted=taint.tainted,
            )
        return AttemptOutcome(text=reply, tainted=taint.tainted)
