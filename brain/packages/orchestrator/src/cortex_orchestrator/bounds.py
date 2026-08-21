"""The orderings between bounds that no single settings class can check for itself.

A bound this deployment sets is usually validated where it is declared: ``ToolsConfig`` refuses a
price outside the dispatch budget, ``SubagentsConfig`` refuses a run deadline that does not outlast
its own stall ceiling, and each is a relation between fields one class can see. A few relations are
not like that. They hold between numbers **two** settings classes declare, so neither class can
express one, and the comparison belongs at the composition root that reads both.

That is the same argument ``check_control_deadline`` (``swap_builders.py``) makes for a pairing
that spans two containers' env, and this module is its twin for pairings that span two config
classes in one process. It builds nothing and holds nothing: each check takes the config objects,
compares, and hands one straight back so the root gates on the way through rather than holding an
unchecked one for a statement. A module of its own rather than a corner of ``builders.py``, because
a builder returns an adapter plus the coroutine that releases it and none of this does either.
"""

import logging

from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.config_tools import ToolsConfig

__all__ = ["ToolCallDeadlineError", "check_tool_call_deadline", "delegated_call_bounds"]

_logger = logging.getLogger(__name__)


class ToolCallDeadlineError(RuntimeError):
    """The bound on one tool call does not fit inside the delegated run that has to contain it."""


def delegated_call_bounds(tools: ToolsConfig) -> int:
    """How many whole call bounds one delegated dispatch can spend, the run's own listing included.

    **The bound is spent per walk, not per dispatch**, which is what makes a bare comparison of the
    two numbers wrong rather than merely loose. Every one of these reaches
    ``BoundedToolRegistry`` separately and every one of them can find a wedged sidecar:

    - the run's **advertisement**, one walk, which ``stream_tool_loop`` makes once before its
      rounds;
    - the **gated strip**, one walk, which ``UngatedToolRegistry.invoke`` makes live on every
      delegated dispatch, deliberately uncached so a re-flagged tool fails closed;
    - the **routing walk**, one more, which ``AggregateToolRegistry.invoke`` makes to find which
      registry owns the name, and which does not exist at all with a single endpoint, that being
      composed as itself rather than behind an aggregate;
    - the **call**.

    A walk costs one bound per wedged sidecar it lists, since
    ``SkipUnavailableToolRegistry`` catches each overrun and carries on, so the ceiling on a walk
    is the endpoint count and the ceiling here is that count times the walks plus the call. It is
    an **upper bound and is meant to be**: the ``fail`` policy aborts a walk at the first overrun,
    and one wedged sidecar among healthy ones costs one bound a walk rather than several. Measured
    against the real composition at 60 s and one endpoint, a delegated dispatch spends the bound
    twice and the advertisement before it once more, which is this function's 3.

    **What it does not cover, deliberately.** A run makes many dispatches over many rounds, so this
    is what the *first* wedged dispatch costs and never what a whole run can. Bounding the run's
    worst case would mean multiplying by ``MAX_TOOL_DISPATCHES`` as well, which the shipped pair
    does not clear and which would refuse deployments that work: the failure this exists to prevent
    is a run cut *mid call*, reported as a subtask that would not stop talking, and for that the
    model has to reach the tool error at all.
    """
    sidecars = len(tools.named_endpoints)
    walks = 2 if sidecars == 1 else 3
    return walks * sidecars + 1


