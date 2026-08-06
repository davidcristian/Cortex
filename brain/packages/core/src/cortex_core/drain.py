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
from cortex_core.inference import JsonSchema, TextChunk
from cortex_core.ports import InferenceBackend


async def drain_text(
    backend: InferenceBackend,
    model: str,
    messages: Sequence[Message],
    *,
    schema: JsonSchema | None = None,
) -> str:
    """Consume one completion to its end, closing the stream whatever happens, and join its text.

    Only assistant text (``TextChunk``) contributes: a reasoning model's ``ReasoningChunk`` and any
    ``ToolCall`` are dropped, so a caller gets the reply and never the private thinking. ``schema``
    constrains decoding when the caller needs a fixed shape (ADR-0028). ``InferenceError``
    propagates for the caller to decide about, and the stream is closed on that path too, which is
    the whole reason this exists.

    The port promises only an ``AsyncIterator``, and only an async *generator* has an ``aclose``
    to call; a plain iterator holds no suspended ``finally`` and so holds no lease. Both shapes are
    live in this tree, so the close is guarded rather than assumed.
    """
    stream = backend.stream(model, messages, schema=schema)
    parts: list[str] = []
    try:
        parts = [event.text async for event in stream if isinstance(event, TextChunk)]
    finally:
        if isinstance(stream, AsyncGenerator):
            await stream.aclose()
    return "".join(parts)
