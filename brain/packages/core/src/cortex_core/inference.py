"""Inference stream events: what a backend yields while producing one completion.

A completion streams ``TextChunk`` (assistant text, emitted live) interleaved with
``ToolCall`` (the model asking to run a tool). Pure data with no ``ports`` import, so
``ports`` can name ``InferenceEvent`` in the ``InferenceBackend`` contract without a cycle,
mirroring how the ``tools`` and ``memory`` values are depended on.
"""

from dataclasses import dataclass

from cortex_core.tools import ToolCall


@dataclass(frozen=True, slots=True)
class TextChunk:
    """One delta of assistant text streamed from the model."""

    text: str


type InferenceEvent = TextChunk | ToolCall
