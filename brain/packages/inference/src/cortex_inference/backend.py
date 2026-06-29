"""LlamaCppBackend: the InferenceBackend port over llama-server's OpenAI HTTP API.

ADR-0005: one ``llama-server`` per model, its OpenAI-compatible ``/v1/chat/completions``
as the adapter surface. This adapter takes a GPU lease from the ``ModelManager``, opens a
streaming chat completion against the leased endpoint, and yields the assistant text as
``TextChunk`` deltas plus any ``ToolCall`` the model makes from the offered ``tools``
(native function-calling, ADR-0009, which needs the server started with ``--jinja``). It is a
thin HTTP translator with no orchestration and no session state (the one hard rule). Every
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
    Role,
    TextChunk,
    ToolCall,
    ToolSpec,
)
from cortex_core.inference import InferenceEvent

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
_SSE_DATA_PREFIX = "data:"
_SSE_DONE = "[DONE]"


@dataclass
class _PendingCall:
    """A tool call being reassembled from streamed OpenAI ``tool_calls`` fragments."""

    id: str = ""
    name: str = ""
    arguments: str = ""


def _to_openai_message(message: Message) -> dict[str, object]:
    """Map one core ``Message`` onto an OpenAI chat message, tool structure included."""
    if message.role is Role.TOOL:
        return {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.text}
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


def _consume_chunk(payload: str, pending: dict[int, _PendingCall]) -> str | None:
    """Return a chunk's text delta (or ``None``), folding any tool-call fragments into ``pending``.

    Malformed JSON or an unexpected shape raises ``InferenceError``. A silently skipped chunk
    would drop reply text or a tool call, exactly the failure mode the store adapter refuses.
    """
    try:
        data = json.loads(payload)
        choices = data["choices"]
        if not choices:
            return None
        delta = choices[0]["delta"]
        for fragment in delta.get("tool_calls", ()):
            slot = pending.setdefault(fragment.get("index", 0), _PendingCall())
            slot.id = fragment.get("id") or slot.id
            function = fragment.get("function")
            slot.name = function.get("name") or slot.name
            slot.arguments += function.get("arguments") or ""
        content = delta.get("content")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError) as err:
        msg = f"malformed streaming chunk from llama-server: {payload!r}"
        raise InferenceError(msg) from err
    if content is None:
        return None
    if not isinstance(content, str):
        msg = f"non-string content in streaming chunk: {content!r}"
        raise InferenceError(msg)
    return content


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
        self, model: str, messages: Sequence[Message], *, tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[InferenceEvent]:
        """Stream text deltas from the leased llama-server, then any assembled tool calls."""
        payload: dict[str, object] = {
            "model": model,
            "messages": [_to_openai_message(message) for message in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = _to_openai_tools(tools)
        pending: dict[int, _PendingCall] = {}
        try:
            async with self._manager.acquire(model) as lease:
                url = f"{lease.endpoint}{_CHAT_COMPLETIONS_PATH}"
                async with self._client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        stripped = line.strip()
                        if not stripped.startswith(_SSE_DATA_PREFIX):
                            continue
                        data = stripped[len(_SSE_DATA_PREFIX) :].strip()
                        if data == _SSE_DONE:
                            break
                        delta = _consume_chunk(data, pending)
                        if delta:
                            yield TextChunk(delta)
        except ModelManagerError as err:
            msg = f"model manager could not lease {model!r} for inference"
            raise InferenceError(msg) from err
        except httpx.HTTPError as err:
            msg = f"llama-server request failed for model {model!r}"
            raise InferenceError(msg) from err
        for call in _finish_calls(pending):
            yield call
