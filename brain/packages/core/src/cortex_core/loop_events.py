"""The tool loop's yield vocabulary: what ``stream_tool_loop`` surfaces besides reply text.

Split from ``tool_loop.py`` at the 300-line cap when the escalation slot threading landed
(ADR-0030); the contract is unchanged. The loop yields ``str`` (reply text), ``ReasoningDelta``
(ADR-0020), or ``ToolStep`` (ADR-0009 addendum); this module owns the two event values and the
registry-authored chip text, and ``tool_loop.py`` owns running the loop that yields them.
"""

from dataclasses import dataclass

from cortex_core.tools import ToolSpec

# Upper bound on a ToolStep summary: the chip is one slim line, and an advertised description
# is sidecar-authored text of arbitrary length (ADR-0009 addendum).
MAX_STEP_SUMMARY_CHARS = 120


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """A delta of the model's reasoning trace, surfaced by the loop distinctly from reply text
    (ADR-0020). The loop's yield vocabulary is ``str`` (reply text), ``ReasoningDelta``, or
    ``ToolStep``: reply text accumulates into the answer and is persisted, a reasoning delta is
    ephemeral status and is never added to the assistant message nor fed back into the context.
    """

    text: str


@dataclass(frozen=True, slots=True)
class ToolStep:
    """One audited tool dispatch about to run, yielded by the loop immediately before the
    dispatch so a consumer can surface it while the tool works (ADR-0009 addendum). Ephemeral
    like ``ReasoningDelta``: the cortex engine maps it to the domain ``ToolActivity`` event,
    a subagent drops it. Both fields are copied straight off the advertised ``ToolSpec``
    (``tool_name`` is ``spec.name``, ``summary`` is ``step_summary``): nothing the model
    authored, neither the call name nor its arguments, ever rides this event.
    """

    tool_name: str
    summary: str


def step_summary(spec: ToolSpec) -> str:
    """The chip text for one dispatch: the advertised description's first line, capped, with
    the advertised name as the fallback when the description is empty.

    Registry-authored by construction, because a ``ToolStep`` is only yielded for a call that
    matched an advertised spec (``stream_tool_loop``). The model's call name and arguments
    never reach it: a value the model authored would be a display channel the reply-side
    guardrail (ADR-0015) never inspects, exactly the laundering surface this event must not open.
    """
    description = spec.description.strip()
    line = description.splitlines()[0] if description else spec.name
    return line[:MAX_STEP_SUMMARY_CHARS]
