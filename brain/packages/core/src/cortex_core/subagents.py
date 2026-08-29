"""Subagent value types: the delegated task, the bounds one run gets, and its result.

Pure data, no I/O, see ADR-0010. These live here, importing no ports, so ``ports.py`` can depend
on them without a cycle exactly as ``tools.py`` and ``memory.py`` do. A subagent is a stateless
function over a ``TaskStore``: ``spawn_subagent`` writes a ``SubagentTask``, the runner reads it
back by id and writes a ``SubagentResult``, and the cortex reads the result. Nothing lives in a
model process.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SubagentTask:
    """One narrow task delegated to a subagent, persisted to the store before it runs.

    ``instruction`` is what to do; ``context`` is the material the subagent needs to work from
    the store alone (the cortex conversation is never shared, so the subagent is stateless over
    the task). ``at`` must be timezone-aware: task state outlives the process and any swap (the
    one hard rule), so a naive timestamp is ambiguous. ``model`` is the roster entry the cortex
    requested (``""`` = the default) and ``tainted`` whether the spawning turn had read untrusted
    content at spawn time (the two resolution inputs only the spawn site knows), riding on the
    record so the runner resolves safely from the store alone (ADR-0017/0018).

    ``session_id`` and ``turn_id`` are the spawning turn's attribution, written from the spawn
    dispatch's ``TurnStamp`` and read back by the runner, so this task's own tool calls are
    audited under the chat and the turn that asked for them (ADR-0009 named-work addendum;
    both ``""`` when nothing conversational spawned it, which is the schedule ticker's fire).
    ``item_id`` is the third and is that fire's own (ADR-0009 fired-work addendum): the
    scheduled item whose firing spawned this task, ``""`` for every spawn a conversation made,
    so a delegate's calls say which item they are the work of and a turn's delegate keeps
    saying honestly that no item is behind it.
    All three ride the record rather than the call for the reason everything else here does: a
    subagent is a stateless function over the store, so an attribution that lived only in a
    parameter would be lost by the first re-read (the one hard rule).
    """

    id: str
    instruction: str
    context: str
    at: datetime
    model: str = ""
    tainted: bool = False
    session_id: str = ""
    turn_id: str = ""
    item_id: str = ""

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.tzinfo.utcoffset(self.at) is None:
            msg = "SubagentTask.at must be timezone-aware"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AttemptBounds:
    """How far one placed attempt at a task may go before it must stop (ADR-0005 total-cap
    addendum).

    Two knobs that answer the same question in the two units a runaway can be measured in, and
    they are one value because a deployment that sets one and not the other has bounded half of
    the failure. ``max_tokens`` becomes the ``GenerationBounds.max_tokens`` of every completion
    the attempt asks for, so no single completion decodes forever; ``timeout_s`` is the deadline
    on the whole attempt, every completion and every tool dispatch between them, so the admission
    and the placement the attempt holds are released at a point in time rather than whenever the
    model happens to stop.

    Neither replaces the other. The token cap is what bounds a fast tier, where a deadline's worth
    of decoding is an essay; the deadline is what bounds a slow one, where the pool decodes at
    between 0.18 and 1.35 tok/s depending on what else the host is doing, which makes even a small
    token budget minutes of held admission.

    The defaults are ``None`` and ``None``, meaning no cap and no deadline, so an attempt built
    without bounds sends the request this repo has always sent and runs as long as it always did.
    A deployment's numbers arrive from ``SubagentsConfig`` at the composition root.
    """

    max_tokens: int | None = None
    timeout_s: float | None = None

    def __post_init__(self) -> None:
        if self.max_tokens is not None and self.max_tokens < 1:
            msg = f"AttemptBounds.max_tokens must be at least 1, got {self.max_tokens}"
            raise ValueError(msg)
        if self.timeout_s is not None and self.timeout_s <= 0:
            # Strictly positive rather than non-negative, unlike the admission wait, because the
            # two zeros would mean opposite things: a zero wait is "never queue", a policy a
            # deployment may want, while a zero deadline is "every attempt fails before it runs".
            msg = f"AttemptBounds.timeout_s must be > 0, got {self.timeout_s}"
            raise ValueError(msg)


# What an attempt built without a deployment's numbers runs under: no cap, no deadline. A shared
# frozen instance rather than a call in an argument default, the ``DEFAULT_DISPATCH_POLICY``
# precedent.
UNBOUNDED_ATTEMPT = AttemptBounds()

# The shipped numbers, declared here beside the value they fill and imported by
# ``SubagentsConfig`` rather than restated there, the ``DEFAULT_ADMISSION_WAIT_S`` precedent: one
# declaration is stronger than any scan tying two, and nothing outside this language spells either.
# Both derivations are measurements taken on the shipped CPU entry and are argued in full at the
# ADR-0005 total-cap addendum.
#
# The cap is roughly five times the longest reply a narrow subtask produced there, a
# summarization answering in 199 tokens where an extraction took 125 and a lookup 4. Sized from the
# answer rather than from the context, the way the recap fold's six times and the title's eight
# are: what makes a cap safe is that reaching it is itself the evidence, and a reply five times the
# longest one this tier has been measured writing is a model that is talking rather than working.
#
# Those five replies were all measured on the tools-enabled shape, and a subagents-only stack runs
# the constrained one, so the number is confirmed rather than derived on the shape that ships
# (ADR-0005 ceilings addendum). Forty draws of it answer in 256 to 429 tokens, the rule's five times
# would put the cap above the slot's own context, and the sentence above holds on this shape too:
# every run measured reaching this cap reached it on a narration or a reasoning trace and never on
# a long answer. Two bounds sit above it rather than the one this comment used to name, and the
# per-slot context is the looser: the run deadline below admits about 425 decoded tokens on a
# saturated host and about 3200 on an idle one, so on a busy box it is the deadline that fires
# first and this cap is out of reach.
#
# Which of the two binds is therefore not fixed, and this cap is deliberately ordered against
# nothing (ADR-0005 independence addendum). Two facts decide it and neither is visible to a
# validator: what else the host is doing, worth a factor of seven on this tier's measured decode
# rate, and whether the deployment gives its subagents tools, since this bound is spent per
# completion where the deadline is armed once around the whole attempt, so a tools-enabled run may
# spend this one every round. The conversion between a count and a time is the operator's, and the
# table for it is in that addendum.
DEFAULT_SUBAGENT_MAX_TOKENS = 1024
# The deadline is four times the longest whole subtask measured on that tier, the extra doubling
# covering a tool-using run whose loop spends that on several rounds where the measurement spent it
# on one. That subtask figure is an interval rather than a point, two sittings on one box reading
# 324.3 s and 623.8 s for the same shape, and the number below is four times the upper end. Taken
# from a full batch instead of from single subtasks it lands in the same place: the longest a spawn
# was measured holding its admission across a batch of eight is 595.2 s, and this is four times
# that. It also sits strictly between the two bounds either side of it, the pool's 600 s stall
# ceiling and its 7200 s admission wait, so the three are ordered by the scope of what they
# bound: one silent gap, then one whole run, then the queue for a run. ``SubagentsConfig`` refuses
# to start unless both of those orderings hold for the deployment's own numbers, the second of
# them skipped at a wait of zero, which is the policy of never queueing at all. Those two
# refusals are what hold this ordering, here and in the repo's own numbers: every bare
# construction of that class reads these three declarations, so a retune inverting either
# relation fails the orchestrator suite on the commit that types it.
#
# The cap above is the one neighbour this deadline is not ordered against, by decision rather than
# by oversight (ADR-0005 independence addendum). A time and a count are commensurable only through
# the tier's decode rate, which is measured rather than configured and moves by a factor of seven
# on one machine with nothing but the host's load changing, so a boot check would have to hold a
# hardware fact this process has no way to know. Both bounds refuse honestly whichever fires; what
# the ordering would buy is which diagnosis a reader gets, since nothing downstream branches on it.
DEFAULT_SUBAGENT_RUN_TIMEOUT_S = 2400.0

# How many attempts at one task fit inside one ``scheduler.admit``, which is what makes the queue
# ordering above a relation over twice the deadline rather than over the deadline. ``_placed``
# runs a placed attempt and, when a GPU-placed one comes back an inference failure, re-runs it once
# on the CPU inside the same admission under a deadline armed fresh (a re-run handed the remains of
# a spent deadline would be refused before it began). So a task can hold its room for this many
# whole deadlines, and the wait a peer will spend has to outlast that rather than one of them. The
# tie to the runner is not prose: ``test_runner.py`` drives the re-run path with a counting backend
# and asserts the attempts against this number and against the literal both.
ATTEMPTS_PER_ADMISSION = 2


@dataclass(frozen=True, slots=True)
class SubagentResult:
    """A subagent's outcome, persisted for the cortex to read.

    ``output`` is the answer text. ``ok`` is False when the subagent could not complete (e.g.
    its inference failed or the task vanished), ``detail`` carrying the reason. This mirrors
    ``ToolResult.is_error`` so a failed delegation is a value the cortex consumes, not a crash.
    ``tainted`` is True when the subagent consumed untrusted content (ADR-0013); the spawn tool
    aggregates it so a subagent that read a malicious file taints the cortex that spawned it.
    """

    task_id: str
    output: str
    ok: bool = True
    detail: str = ""
    tainted: bool = False
