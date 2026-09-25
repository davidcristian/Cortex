"""One placed attempt at a delegated task, and what it produced."""

import asyncio
from contextlib import aclosing

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError, MalformedToolCallError
from cortex_core.events import ToolActivity
from cortex_core.inference import GenerationBounds
from cortex_core.loop_events import ToolStep
from cortex_core.ports import Clock, InferenceBackend
from cortex_core.progress import ProgressSink
from cortex_core.stops import StopLedger
from cortex_core.subagent_outcome import (
    GENERATION_CAP_BOUND,
    GENERATION_CAP_MSG,
    GENERATION_DEADLINE_MSG,
    INNER_TIMEOUT_MSG,
    MALFORMED_ENVELOPE_MSG,
    AttemptFailure,
    AttemptOutcome,
    cap_detail,
    reran_on_cpu,
)
from cortex_core.subagent_reply import (
    REPLY_ENVELOPE,
    REPLY_INSTRUCTION,
    instruct_reply,
    settle_reply,
    unwrap_envelope,
)
from cortex_core.subagents import UNBOUNDED_ATTEMPT, AttemptBounds, SubagentTask
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.untrusted import TaintLedger, new_nonce, security_preamble_message

__all__ = [
    "GENERATION_CAP_BOUND",
    "GENERATION_CAP_MSG",
    "GENERATION_DEADLINE_MSG",
    "INNER_TIMEOUT_MSG",
    "MALFORMED_ENVELOPE_MSG",
    "REPLY_ENVELOPE",
    "REPLY_INSTRUCTION",
    "AttemptFailure",
    "AttemptOutcome",
    "PlacedAttempt",
    "cap_detail",
    "instruct_reply",
    "reran_on_cpu",
    "settle_reply",
    "task_messages",
    "unwrap_envelope",
]


def task_messages(task: SubagentTask, *, constrain: bool) -> list[Message]:
    """The subagent's prompt: the instruction as the user ask, context as system framing."""
    asked = instruct_reply(task.instruction) if constrain else task.instruction
    messages = [Message(role=Role.USER, text=asked, at=task.at, turn_id=task.id)]
    if task.context:
        framing = Message(role=Role.SYSTEM, text=task.context, at=task.at, turn_id=task.id)
        messages.insert(0, framing)
    return messages


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
        constrain = self._tools is None and self._constrain_output
        working = task_messages(task, constrain=constrain)
        if self._tools is not None:
            working.insert(0, security_preamble_message(task.at, task.id))
        # The task's context can quote untrusted text, so a tainted task's attempt starts tainted.
        taint = TaintLedger(tainted=task.tainted)
        stops = StopLedger()
        context = ToolLoopContext(
            dispatcher=self._tools,
            clock=self._clock,
            turn_id=task.turn_id,
            taint=taint,
            nonce=new_nonce(),
            session_id=task.session_id,
            task_id=task.id,
            item_id=task.item_id,
            schema=REPLY_ENVELOPE if constrain else None,
            bounds=self._generation,
            budget=DispatchBudget() if budget is None else budget,
            stops=stops,
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
        except MalformedToolCallError as err:
            # A tool call the model was still writing when a token limit ended the completion is
            # a truncation, not a bad reply, so the ledger decides which of the two this is.
            if not stops.capped:
                return AttemptOutcome(
                    text="".join(parts),
                    failure=AttemptFailure.INFERENCE,
                    detail=str(err),
                    tainted=taint.tainted,
                )
            return AttemptOutcome(
                text="".join(parts),
                failure=AttemptFailure.TRUNCATED,
                detail=cap_detail(self._bounds.max_tokens),
                tainted=taint.tainted,
            )
        except InferenceError as err:
            return AttemptOutcome(
                text="".join(parts),
                failure=AttemptFailure.INFERENCE,
                detail=str(err),
                tainted=taint.tainted,
            )
        return settle_reply(
            "".join(parts),
            capped=stops.capped,
            max_tokens=self._bounds.max_tokens,
            constrain=constrain,
            tainted=taint.tainted,
        )
