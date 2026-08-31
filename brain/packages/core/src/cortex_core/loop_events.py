"""The tool loop's yield vocabulary: what ``stream_tool_loop`` surfaces besides reply text.

Split from ``tool_loop.py`` at the 300-line cap when the escalation slot threading landed
(ADR-0030); the contract is unchanged. The loop yields ``str`` (reply text), ``ReasoningDelta``
(ADR-0020), ``ToolStep`` (ADR-0009 addendum), or ``StepOutcome`` (ADR-0029 outcome addendum);
this module owns the three event values and the registry-authored chip text, and
``tool_loop.py`` owns running the loop that yields them.
"""

from dataclasses import dataclass

from cortex_core.tools import ToolSpec

# Upper bound on a ToolStep summary: the chip is one slim line, and an advertised description
# is sidecar-authored text of arbitrary length (ADR-0009 addendum).
MAX_STEP_SUMMARY_CHARS = 120


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """A delta of the model's reasoning trace, yielded separately from reply text (ADR-0020).

    The loop's yield vocabulary is ``str`` (reply text), ``ReasoningDelta``, or ``ToolStep``:
    reply text accumulates into the answer and is persisted, while a reasoning delta is ephemeral
    status and is never added to the assistant message nor fed back into the context.
    """

    text: str


@dataclass(frozen=True, slots=True)
class ToolStep:
    """One audited tool dispatch about to run, yielded just before the dispatch (ADR-0009).

    A consumer can surface it while the tool works. Ephemeral like ``ReasoningDelta``: the cortex
    engine maps it to the domain ``ToolActivity`` event and a subagent drops it. Both fields are
    copied straight off the advertised ``ToolSpec`` (``tool_name`` is ``spec.name``, ``summary``
    is ``step_summary``), so nothing the model authored, neither the call name nor its arguments,
    ever rides this event.
    """

    tool_name: str
    summary: str


@dataclass(frozen=True, slots=True)
class StepOutcome:
    """How one announced dispatch ended, yielded as soon as it resolves (ADR-0029 outcome).

    The other half of ``ToolStep``: the loop yields exactly one of these per ``ToolStep`` it
    yielded, on every path out of the dispatch, so a consumer that showed something on the step
    has something to clear it with.

    ``tool_name`` is the same registry-authored ``spec.name`` the step carried. ``ok`` is the
    audit trail's own value (``ToolInvocation.ok``, the negation of the result's ``is_error``),
    read off the same result the audit line was written from, so a display surface and the audit
    log cannot disagree about one dispatch. It is a bit rather than a reason because the gate
    denials and the tool's own failures differ in what the model is told and not in what a consent
    surface may claim, and a reason nothing renders would be a wire vocabulary with no consumer.

    Ephemeral like ``ToolStep``: never reply text, never persisted, never fed back to the model.
    """

    tool_name: str
    ok: bool


def step_summary(spec: ToolSpec) -> str:
    """The chip text for one dispatch: the description's first line, capped, or else the name.

    The advertised name is the fallback when the advertised description is empty. The text is
    registry-authored by construction, because a ``ToolStep`` is only yielded for a call that
    matched an advertised spec (``stream_tool_loop``). The model's call name and arguments
    never reach it: a value the model authored would be a display channel the reply-side
    guardrail (ADR-0015) never inspects, exactly the laundering surface this event must not open.
    """
    description = spec.description.strip()
    line = description.splitlines()[0] if description else spec.name
    return line[:MAX_STEP_SUMMARY_CHARS]
