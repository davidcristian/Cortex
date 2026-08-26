"""Run one model call to its end and let go of the GPU, deterministically (ADR-0038 decision 8)."""

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
    """Consume one completion to its end, closing the stream whatever happens, and join its text."""
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
