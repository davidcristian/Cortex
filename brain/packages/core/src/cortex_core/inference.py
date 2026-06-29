"""Inference stream events: what a backend yields while producing one completion."""

from dataclasses import dataclass

from cortex_core.tools import ToolCall


@dataclass(frozen=True, slots=True)
class TextChunk:
    """One delta of assistant text streamed from the model."""

    text: str


type InferenceEvent = TextChunk | ToolCall
