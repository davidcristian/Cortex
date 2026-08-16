"""One placed attempt at a delegated task, and what it produced (ADR-0010/0012/0028).

Split out of ``runner.py`` so that file holds only the composition (resolve, admit, place, retry,
persist) and this one holds the run itself. The split exists because placement gained a second
attempt: ADR-0012 deferred, and ADR-0030 schedules, a **single CPU re-run after a GPU-placed
failure**, which needs "run once and say what happened" to be separable from "store the outcome".

So an attempt returns an ``AttemptOutcome`` rather than persisting a ``SubagentResult``. That
outcome vocabulary (``AttemptFailure``, ``AttemptOutcome``, ``reran_on_cpu``, and every refusal
template a failed attempt reports as its ``detail``) is shared with the runner that reads it, so it
lives in ``subagent_outcome.py`` and is re-exported here, the ``tool_loop``/``ToolLoopContext``
precedent; this module owns the running.
"""

import asyncio
from contextlib import aclosing

from cortex_core.conversation import Message, Role
from cortex_core.dispatch import ToolDispatcher
from cortex_core.errors import InferenceError
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
from cortex_core.subagent_reply import REPLY_ENVELOPE, settle_reply, unwrap_envelope
from cortex_core.subagents import UNBOUNDED_ATTEMPT, AttemptBounds, SubagentTask
from cortex_core.tool_budget import DispatchBudget
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.untrusted import TaintLedger, new_nonce, security_preamble_message

# Re-exported so every existing `from cortex_core.subagent_attempt import ...` keeps resolving
# after the outcome and reply splits; neither vocabulary lives beside a single collaborator now.
__all__ = [
    "GENERATION_CAP_BOUND",
    "GENERATION_CAP_MSG",
    "GENERATION_DEADLINE_MSG",
    "INNER_TIMEOUT_MSG",
    "MALFORMED_ENVELOPE_MSG",
    "REPLY_ENVELOPE",
    "AttemptFailure",
    "AttemptOutcome",
    "PlacedAttempt",
    "cap_detail",
    "reran_on_cpu",
    "settle_reply",
    "task_messages",
    "unwrap_envelope",
]


def task_messages(task: SubagentTask) -> list[Message]:
    """The subagent's prompt: the instruction as the user ask, context as system framing."""
    messages = [Message(role=Role.USER, text=task.instruction, at=task.at, turn_id=task.id)]
    if task.context:
        framing = Message(role=Role.SYSTEM, text=task.context, at=task.at, turn_id=task.id)
        messages.insert(0, framing)
    return messages


class PlacedAttempt:
    """Streams one task on one already-placed backend to an outcome, storing nothing.

    Holds only what every attempt of every task shares (the clock, the subagents' dispatcher,
    whether a tool-less reply is constrained, and how far one attempt may go), so the runner can
    make two attempts of the same task on different backends from one instance.
    """

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
        # How far one attempt may go (ADR-0005 total-cap addendum). Shared across the runner's two
        # attempts and armed fresh for each: a re-run handed the remains of a spent deadline would
        # be refused before it began, turning the one transport failure a re-place exists for into
        # a certain one.
        self._bounds = bounds
        # The token half said in the port's own vocabulary, built once because it is the same
        # request shape for every completion of every attempt. ``thinking`` is left at its default,
        # which emits no key at all, so the pairing ADR-0038 insists on (a cap on a reasoning model
        # with thinking left ON deletes the reply rather than shortening it) is kept by the tier
        # rather than by this request: every subagent server this repo ships starts with
        # ``--chat-template-kwargs '{"enable_thinking": false}'`` (ADR-0010), and saying it again
        # per request would change the request for a deployment whose template spells the flag
        # differently.
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
        """Stream ``task`` on ``backend`` as ``model`` and say what came back.

        Every attempt is a fresh function over the task: its own working set, taint ledger and
        fence nonce, so a re-run after a failed one inherits nothing from it. ``budget`` is the
        exception and deliberately so: it is the spawning turn's dispatch pool (ADR-0009 turn-wide
        addendum), a spend bound that a second attempt must keep spending from rather than reset.

        The deadline is armed here, around the whole consumption, so it covers every completion
        and every tool dispatch between them: what an attempt holds while it runs is an admission
        slot, a placement and a model lease, and it holds all three across the tool loop rather
        than across one completion (ADR-0005 total-cap addendum). Reaching it is a ``TRUNCATED``
        outcome carrying the fragment produced so far, never an escaping exception, so a runaway
        arrives at the cortex through the very path a dead backend does.

        ``aclosing`` is the discipline ``tool_loop`` already applies to its own two generators,
        applied to it: the cancellation a deadline delivers lands wherever the task is suspended,
        and everywhere but one that is *inside* the loop generator, which therefore unwinds and
        runs every ``finally`` on the way out, the model lease released with them. The exception
        is a suspension in ``progress.emit`` below, where the loop generator is left at its yield
        instead, and closing it at a point in the code rather than at asynchronous-generator
        finalization is the same argument ``drain_text`` makes. Measured on this shape the two
        release identically, because the backend's own stream is closed by the loop before any
        step reaches that sink; what the wrapper buys is that the release stops depending on
        where the timer happened to fire.
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
        # Where each completion of this loop reports why it ended (ADR-0005 finish-reason
        # addendum). The cortex turn passes none, its reader watching the reply arrive; a
        # delegated reply is read as finished text by a model that never saw it stream, so a
        # completion cut at a token limit has to arrive as a refusal or it arrives as an answer.
        stops = StopLedger()
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
            stops=stops,
        )
        parts: list[str] = []
        # Only reply text joins the answer. A reasoning delta is ephemeral status (the subagent
        # tier runs thinking-off per ADR-0010, so none is expected, but drop one defensively). A
        # tool step is this subagent's audited dispatch about to run: it surfaces onto the spawning
        # stream's progress sink so the overlay's chip shows the delegated work (ADR-0010 progress
        # addendum), never joining the answer. Both of its fields are registry-authored (copied off
        # the matched ToolSpec), so no untrusted-derived text ever rides the sink and it needs no
        # guardrail pass, the same argument the cortex's own ToolActivity makes. A step outcome
        # (ADR-0029 outcome addendum) is dropped like a reasoning delta: it exists for the capture
        # indicator, which is a consent surface over a cortex-only built-in a subagent can never
        # call, so forwarding one would put an event on the seam with no consumer at either end,
        # and the sink it would ride drops on a full buffer, so the pairing it would claim is not
        # one this path can keep (ADR-0029 delegated-pairing addendum, where the decline is argued
        # and where the two lines that reverse it are named). Append text incrementally (not a
        # comprehension) so text produced before a mid-stream failure or a deadline survives.
        # Built before the ``try`` rather than bound by an ``as``, so the handler below can ask it
        # whether it was the thing that fired without depending on the block having been entered.
        # ``None`` is a bound of no bound, so an unbounded deployment takes this same path rather
        # than a branch of its own.
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
            # Only an expired deadline is this attempt's own bound. A ``TimeoutError`` from
            # anywhere else (a socket that timed out, a tool that raised one) is the backend not
            # answering, and calling it a truncation would blame a bound that had not fired, or
            # quote one an unbounded attempt does not have. Both arms sit ahead of the envelope
            # check below on purpose: a stop that lands mid-envelope would otherwise be reported
            # as a model breaking its grammar, sending the reader to the model rather than to
            # whatever actually stopped it.
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
        return settle_reply(
            "".join(parts),
            capped=stops.capped,
            max_tokens=self._bounds.max_tokens,
            constrain=constrain,
            tainted=taint.tainted,
        )
