"""Inference stream events: what a backend yields while producing one completion.

A completion streams ``TextChunk`` (assistant reply text, emitted live) and, from a reasoning
model, ``ReasoningChunk`` (its private deliberation, emitted before the reply, ADR-0020),
interleaved with ``ToolCall`` (the model asking to run a tool). Pure data with no ``ports``
import, so ``ports`` can name ``InferenceEvent`` in the ``InferenceBackend`` contract without a
cycle, mirroring how the ``tools`` and ``memory`` values are depended on.
"""

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
