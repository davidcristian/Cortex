"""LlamaCppBackend: the InferenceBackend port over llama-server's OpenAI HTTP API.

ADR-0005: one ``llama-server`` per model, its OpenAI-compatible ``/v1/chat/completions``
as the adapter surface. This adapter takes a GPU lease from the ``ModelManager``, opens a
streaming chat completion against the leased endpoint, and yields the assistant reply as
``TextChunk`` deltas, a reasoning model's thinking as ``ReasoningChunk`` deltas (ADR-0020's
``reasoning_content``, emitted before the reply), and any ``ToolCall`` the model makes from the
offered ``tools`` (native function-calling, ADR-0009, needing the server started with ``--jinja``).
It is a thin HTTP translator with no orchestration and no session state (the one hard rule). Every
transport, status, or decode failure, and any ``ModelManager`` failure, crosses the port as
``InferenceError`` with the cause chained.
"""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass

import httpx

from cortex_core import (
    InferenceError,
    Message,
    ModelManager,
    ModelManagerError,
    ReasoningChunk,
    Role,
    TextChunk,
    ToolCall,
    ToolSpec,
    data_uri,
)
from cortex_core.inference import InferenceEvent, JsonSchema

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
_SSE_DATA_PREFIX = "data:"
_SSE_DONE = "[DONE]"

# How much of llama-server's error body to quote back. Long enough for its own message (a
# missing multimodal projector reads as its own hint rather than a bare 500) and short enough
# that a server which answers HTML never floods the log.
_ERROR_EXCERPT_CHARS = 300


async def _raise_for_status(response: httpx.Response, model: str) -> None:
    """Raise on a non-2xx, quoting a bounded excerpt of the body.

    ``raise_for_status`` alone would report the status and nothing else, because the response
    is streamed and its body is never read; the most common misconfiguration on this path (a
    vision request to a server started without its projector) is then indistinguishable from
    any other failure. Reading the body is safe here precisely because the request has already
    failed, so nothing is consumed that the stream still needs.
    """
    if not response.is_error:
        return
    body = (await response.aread()).decode("utf-8", errors="replace").strip()
    excerpt = body[:_ERROR_EXCERPT_CHARS]
    detail = f": {excerpt}" if excerpt else ""
    msg = f"llama-server answered {response.status_code} for model {model!r}{detail}"
    raise InferenceError(msg)


@dataclass
class _PendingCall:
    """A tool call being reassembled from streamed OpenAI ``tool_calls`` fragments."""

    id: str = ""
    name: str = ""
    arguments: str = ""


def _tool_content(message: Message) -> object:
    """The ``content`` of a tool message: a plain string, or a content-parts array with images.

    The array form is what carries a screen capture (ADR-0029), and it rides the message that
    *answers* the tool call rather than a forged user turn: measured against the real cortex, a
    ``role: "tool"`` message whose content is a parts array with a ``data:`` image URI is
    accepted inside a full tool-calling exchange and answered correctly. A message with no
    images emits the byte-identical string it always did, so every text-only request is
    unchanged.
    """
    if not message.images:
        return message.text
    parts: list[dict[str, object]] = [{"type": "text", "text": message.text}]
    parts.extend(
        {"type": "image_url", "image_url": {"url": data_uri(image)}} for image in message.images
    )
    return parts


def _to_openai_message(message: Message) -> dict[str, object]:
    """Map one core ``Message`` onto an OpenAI chat message, tool structure included."""
    if message.role is Role.TOOL:
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": _tool_content(message),
        }
    if message.tool_calls:
        return {
            "role": message.role.value,
            "content": message.text,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(dict(call.arguments))},
                }
                for call in message.tool_calls
            ],
        }
    return {"role": message.role.value, "content": message.text}


