"""Inference stream events, and the bounds one request may put on the completion it asks for."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from cortex_core.tools import ToolCall

# ``object`` values rather than ``Any``: the schema is passed to the model server unchanged
# and the core never reads inside it.
type JsonSchema = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TextChunk:
    """One delta of assistant reply text streamed from the model."""

    text: str


@dataclass(frozen=True, slots=True)
class ReasoningChunk:
    """One delta of a reasoning model's thinking trace (``reasoning_content``)."""

    text: str


@dataclass(frozen=True, slots=True)
class DecodeCadence:
    """How fast the server decoded one completion, as that server reports it."""

    tokens_per_second: float
    tokens: int

    def __post_init__(self) -> None:
        if self.tokens_per_second < 0:
            msg = f"DecodeCadence.tokens_per_second must be >= 0, got {self.tokens_per_second}"
            raise ValueError(msg)
        if self.tokens < 0:
            msg = f"DecodeCadence.tokens must be >= 0, got {self.tokens}"
            raise ValueError(msg)


class StopReason(Enum):
    """Why one completion ended, in this core's own vocabulary rather than an engine's."""

    FINISHED = "finished"
    CAPPED = "capped"
    CALLED = "called"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DecodeStop:
    """Why the server stopped decoding one completion, as that server reports it."""

    reason: StopReason


type InferenceEvent = TextChunk | ReasoningChunk | ToolCall | DecodeCadence | DecodeStop


@dataclass(frozen=True, slots=True)
class GenerationBounds:
    """How far one request lets the model go before it must answer."""

    max_tokens: int | None = None
    thinking: bool = True
    trace_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.max_tokens is not None and self.max_tokens < 1:
            msg = "max_tokens must be at least 1"
            raise ValueError(msg)
        if self.trace_tokens is not None and self.trace_tokens < 0:
            msg = "trace_tokens must not be negative"
            raise ValueError(msg)
