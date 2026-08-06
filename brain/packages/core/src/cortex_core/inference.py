"""Inference stream events, and the bounds one request may put on the completion it asks for."""

from collections.abc import Mapping
from dataclasses import dataclass

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


type InferenceEvent = TextChunk | ReasoningChunk | ToolCall


@dataclass(frozen=True, slots=True)
class GenerationBounds:
    """How far one request lets the model go before it must answer (ADR-0020's deferred levers)."""

    max_tokens: int | None = None
    thinking: bool = True

    def __post_init__(self) -> None:
        if self.max_tokens is not None and self.max_tokens < 1:
            msg = "max_tokens must be at least 1"
            raise ValueError(msg)
