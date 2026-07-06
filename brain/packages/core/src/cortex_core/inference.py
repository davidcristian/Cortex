"""Inference stream events: what a backend yields while producing one completion."""

from dataclasses import dataclass

from cortex_core.tools import ToolCall


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