def check_tool_call_deadline(subagents: SubagentsConfig, tools: ToolsConfig) -> SubagentsConfig:
    """Refuse a deployment whose tool call may be bounded above the run that contains it.

    ``CORTEX_TOOLS_CALL_TIMEOUT_S`` is a fourth bound on a delegated run, beside the three
    ``SubagentsConfig`` declares. Those three nest by the scope each bounds, one silent gap inside
    one whole run inside the queue for a run; this one is the innermost's sibling rather than its
    child, bounding one tool dispatch where the stall ceiling bounds one silent read, and both of
    them sit inside the run. The run outlasting the stall ceiling is refused at boot already. This
    one was related to nothing.

    **Measured, not reasoned.** With the pair the right way round, a wedged sidecar loses one call
    at the bound, the ``ToolError`` becomes the ``is_error`` result the loop recovers from, and the
    subtask still answers. With the pair inverted, the run's own deadline fires first and the whole
    delegated run comes back ``TRUNCATED`` with no text at all, under a detail saying the subtask
    "was still generating" and should be narrowed before it is delegated again. That sends the
    reader to the model and the instruction when the cause was a sidecar two knobs away, and it
    skips the CPU re-run as well, a truncation being deliberately never re-placed. So the bound
    that exists to make a wedge survivable is deleted for delegated work by a pair nothing checks.

    **Refused rather than clamped or logged.** A clamp would retune a number the operator typed,
    and would have to pick which one: lowering the call bound to meet the run bound leaves them
    equal, which is the race the strictness below exists to avoid, and raising the run bound spends
    more of the user's wall clock and holds a model lease longer than the deployment asked. A
    warning would leave the misordering running, so the failure still arrives, wearing the wrong
    diagnosis; a boot line nobody greps is exactly as invisible as the knob it describes. The one
    place a warning is right is where ``check_control_deadline`` puts one, a far side that cannot
    be **asked**, and both numbers here are this process's own env, always readable.

    **What is compared is the dispatch, not the bound.** A single call bound under the run bound
    is not enough, because one dispatch spends that bound several times over:
    ``delegated_call_bounds`` above says how many, and it is that product the run deadline has to
    outlast. Comparing the bare numbers under-protects the very path this exists for by at least
    twice, and by more with a second sidecar: ``CORTEX_TOOLS_CALL_TIMEOUT_S=700`` under
    ``CORTEX_SUBAGENTS_RUN_TIMEOUT_S=900`` passes every validator, and then one wedged sidecar
    spends 1400 s inside a run allowed 900, which is verbatim the outcome below. Refused, that pair
    fails at boot instead.

    **Strictly under**, the ``ControlBounds.clears`` rule: a dispatch allowed the whole of the run
    would leave which bound fires a race, and the expensive side of that race is the one reporting
    a wedge as a runaway. Compared only when both capabilities are on, the shape of
    ``check_control_deadline`` returning early for a deployment that never escalates: without
    ``mcp`` no ``BoundedToolRegistry`` is built, and without a delegation backend there is no run
    for a call to sit inside. The cortex's own loop is deliberately not in the series, a
    ``Converse`` turn announcing no deadline for its calls to be ordered against (ADR-0024).

    **What a passing check does and does not promise.** It promises that the first wedged dispatch
    of a delegated run reaches the loop as a ``ToolError`` rather than being cut mid call by the
    run's own deadline, which is the difference between a subtask that reports a broken sidecar and
    a run reported ``TRUNCATED`` for reasons that point at the model. It promises nothing about the
    run finishing: a run may dispatch many times, and the arithmetic that would cover all of them
    is in ``delegated_call_bounds``, along with why it is not the one used here.

    Gated at the env read, before anything at all is built, so a refusal releases nothing: earlier
    than the control deadline's own check, which has a runtime to close first because asking the
    far side is what tells it there is a fault.
    """
    if tools.backend != "mcp" or subagents.backend != "llamacpp":
        return subagents
    if _dispatch_cost(tools) < subagents.run_timeout_s:
        # The numbers ride the record alone, the shipped formatter appending whatever a record
        # carries; the refusal below is the one place they stay in the prose, being read where no
        # formatter runs.
        _logger.info(
            "the delegated run's deadline outlasts one wedged tool dispatch",
            extra=_pairing(subagents, tools),
        )
        return subagents
    msg = (
        f"CORTEX_TOOLS_CALL_TIMEOUT_S is {tools.call_timeout_s} s and one delegated dispatch can "
        f"spend it {delegated_call_bounds(tools)} times over across "
        f"{len(tools.named_endpoints)} configured sidecar(s), so {_dispatch_cost(tools)} s, while "
        f"CORTEX_SUBAGENTS_RUN_TIMEOUT_S is {subagents.run_timeout_s} s: one wedged tool call can "
        "outlast the whole delegated run that has to contain it, the run's deadline fires first, a "
        "stalled sidecar is reported as a subtask that would not stop talking, and the re-run a "
        "transport failure earns is skipped. Lower the call bound, or raise the run bound above "
        "the dispatch (docs/runbooks/tools-mcp.md)"
    )
    _logger.error(msg, extra=_pairing(subagents, tools))
    raise ToolCallDeadlineError(msg)


def _dispatch_cost(tools: ToolsConfig) -> float:
    """What one wedged delegated dispatch costs in seconds: the bound times its own multiple."""
    return delegated_call_bounds(tools) * tools.call_timeout_s


def _pairing(subagents: SubagentsConfig, tools: ToolsConfig) -> dict[str, float]:
    """The numbers as record fields, built once so both lines carry the same set.

    The multiple rides along with the two bounds, because it is the term that makes the comparison
    say something a reader cannot recompute from the pair: the same 60 s under the same 2400 s is
    a different amount of headroom with a second sidecar configured.
    """
    return {
        "call_timeout_s": tools.call_timeout_s,
        "call_bounds_per_dispatch": delegated_call_bounds(tools),
        "dispatch_timeout_s": _dispatch_cost(tools),
        "run_timeout_s": subagents.run_timeout_s,
    }
