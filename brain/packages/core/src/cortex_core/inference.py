"""Inference stream events, and the bounds one request may put on the completion it asks for.

A completion streams ``TextChunk`` (assistant reply text, emitted live) and, from a reasoning
model, ``ReasoningChunk`` (its private deliberation, emitted before the reply, ADR-0020),
interleaved with ``ToolCall`` (the model asking to run a tool), and closes with a
``DecodeCadence`` when the server told the adapter how fast it decoded (ADR-0030 spill-watch
addendum). Pure data with no ``ports``
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


@dataclass(frozen=True, slots=True)
class DecodeCadence:
    """How fast the server decoded one completion, as that server reports it (ADR-0030).

    Not a delta of anything, which is why it is not a ``*Chunk``: it arrives once, whole, at the
    end of the completion it describes, because a rate is only knowable once the tokens are
    counted. A backend whose engine reports no such figure emits none, and every consumer is
    written for that: the value is evidence when present and silence otherwise, never a default.

    It exists because of the one failure this repo can produce and cannot see any other way. An
    overcommitted card does not refuse a load, it pages the excess to host memory and serves
    anyway, so both tiers report ``ready`` and ``nvidia-smi`` reads like a genuine fit; measured
    on the 24 GB card, a pair that fits and a pair 4676 MiB short read the same used and free
    memory and differ only here, the deep model decoding at 14.80 to 17.29 tok/s where it holds
    25.07 to 33.28 with the card to itself (docs/runbooks/model-swap.md).

    ``tokens`` is how many were decoded, and it is what makes the rate readable: a two-token
    completion's rate is dominated by whatever the server was doing when it started, so a
    consumer judges nothing on a sample too short to mean anything (``CadenceWatch``).
    """

    tokens_per_second: float
    tokens: int

    def __post_init__(self) -> None:
        if self.tokens_per_second < 0:
            msg = f"DecodeCadence.tokens_per_second must be >= 0, got {self.tokens_per_second}"
            raise ValueError(msg)
        if self.tokens < 0:
            msg = f"DecodeCadence.tokens must be >= 0, got {self.tokens}"
            raise ValueError(msg)


type InferenceEvent = TextChunk | ReasoningChunk | ToolCall | DecodeCadence


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
