"""What ``stream_tool_loop`` yields besides reply text."""

from dataclasses import dataclass

from cortex_core.tools import ToolSpec

MAX_STEP_SUMMARY_CHARS = 120


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    """A piece of the model's reasoning trace, yielded separately from reply text."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolStep:
    """One audited tool dispatch about to run, yielded just before it runs."""

    tool_name: str
    summary: str


@dataclass(frozen=True, slots=True)
class StepOutcome:
    """How one announced dispatch ended, yielded as soon as it finishes."""

    tool_name: str
    ok: bool


def step_summary(spec: ToolSpec) -> str:
    """The short label for one dispatch: the description's first line, truncated, or the name."""
    description = spec.description.strip()
    line = description.splitlines()[0] if description else spec.name
    return line[:MAX_STEP_SUMMARY_CHARS]
