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

from collections.abc import AsyncGenerator, Sequence

from cortex_core.conversation import Message
from cortex_core.inference import DecodeStop, GenerationBounds, JsonSchema, TextChunk
from cortex_core.ports import InferenceBackend
from cortex_core.stops import StopLedger


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
    the model may go and whether it thinks first (ADR-0038 cheap-fold addendum). Every caller here
    is an in-turn side call whose thinking is discarded by the line above, which is exactly the
    case ``GenerationBounds(thinking=False)`` exists for. ``InferenceError`` propagates for the
    caller to decide about, and the stream is closed on that path too, which is the whole reason
    this exists.

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
    stream = backend.stream(model, messages, schema=schema, bounds=bounds)
    parts: list[str] = []
    try:
        async for event in stream:
            if isinstance(event, TextChunk):
                parts.append(event.text)
            elif isinstance(event, DecodeStop) and stops is not None:
                stops.observe(event)
    finally:
        if isinstance(stream, AsyncGenerator):
            await stream.aclose()
    return "".join(parts)
