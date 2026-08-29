"""LlamaCppBackend: the InferenceBackend port over llama-server's OpenAI HTTP API.

ADR-0005: one ``llama-server`` per model, its OpenAI-compatible ``/v1/chat/completions``
as the adapter surface. This adapter takes a GPU lease from the ``ModelManager``, opens a
streaming chat completion against the leased endpoint, and yields the assistant reply as
``TextChunk`` deltas, a reasoning model's thinking as ``ReasoningChunk`` deltas (ADR-0020's
``reasoning_content``, emitted before the reply), any ``ToolCall`` the model makes from the
offered ``tools`` (native function-calling, ADR-0009, needing the server started with ``--jinja``),
a closing ``DecodeStop`` carrying the server's ``finish_reason`` (ADR-0005 finish-reason addendum),
and a closing ``DecodeCadence`` when the server reported how fast it decoded (ADR-0030
spill-watch addendum).
It is a thin HTTP translator with no orchestration and no session state (the one hard rule). Every
transport, status, or decode failure, and any ``ModelManager`` failure, crosses the port as
``InferenceError`` with the cause chained.

Its two halves live beside it, split off when the cadence arm took this file to the 300-line cap:
``request.py`` maps core values onto the wire, ``decode.py`` maps the wire back. What stays here
is what neither of them can own, the lease and the order events leave in.
"""

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


def _transport_failure(err: httpx.HTTPError, model: str) -> InferenceError:
    """The port's error for a failed exchange, with a stall named apart from a dead server.

    Both cross as ``InferenceError`` (a caller must never see an httpx type), but the two send
    an operator to opposite places: nothing answered at all, against a server that took the
    request and then went quiet past the client's stall ceiling, which is a wedged or contended
    tier rather than an unreachable one (ADR-0005 stall-ceiling addendum).
    """
    if isinstance(err, httpx.ReadTimeout):
        return InferenceError(f"llama-server sent nothing for model {model!r} within its ceiling")
    return InferenceError(f"llama-server request failed for model {model!r}")


def _chunk_events(chunk: ChunkRead) -> Iterator[InferenceEvent]:
    """The events one streamed chunk produces, in the order a consumer must see them.

    A reasoning model emits its thinking before its reply, so that order is kept (ADR-0020);
    either may be present in one chunk, usually not both. The stop explains the text that just
    ended, so it sits next to it, and the cadence still closes the stream. llama.cpp puts all four
    on one chunk when it puts them anywhere, so the order between them is this adapter's own
    choice rather than the wire's (ADR-0005 finish-reason addendum).
    """
    if chunk.reasoning:
        yield ReasoningChunk(chunk.reasoning)
    if chunk.content:
        yield TextChunk(chunk.content)
    if chunk.stop is not None:
        yield chunk.stop
    if chunk.cadence is not None:
        yield chunk.cadence


class LlamaCppBackend:
    """InferenceBackend over a llama-server OpenAI-compatible endpoint (ADR-0005).

    The ``http_client`` is injected so timeouts and transport are configured at the
    composition root; the adapter sets no request timeout of its own. A generation may
    legitimately stream for a long time, which is why the root's ceiling is a per-read stall
    bound and not a deadline on the request (ADR-0005 stall-ceiling addendum): a stream that
    keeps arriving is never cut off, and one that stops arriving crosses the port as an
    ``InferenceError`` instead of parking the caller's lease forever.
    """

    def __init__(
        self,
        model_manager: ModelManager,
        http_client: httpx.AsyncClient,
        *,
        trace_lever: bool = False,
    ) -> None:
        self._manager = model_manager
        self._client = http_client
        # Whether a request built here may carry ``GenerationBounds.trace_tokens`` as
        # llama.cpp's ``reasoning_budget_tokens`` (ADR-0005 request-lever addendum). Decided by
        # the composition root, once, from a declaration or from ``lever.py``'s probe of this
        # deployment's own engine, and held rather than re-asked because it is a property of a
        # binary. Off by default, which is the request this adapter has always sent: a bound
        # naming a count against an engine that ignores the key would be a knob that lies.
        self._trace_lever = trace_lever

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Stream text deltas from the leased llama-server, then any assembled tool calls.

        With ``schema`` set (ADR-0028), the request carries an OpenAI ``response_format`` of
        ``json_schema`` so llama-server constrains every token to that shape; the subagent
        runner uses it to force a tool-less weak model's reply into a fixed envelope, killing
        format-laundering. ``None`` leaves the request unconstrained, byte-for-byte as before.
        With ``bounds`` set (ADR-0038 cheap-fold addendum) the request carries a ``max_tokens``,
        asks the chat template for no thinking, and, where this deployment's engine was found to
        read one, budgets the trace (ADR-0005 request-lever addendum); ``None`` leaves all three
        to the server.

        The ``DecodeStop`` and the ``DecodeCadence`` are emitted where the server reports them, on
        the final chunk, so both arrive after the text they describe and before the tool calls that
        are only assembled once the stream ends (ADR-0005 finish-reason addendum, ADR-0030
        spill-watch addendum). A stream that fails partway carries neither, which is the same
        silence a build reporting no timings or no finish reason gives, and it means "nothing was
        said" rather than "the tier was healthy" or "the model finished".
        """
        payload = build_payload(
            model, messages, tools, schema, bounds, trace_lever=self._trace_lever
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
