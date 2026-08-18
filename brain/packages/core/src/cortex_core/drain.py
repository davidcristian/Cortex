"""Run one model call to its end and let go of the GPU, deterministically (ADR-0038 decision 8)."""

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
    """Consume one completion to its end, closing the stream whatever happens, and join its text."""
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
