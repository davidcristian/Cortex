"""LlamaCppBackend: the InferenceBackend port over llama-server's OpenAI HTTP API.

ADR-0005: one ``llama-server`` per model, its OpenAI-compatible ``/v1/chat/completions``
as the adapter surface. This adapter takes a GPU lease from the ``ModelManager``, opens a
streaming chat completion against the leased endpoint, and yields the assistant reply as
``TextChunk`` deltas, a reasoning model's thinking as ``ReasoningChunk`` deltas (ADR-0020's
``reasoning_content``, emitted before the reply), any ``ToolCall`` the model makes from the
offered ``tools`` (native function-calling, ADR-0009, needing the server started with ``--jinja``),
and a closing ``DecodeCadence`` when the server reported how fast it decoded (ADR-0030
spill-watch addendum).
It is a thin HTTP translator with no orchestration and no session state (the one hard rule). Every
transport, status, or decode failure, and any ``ModelManager`` failure, crosses the port as
``InferenceError`` with the cause chained.

Its two halves live beside it, split off when the cadence arm took this file to the 300-line cap:
``request.py`` maps core values onto the wire, ``decode.py`` maps the wire back. What stays here
is what neither of them can own, the lease and the order events leave in.
"""

from collections.abc import AsyncIterator, Sequence

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
from cortex_inference.decode import PendingCall, consume_chunk, finish_calls, raise_for_status
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


class LlamaCppBackend:
    """InferenceBackend over a llama-server OpenAI-compatible endpoint (ADR-0005).

    The ``http_client`` is injected so timeouts and transport are configured at the
    composition root; the adapter sets no request timeout of its own. A generation may
    legitimately stream for a long time, which is why the root's ceiling is a per-read stall
    bound and not a deadline on the request (ADR-0005 stall-ceiling addendum): a stream that
    keeps arriving is never cut off, and one that stops arriving crosses the port as an
    ``InferenceError`` instead of parking the caller's lease forever.
    """

    def __init__(self, model_manager: ModelManager, http_client: httpx.AsyncClient) -> None:
        self._manager = model_manager
        self._client = http_client

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
        With ``bounds`` set (ADR-0038 cheap-fold addendum) the request carries a ``max_tokens``
        and/or asks the chat template for no thinking; ``None`` leaves both to the server.

        The ``DecodeCadence`` is emitted where the server reports it, on the final chunk, so it
        arrives after the text it describes and before the tool calls that are only assembled once
        the stream ends (ADR-0030 spill-watch addendum). A stream that fails partway carries none,
        which is the same silence a build that reports no timings gives, and both mean "no reading"
        rather than "the tier was healthy".
        """
        payload = build_payload(model, messages, tools, schema, bounds)
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
                        content, reasoning, cadence = consume_chunk(data, pending)
                        # A reasoning model emits its thinking before its reply; keep that order
                        # (ADR-0020). Either may be present in a chunk, usually not both.
                        if reasoning:
                            yield ReasoningChunk(reasoning)
                        if content:
                            yield TextChunk(content)
                        if cadence is not None:
                            yield cadence
        except ModelManagerError as err:
            msg = f"model manager could not lease {model!r} for inference"
            raise InferenceError(msg) from err
        except httpx.HTTPError as err:
            raise _transport_failure(err, model) from err
        for call in finish_calls(pending):
            yield call
