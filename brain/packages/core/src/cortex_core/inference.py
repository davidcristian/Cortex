"""Inference stream events, and the bounds one request may put on the completion it asks for."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from cortex_core.tools import ToolCall

# A JSON Schema handed to the backend for constrained decoding (ADR-0028). Open-shaped like a
# tool's parameters, so the value is round-tripped to the model server, never introspected by
# the core; ``object`` values keep it free of an unjustified ``Any``.
type JsonSchema = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TextChunk:
    """One delta of assistant reply text streamed from the model."""

    text: str


@dataclass(frozen=True, slots=True)
class ReasoningChunk:
    """One delta of a reasoning model's thinking trace (``reasoning_content``, ADR-0020).

    Ephemeral: surfaced as live status while the model thinks, never part of the persisted
    reply and never fed back into the model's context on a later tool-loop step.
    """

    text: str


@dataclass(frozen=True, slots=True)
class DecodeCadence:
    """How fast the server decoded one completion, as that server reports it (ADR-0030)."""

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
    """Why one completion ended, in this core's words rather than an engine's (ADR-0005
    finish-reason addendum).
    """

    FINISHED = "finished"
    CAPPED = "capped"
    CALLED = "called"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DecodeStop:
    """Why the server stopped decoding one completion, as that server reports it (ADR-0005)."""

    reason: StopReason


type InferenceEvent = TextChunk | ReasoningChunk | ToolCall | DecodeCadence | DecodeStop


@dataclass(frozen=True, slots=True)
class GenerationBounds:
    """How far one request lets the model go before it must answer (ADR-0020's deferred levers)."""

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