def _to_openai_tools(tools: Sequence[ToolSpec]) -> list[dict[str, object]]:
    """Map the offered tool specs onto OpenAI ``tools`` (function-calling) entries."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": dict(tool.parameters),
            },
        }
        for tool in tools
    ]


def _build_payload(
    model: str, messages: Sequence[Message], tools: Sequence[ToolSpec], schema: JsonSchema | None
) -> dict[str, object]:
    """The streaming chat-completion request body: messages always, tools and a constrained
    ``response_format`` only when present (ADR-0009/0028), so an unconstrained tool-less turn
    is byte-for-byte the original request."""
    payload: dict[str, object] = {
        "model": model,
        "messages": [_to_openai_message(message) for message in messages],
        "stream": True,
    }
    if tools:
        payload["tools"] = _to_openai_tools(tools)
    if schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "reply", "schema": dict(schema), "strict": True},
        }
    return payload


def _require_text(value: object, field: str) -> str | None:
    """A delta text field is a string or absent; anything else fails loud (a non-string is a
    protocol violation, never silently dropped, matching the store adapter's stance)."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"non-string {field} in streaming chunk: {value!r}"
        raise InferenceError(msg)
    return value


def _consume_chunk(payload: str, pending: dict[int, _PendingCall]) -> tuple[str | None, str | None]:
    """Return a chunk's ``(content, reasoning_content)`` text deltas (either may be ``None``),
    folding any tool-call fragments into ``pending``. A reasoning model (the cortex, ADR-0020)
    streams ``reasoning_content`` (its thinking) before ``content`` (its reply); both are surfaced.

    Malformed JSON or an unexpected shape raises ``InferenceError``. A silently skipped chunk
    would drop reply text or a tool call, exactly the failure mode the store adapter refuses.
    """
    try:
        data = json.loads(payload)
        choices = data["choices"]
        if not choices:
            return None, None
        delta = choices[0]["delta"]
        for fragment in delta.get("tool_calls", ()):
            slot = pending.setdefault(fragment.get("index", 0), _PendingCall())
            slot.id = fragment.get("id") or slot.id
            function = fragment.get("function")
            slot.name = function.get("name") or slot.name
            slot.arguments += function.get("arguments") or ""
        content = delta.get("content")
        reasoning = delta.get("reasoning_content")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError) as err:
        msg = f"malformed streaming chunk from llama-server: {payload!r}"
        raise InferenceError(msg) from err
    return _require_text(content, "content"), _require_text(reasoning, "reasoning_content")


def _finish_calls(pending: dict[int, _PendingCall]) -> list[ToolCall]:
    """Turn the reassembled fragments into ``ToolCall``s, parsing each JSON argument string."""
    calls: list[ToolCall] = []
    for slot in pending.values():
        try:
            arguments: Mapping[str, object] = json.loads(slot.arguments) if slot.arguments else {}
        except json.JSONDecodeError as err:
            msg = f"malformed tool-call arguments from llama-server: {slot.arguments!r}"
            raise InferenceError(msg) from err
        calls.append(ToolCall(id=slot.id, name=slot.name, arguments=arguments))
    return calls


class LlamaCppBackend:
    """InferenceBackend over a llama-server OpenAI-compatible endpoint (ADR-0005).

    The ``http_client`` is injected so timeouts and transport are configured at the
    composition root; the adapter sets no request timeout of its own. A generation may
    legitimately stream for a long time.
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
    ) -> AsyncIterator[InferenceEvent]:
        """Stream text deltas from the leased llama-server, then any assembled tool calls.

        With ``schema`` set (ADR-0028), the request carries an OpenAI ``response_format`` of
        ``json_schema`` so llama-server constrains every token to that shape; the subagent
        runner uses it to force a tool-less weak model's reply into a fixed envelope, killing
        format-laundering. ``None`` leaves the request unconstrained, byte-for-byte as before.
        """
        payload = _build_payload(model, messages, tools, schema)
        pending: dict[int, _PendingCall] = {}
        try:
            async with self._manager.acquire(model) as lease:
                url = f"{lease.endpoint}{_CHAT_COMPLETIONS_PATH}"
                async with self._client.stream("POST", url, json=payload) as response:
                    await _raise_for_status(response, model)
                    async for line in response.aiter_lines():
                        stripped = line.strip()
                        if not stripped.startswith(_SSE_DATA_PREFIX):
                            continue
                        data = stripped[len(_SSE_DATA_PREFIX) :].strip()
                        if data == _SSE_DONE:
                            break
                        content, reasoning = _consume_chunk(data, pending)
                        # A reasoning model emits its thinking before its reply; keep that order
                        # (ADR-0020). Either may be present in a chunk, usually not both.
                        if reasoning:
                            yield ReasoningChunk(reasoning)
                        if content:
                            yield TextChunk(content)
        except ModelManagerError as err:
            msg = f"model manager could not lease {model!r} for inference"
            raise InferenceError(msg) from err
        except httpx.HTTPError as err:
            msg = f"llama-server request failed for model {model!r}"
            raise InferenceError(msg) from err
        for call in _finish_calls(pending):
            yield call
