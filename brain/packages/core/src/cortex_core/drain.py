"""Run one model call to its end and let go of the GPU, deterministically (ADR-0038 decision 8).

The GPU lease is a non-reentrant ``asyncio.Lock`` (``model.py``) that an inference adapter holds for
its stream generator's whole lifetime (``backend.py``), so a stream left un-closed leaves the lock
held until asynchronous-generator finalization gets around to it. That is fine when a stream is
consumed to exhaustion on the happy path, and it is exactly not fine when something raises partway
through: the turn that spawned the call then waits on a lease nobody is using.

``TurnEngine.handle_turn`` already knows the answer for its own event stream (``await
events.aclose()`` in a ``finally``); this is that discipline for a one-shot model call, so every
in-turn side call (the session title, a model-based recall rank) releases the lease at a point in
the code rather than at the mercy of the collector.
"""

import logging
from collections.abc import AsyncGenerator, Sequence

from cortex_core.conversation import Message
from cortex_core.inference import (
    DecodeStop,
    GenerationBounds,
    JsonSchema,
    ReasoningChunk,
    TextChunk,
)
from cortex_core.ports import InferenceBackend
from cortex_core.stops import StopLedger

_logger = logging.getLogger(__name__)


async def drain_text(
    backend: InferenceBackend,
    model: str,
    messages: Sequence[Message],
    *,
    schema: JsonSchema | None = None,
    bounds: GenerationBounds | None = None,
    stops: StopLedger | None = None,
) -> str:
    """Consume one completion to its end, closing the stream whatever happens, and join its text.

    Only assistant text (``TextChunk``) contributes: a reasoning model's ``ReasoningChunk``, any
    ``ToolCall``, and the closing ``DecodeCadence`` are dropped, so a caller gets the reply and
    never the private thinking. A side call's decode rate is dropped rather than watched because
    it runs on whichever tier the turn is already on, so it says nothing about a swap. ``schema``
    constrains decoding when the caller needs a fixed shape (ADR-0028), and ``bounds`` caps how far
    the model may go, whether it thinks first, and how far a thought that happens may run
    (ADR-0038 cheap-fold addendum, ADR-0005 request-lever addendum). Every caller here is an
    in-turn side call whose thinking is discarded by the line above, which is exactly the case
    ``GenerationBounds(thinking=False, trace_tokens=0)`` exists for, and all three of them pass
    both: the switch is what a chat template reads and the zero is what the engine's own sampler
    does, and neither is derived from the other. ``InferenceError`` propagates for the
    caller to decide about, and the stream is closed on that path too, which is the whole reason
    this exists.

    **A trace that arrives despite ``thinking=False`` is dropped with a line rather than in
    silence** (ADR-0005 switch-is-advisory addendum). That switch is a request to the deployment's
    chat template and not a guarantee about the model, and where it goes unhonoured every caller
    here is holding a cap sized on the wanted answer while the model spends it thinking, so the
    reply comes back empty or cut with the tokens unaccounted for. This is the one place that sees
    both halves of that, the request that asked and the trace that came back, and it is the place
    the trace is destroyed, so the line is written here and says how many characters went unread.
    Nothing else changes: the text is returned exactly as before, because a deployment that ignores
    the switch is something an operator fixes at the deployment and not something a side call can
    react to. There are two such fixes now, and this line is how a deployment learns it needs one:
    the tier's own ``--reasoning-budget 0``, and the per-request budget every caller here already
    asks for, which reaches the engine only where that engine reads it
    (``CORTEX_INFERENCE_TRACE_LEVER``, ADR-0005 request-lever addendum). So a line here on a
    deployment whose engine does read one says the count was carried and something else went
    wrong; on one whose engine does not, it says exactly what it always said. A completion that
    fails part way says nothing, there being no completion to describe, which is the stance the
    rank's own two warnings take.

    ``stops`` is the optional collaborator that receives the closing ``DecodeStop``, threaded the
    way ``ToolLoopContext`` threads one into ``stream_tool_loop`` and for the same reason: why a
    completion ended is a fact about the machine that stopped it rather than something the model
    said, so it goes to whoever asked instead of into the returned text. A caller that hands none
    drops the stop exactly as this helper always has, so the return type is still a bare ``str``
    and the callers that want only that are untouched (ADR-0038's cut-fold addendum). The recap
    fold passes one, a fold cut at the token cap being otherwise indistinguishable from a model
    that wandered.

    The port promises only an ``AsyncIterator``, and only an async *generator* has an ``aclose``
    to call; a plain iterator holds no suspended ``finally`` and so holds no lease. Both shapes are
    live in this tree, so the close is guarded rather than assumed.

    Six arguments is ruff's ceiling here, deliberately reached rather than approached: a seventh
    collaborator wants a bundle (the ``ToolLoopContext`` move), not another keyword.
    """
    asked_against = bounds is not None and not bounds.thinking
    stream = backend.stream(model, messages, schema=schema, bounds=bounds)
    parts: list[str] = []
    unasked = 0
    try:
        async for event in stream:
            if isinstance(event, TextChunk):
                parts.append(event.text)
            elif isinstance(event, ReasoningChunk) and asked_against:
                unasked += len(event.text)
            elif isinstance(event, DecodeStop) and stops is not None:
                stops.observe(event)
    finally:
        if isinstance(stream, AsyncGenerator):
            await stream.aclose()
    if unasked:
        _logger.warning(
            "the model deliberated on a request that asked for no thinking, and the trace was "
            "dropped unread",
            extra={"model": model, "chars": unasked},
        )
    return "".join(parts)
