"""Inference stream events, and the bounds one request may put on the completion it asks for.

A completion streams ``TextChunk`` (assistant reply text, emitted live) and, from a reasoning
model, ``ReasoningChunk`` (its private deliberation, emitted before the reply, ADR-0020),
interleaved with ``ToolCall`` (the model asking to run a tool). Pure data with no ``ports``
import, so ``ports`` can name ``InferenceEvent`` in the ``InferenceBackend`` contract without a
cycle, mirroring how the ``tools`` and ``memory`` values are depended on. ``GenerationBounds``
rides the same module for the same reason: it is request-side vocabulary the port names, like
``JsonSchema``.
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


@dataclass(frozen=True, slots=True)
class GenerationBounds:
    """How far one request lets the model go before it must answer (ADR-0020's deferred levers).

    Two knobs that only make sense together, which is why they are one value rather than two
    keywords. ``max_tokens`` caps what the server will decode for this request; ``thinking``
    ``False`` asks the chat template to skip the model's deliberation entirely. A reasoning model
    spends its budget on thinking *first*, so a cap without the switch does not shorten the reply,
    it deletes it: measured against the shipped cortex on a summarization prompt, ``max_tokens``
    160 and 256 with thinking on both came back ``finish_reason: "length"`` carrying 624 and 988
    characters of ``reasoning_content`` and an **empty** ``content``. Pairing them is what makes a
    cap sized from the wanted answer safe.

    The defaults are the deployment's own: no cap (llama-server's ``n_predict: -1``) and whatever
    the server's chat template does about thinking. So a caller that passes nothing gets the
    request this repo has always sent, byte for byte.
    """

    max_tokens: int | None = None
    thinking: bool = True

    def __post_init__(self) -> None:
        if self.max_tokens is not None and self.max_tokens < 1:
            msg = "max_tokens must be at least 1"
            raise ValueError(msg)
