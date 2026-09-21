"""The ``InferenceBackend`` port over llama-server's OpenAI HTTP API.

It takes a GPU lease from the ``ModelManager``, opens a streaming chat completion against the
leased endpoint, and yields the reply and the model's thinking as core events.
"""

import logging
from collections.abc import AsyncIterator, Iterator, Sequence

import httpx

from cortex_core import (
    InferenceError,
    Message,
    ModelManager,
    ModelManagerError,
    ReasoningChunk,
    TextChunk,
    ToolSpec,
)
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_inference.decode import (
    ChunkRead,
    PendingCall,
    consume_chunk,
    finish_calls,
    raise_for_status,
)
from cortex_inference.request import build_payload

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
_SSE_DATA_PREFIX = "data:"
_SSE_DONE = "[DONE]"

_logger = logging.getLogger(__name__)


def _transport_failure(err: httpx.HTTPError, model: str) -> InferenceError:
    """The port's error for a failed exchange, with a stall named apart from a dead server."""
    if isinstance(err, httpx.ReadTimeout):
        return InferenceError(f"llama-server sent nothing for model {model!r} within its ceiling")
    return InferenceError(f"llama-server request failed for model {model!r}")


def _chunk_events(chunk: ChunkRead) -> Iterator[InferenceEvent]:
    """The events one streamed chunk produces, in the order a consumer must see them."""
    if chunk.reasoning:
        yield ReasoningChunk(chunk.reasoning)
    if chunk.content:
        yield TextChunk(chunk.content)
    if chunk.stop is not None:
        yield chunk.stop
    if chunk.cadence is not None:
        yield chunk.cadence


class LlamaCppBackend:
    """``InferenceBackend`` over a llama-server OpenAI-compatible endpoint.

    The ``http_client`` is injected, so the adapter sets no request timeout of its own: a
    generation may stream for a long time, and the root's ceiling is a per-read stall bound.
    """

    def __init__(
        self,
        model_manager: ModelManager,
        http_client: httpx.AsyncClient,
        *,
        send_trace_budget: bool = False,
    ) -> None:
        self._manager = model_manager
        self._client = http_client
        # Off by default: an engine that does not parse ``reasoning_budget_tokens`` drops the
        # count without reporting anything, which would leave a setting that changes nothing.
        self._send_trace_budget = send_trace_budget
        self._reported_unsent_budget = False

    def _report_unsent_budget(self, model: str, bounds: GenerationBounds | None) -> None:
        """Warn, once per backend, when a request names a trace count it will not send."""
        if self._send_trace_budget or self._reported_unsent_budget or bounds is None:
            return
        if bounds.trace_tokens is None or (bounds.trace_tokens == 0 and not bounds.thinking):
            return
        self._reported_unsent_budget = True
        _logger.warning(
            "trace budget not sent because its setting is off",
            extra={"model": model, "trace_budget": bounds.trace_tokens},
        )

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Stream text deltas from the leased llama-server, then any assembled tool calls."""
        self._report_unsent_budget(model, bounds)
        payload = build_payload(
            model, messages, tools, schema, bounds, send_trace_budget=self._send_trace_budget
        )
        pending: dict[int, PendingCall] = {}
        try:
            async with self._manager.acquire(model) as lease:
                url = f"{lease.endpoint}{_CHAT_COMPLETIONS_PATH}"
                async with self._client.stream("POST", url, json=payload) as response:
                    await raise_for_status(response, model)
                    async for line in response.aiter_lines():
                        stripped = line.strip()
                        if not stripped.startswith(_SSE_DATA_PREFIX):
                            continue
                        data = stripped[len(_SSE_DATA_PREFIX) :].strip()
                        if data == _SSE_DONE:
                            break
                        for event in _chunk_events(consume_chunk(data, pending)):
                            yield event
        except ModelManagerError as err:
            msg = f"model manager could not lease {model!r} for inference"
            raise InferenceError(msg) from err
        except httpx.HTTPError as err:
            raise _transport_failure(err, model) from err
        for call in finish_calls(pending):
            yield call
