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
from cortex_inference.request import build_payload, join_leading_system, leading_system_count
from cortex_inference.system_probe import SystemProbeError, delivers_system_messages

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

    The ``http_client`` is injected, so a generation, which may stream for a long time, runs under
    the root's per-read stall bound; only the system message probe sets a timeout of its own.
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
        self._builds: dict[str, str] = {}
        self._probes: dict[tuple[str, int], str] = {}

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

    def _note_build(self, model: str, endpoint: str, build: str | None) -> None:
        """Log the build a model's server names, the first time and whenever it changes."""
        if build is None or self._builds.get(model) == build:
            return
        self._builds[model] = build
        _logger.info(
            "model now served by engine build",
            extra={"model": model, "endpoint": endpoint, "build": build},
        )

    def _changed(self, endpoint: str, count: int, outcome: str) -> bool:
        """Record a probe's outcome; ``True`` when it differs from the last one for this pair."""
        if self._probes.get((endpoint, count)) == outcome:
            return False
        self._probes[endpoint, count] = outcome
        return True

    async def _joins(self, endpoint: str, model: str, count: int) -> bool:
        """Whether the leased server's template needs its leading system messages joined."""
        try:
            delivers = await delivers_system_messages(endpoint, model, count, self._client)
        except SystemProbeError as err:
            if self._changed(endpoint, count, "failed"):
                _logger.warning(
                    "system message probe failed; joining the leading system messages",
                    extra={"endpoint": endpoint, "system_messages": count, "error": str(err)},
                )
            return True
        if self._changed(endpoint, count, "delivers" if delivers else "joins"):
            _logger.info(
                "system message probe answered",
                extra={"endpoint": endpoint, "system_messages": count, "delivers": delivers},
            )
        return not delivers

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
        leading = leading_system_count(messages)
        pending: dict[int, PendingCall] = {}
        try:
            async with self._manager.acquire(model) as lease:
                joins = leading > 1 and await self._joins(lease.endpoint, model, leading)
                sent = join_leading_system(messages) if joins else messages
                payload = build_payload(
                    model,
                    sent,
                    tools,
                    schema,
                    bounds,
                    send_trace_budget=self._send_trace_budget,
                )
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
                        chunk = consume_chunk(data, pending)
                        self._note_build(model, lease.endpoint, chunk.build)
                        for event in _chunk_events(chunk):
                            yield event
        except ModelManagerError as err:
            msg = f"model manager could not lease {model!r} for inference"
            raise InferenceError(msg) from err
        except httpx.HTTPError as err:
            raise _transport_failure(err, model) from err
        for call in finish_calls(pending):
            yield call
