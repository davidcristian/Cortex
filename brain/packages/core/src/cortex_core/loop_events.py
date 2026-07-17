"""The tool loop's yield vocabulary: what ``stream_tool_loop`` surfaces besides reply text."""

from dataclasses import dataclass

from cortex_core.tools import ToolSpec

# Upper bound on a ToolStep summary: the chip is one slim line, and an advertised description
# is sidecar-authored text of arbitrary length (ADR-0009 addendum).
MAX_STEP_SUMMARY_CHARS = 120


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """A delta of the model's reasoning trace, surfaced by the loop distinctly from reply text
    (ADR-0020).
    """

    text: str


@dataclass(frozen=True, slots=True)
class ToolStep:
    """One audited tool dispatch about to run, yielded by the loop immediately before the dispatch
    so a consumer can surface it while the tool works (ADR-0009 addendum).
    """

    tool_name: str
    summary: str


def step_summary(spec: ToolSpec) -> str:
    """The chip text for one dispatch: the advertised description's first line, capped, with
    the advertised name as the fallback when the description is empty.
    """
    description = spec.description.strip()
    line = description.splitlines()[0] if description else spec.name
    return line[:MAX_STEP_SUMMARY_CHARS]
