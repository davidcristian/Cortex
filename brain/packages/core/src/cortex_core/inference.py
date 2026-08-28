"""Inference stream events, and the bounds one request may put on the completion it asks for.

A completion streams ``TextChunk`` (assistant reply text, emitted live) and, from a reasoning
model, ``ReasoningChunk`` (its private deliberation, emitted before the reply, ADR-0020), then a
``DecodeStop`` saying why it ended (ADR-0005 finish-reason addendum), a ``DecodeCadence`` when the
server told the adapter how fast it decoded (ADR-0030 spill-watch addendum), and last any
``ToolCall`` the model made, which is whole by the time it crosses and never precedes the words
beside it. Pure data with no ``ports``
import, so ``ports`` can name ``InferenceEvent`` in the ``InferenceBackend`` contract without a
cycle, mirroring how the ``tools`` and ``memory`` values are depended on. ``GenerationBounds``
rides the same module for the same reason: it is request-side vocabulary the port names, like
``JsonSchema``.
"""

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


class StopReason(Enum):
    """Why one completion ended, in this core's words rather than an engine's (ADR-0005
    finish-reason addendum).

    A closed set, because the wire value is llama.cpp's own vocabulary and the core must not
    depend on a backend's spelling; an adapter translates into these four and no others. A word
    no member covers arrives as ``UNKNOWN`` rather than as silence, so a reason nobody has taught
    this core yet can never be read as a model that finished.

    ``FINISHED`` is the model ending its own turn. ``CAPPED`` is a token limit ending it instead,
    which is the distinction this whole value exists for: a capped reply stops where the count ran
    out rather than where the answer did, so a reader who cannot see it mistakes a cut reply for a
    short one. Which limit is deliberately not part of the answer, a request's own ``max_tokens``
    and the server's context window being indistinguishable on the wire and equally cut.
    ``CALLED`` is the model stopping to call a tool, the ordinary end of every round of a tool
    loop but the last.
    """

    FINISHED = "finished"
    CAPPED = "capped"
    CALLED = "called"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DecodeStop:
    """Why the server stopped decoding one completion, as that server reports it (ADR-0005).

    Not a delta of anything, for ``DecodeCadence``'s reason: it arrives once, whole, at the end of
    the completion it describes, because why a completion ended is only knowable once it has. A
    backend whose engine says nothing about it emits none, and every consumer is written for that:
    the value is evidence when present and silence otherwise, and silence is never read as
    ``FINISHED``.

    It is its own event rather than a field on the closing cadence, though llama.cpp puts both on
    one chunk, because the two are separate facts with separate availability. A build that reports
    no ``timings`` still reports why it stopped, so a reason riding the cadence would be lost
    exactly where it was reported; and ``CadenceWatch``, which every loop hands its cadences to,
    answers a question about rates, so a non-rate fact reaching a consumer through it would arrive
    at a collaborator shaped for another question.
    """

    reason: StopReason


type InferenceEvent = TextChunk | ReasoningChunk | ToolCall | DecodeCadence | DecodeStop


@dataclass(frozen=True, slots=True)
class GenerationBounds:
    """How far one request lets the model go before it must answer (ADR-0020's deferred levers).

    Two knobs that only make sense together, which is why they are one value rather than two
    keywords. ``max_tokens`` caps what the server will decode for this request; ``thinking``
    ``False`` asks the deployment's chat template to skip the model's deliberation. A reasoning
    model spends its budget on thinking *first*, so a cap without the switch does not shorten the
    reply, it deletes it: measured against the shipped cortex on a summarization prompt,
    ``max_tokens`` 160 and 256 with thinking on both came back ``finish_reason: "length"`` carrying
    624 and 988 characters of ``reasoning_content`` and an **empty** ``content``.

    **``thinking`` is a request and not a guarantee** (ADR-0005 switch-is-advisory addendum). It
    renders as ``chat_template_kwargs: {"enable_thinking": false}``, which reaches a template this
    value knows nothing about, and whether the model then skips its trace was measured to depend on
    the shape of the request carrying it: on the shipped cortex pick the switch holds plain and
    constrained alike, and on the shipped subagent pick it holds on a plain request and is a coin
    toss on one carrying a ``response_format``, where the model deliberates through it on 4 draws
    in 5 and spends the whole cap doing so. The cause is a template this value cannot see: a
    ``response_format`` makes llama.cpp build a grammar that leaves the model's thought open, and
    only one of the two picks' templates has already closed it. So a cap sized from the wanted
    answer is made safe by neither this value nor the pick, but by a
    **bounded trace**, of which this switch is the cheapest source and not a dependable one. The
    dependable one is the tier's own ``--reasoning-budget`` (ADR-0005 trace-budget addendum), which
    ends the thought at the engine whatever the model wants, and which every subagent server this
    repo ships now carries at zero for exactly this reason.

    Nothing here can tell a caller which side its deployment is on, so two things say it instead:
    ``brain/packages/inference/tests/test_thinking_switch_live.py`` is the probe that answers it
    per request shape, and ``drain_text`` logs it when a request that asked for no thinking is
    answered with a trace anyway.

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
