"""One placed attempt at a delegated task, and what it produced (ADR-0010/0012/0028).

Split out of ``runner.py`` so that file holds only the composition (resolve, admit, place, retry,
persist) and this one holds the run itself. The split exists because placement gained a second
attempt: ADR-0012 deferred, and ADR-0030 schedules, a **single CPU re-run after a GPU-placed
failure**, which needs "run once and say what happened" to be separable from "store the outcome".

So an attempt returns an ``AttemptOutcome`` rather than persisting a ``SubagentResult``. The
distinction that makes the re-run correct is ``AttemptFailure``: a backend that did not answer is
worth trying elsewhere, a model that answered outside its grammar is not, and keying the retry on
``ok is False`` would re-run a malformed envelope on the CPU for nothing.
"""

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
    """Why an attempt did not answer, or that it did. The retry decision reads exactly this.

    ``INFERENCE`` is the placed backend failing to answer (a dead ``llama-server``, a stream that
    died, a load that could not fit the GPU): the same task on another target may well succeed, so
    this is the only failure a re-place can help. ``MALFORMED`` is the model answering outside its
    constrained grammar, which is a property of the model and the prompt rather than of where it
    ran, so re-placing it would spend a second load to be told the same thing.
    """

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
    """Fold a GPU attempt that did not answer, plus its one CPU re-run, into one outcome.

    The re-run's text and failure win, because it is the attempt that actually ran to an answer
    (or to a second failure); the first attempt's partial text is dropped along with the context
    that produced it. The taint is the **union**: a first attempt that read untrusted content
    before its backend died did consume that content, and under-reporting taint is the one
    direction that costs safety rather than precision (ADR-0013).
    """
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
    """The ``reply`` string from a constrained envelope, or ``None`` if it is malformed.

    A constrained stream should always yield ``{"reply": "..."}``, but a mid-stream failure or a
    weak model that slips the grammar could leave a partial or wrong-shaped payload; that degrades
    to a ``MALFORMED`` outcome rather than reporting raw JSON as the answer. A non-object payload
    or a missing key raises (``TypeError``/``KeyError``), which is caught alongside a decode error.
    """
    try:
        reply = json.loads(text)["reply"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    return reply if isinstance(reply, str) else None


class PlacedAttempt:
    """Streams one task on one already-placed backend to an outcome, storing nothing.

    Holds only what every attempt of every task shares (the clock, the subagents' dispatcher, and
    whether a tool-less reply is constrained), so the runner can make two attempts of the same task
    on different backends from one instance.
    """

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
        """Stream ``task`` on ``backend`` as ``model`` and say what came back.

        Every attempt is a fresh function over the task: its own working set, taint ledger and
        fence nonce, so a re-run after a failed one inherits nothing from it. ``budget`` is the
        exception and deliberately so: it is the spawning turn's dispatch pool (ADR-0009 turn-wide
        addendum), a spend bound that a second attempt must keep spending from rather than reset.
        """
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
