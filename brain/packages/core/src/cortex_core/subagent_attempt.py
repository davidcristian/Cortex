"""One placed attempt at a delegated task, and what it produced (ADR-0010/0012/0028)."""

import asyncio
import json
from contextlib import aclosing

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError
from cortex_core.events import ToolActivity
from cortex_core.inference import GenerationBounds, JsonSchema
from cortex_core.loop_events import ToolStep
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.progress import ProgressSink
from cortex_core.subagent_outcome import AttemptFailure, AttemptOutcome, reran_on_cpu
from cortex_core.subagents import UNBOUNDED_ATTEMPT, AttemptBounds, SubagentTask
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.untrusted import TaintLedger, new_nonce, security_preamble_message

# Re-exported so every existing `from cortex_core.subagent_attempt import ...` keeps resolving
# after the outcome split; the vocabulary itself now lives beside neither collaborator.
__all__ = [
    "GENERATION_DEADLINE_MSG",
    "INNER_TIMEOUT_MSG",
    "MALFORMED_ENVELOPE_MSG",
    "REPLY_ENVELOPE",
    "AttemptFailure",
    "AttemptOutcome",
    "PlacedAttempt",
    "reran_on_cpu",
    "task_messages",
]

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

GENERATION_DEADLINE_MSG = (
    "the subtask was still generating after {timeout_s:g}s, the whole a delegated run is given, "
    "and was stopped where it stood; a run that reaches this bound is talking rather than "
    "working, so treat the subtask as unanswered and narrow it before delegating it again"
)

# What a bare ``TimeoutError`` from inside the run means, as opposed to the deadline above. A
# socket that timed out or a tool that raised one is the backend failing to answer, which is the
# retryable shape, so it is reported as one rather than as a bound this attempt never reached.
INNER_TIMEOUT_MSG = "the subtask timed out below the delegated run's own deadline"


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
        self,
        clock: Clock,
        tools: ToolDispatcher | None,
        *,
        constrain_output: bool,
        bounds: AttemptBounds = UNBOUNDED_ATTEMPT,
    ) -> None:
        self._clock = clock
        self._tools = tools
        # Constrain a tool-less subagent's reply to the fixed envelope (ADR-0028), killing
        # format-laundering on the weak-model niche. Gated to the tool-less path below so the JSON
        # grammar never fights llama.cpp's tool-calling grammar (ADR-0028 decision 3).
        self._constrain_output = constrain_output
        self._bounds = bounds
        self._generation = (
            None if bounds.max_tokens is None else GenerationBounds(max_tokens=bounds.max_tokens)
        )

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
            # How far each of this loop's completions may decode. The rounds cap and this one
            # multiply, so what they bound together is the attempt's decoding rather than one
            # completion's (ADR-0005 total-cap addendum).
            bounds=self._generation,
            # A run with no spawning turn is its own root and gets the default allowance, as
            # every run did before the turn-wide pool existed.
            budget=DispatchBudget() if budget is None else budget,
        )
        parts: list[str] = []
        deadline = asyncio.timeout(self._bounds.timeout_s)
        try:
            async with (
                deadline,
                aclosing(stream_tool_loop(backend, model, working, context)) as deltas,
            ):
                async for delta in deltas:
                    if isinstance(delta, str):
                        parts.append(delta)
                    elif isinstance(delta, ToolStep) and progress is not None:
                        await progress.emit(
                            ToolActivity(tool_name=delta.tool_name, summary=delta.summary)
                        )
        except TimeoutError:
            if not deadline.expired():
                return AttemptOutcome(
                    text="".join(parts),
                    failure=AttemptFailure.INFERENCE,
                    detail=INNER_TIMEOUT_MSG,
                    tainted=taint.tainted,
                )
            return AttemptOutcome(
                text="".join(parts),
                failure=AttemptFailure.TRUNCATED,
                detail=GENERATION_DEADLINE_MSG.format(timeout_s=self._bounds.timeout_s),
                tainted=taint.tainted,
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
