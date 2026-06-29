"""LlamaCppBackend: the InferenceBackend port over llama-server's OpenAI HTTP API.

ADR-0005: one ``llama-server`` per model, its OpenAI-compatible ``/v1/chat/completions``
as the adapter surface. This adapter takes a GPU lease from the ``ModelManager``, opens a
streaming chat completion against the leased endpoint, and yields the assistant text
deltas. It is a thin HTTP translator with no orchestration and no session state (the one hard
rule). Every transport, status, or decode failure, and any ``ModelManager`` failure,
crosses the port as ``InferenceError`` with the cause chained.
"""

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from cortex_core import InferenceError, Message, ModelManager, ModelManagerError

_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
_SSE_DATA_PREFIX = "data:"
_SSE_DONE = "[DONE]"


def _to_openai_messages(messages: Sequence[Message]) -> list[dict[str, str]]:
    """Map the core's messages onto OpenAI chat roles (USER/ASSISTANT only in this slice)."""
    return [{"role": message.role.value, "content": message.text} for message in messages]


def _content_delta(payload: str) -> str | None:
    """Pull the assistant text delta out of one SSE ``data:`` JSON payload.

    Returns ``choices[0].delta.content``, or ``None`` when the chunk carries no text (the
    role-only opening chunk, or a finish chunk with an empty delta). Malformed JSON or an
    unexpected shape raises ``InferenceError``. A silently skipped chunk would drop reply
    text, exactly the failure mode the store adapter also refuses.
    """
    try:
        data = json.loads(payload)
        choices = data["choices"]
        if not choices:
            return None
        content = choices[0]["delta"].get("content")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError) as err:
        msg = f"malformed streaming chunk from llama-server: {payload!r}"
        raise InferenceError(msg) from err
    if content is None:
        return None
    if not isinstance(content, str):
        msg = f"non-string content in streaming chunk: {content!r}"
        raise InferenceError(msg)
    return content


class LlamaCppBackend:
    """InferenceBackend over a llama-server OpenAI-compatible endpoint (ADR-0005).

    The ``http_client`` is injected so timeouts and transport are configured at the
    composition root; the adapter sets no request timeout of its own. A generation may
    legitimately stream for a long time.
    """

    def __init__(self, model_manager: ModelManager, http_client: httpx.AsyncClient) -> None:
        self._manager = model_manager
        self._client = http_client

    async def stream(self, model: str, messages: Sequence[Message]) -> AsyncIterator[str]:
        """Stream the assistant reply as text deltas from the leased llama-server."""
        payload: dict[str, object] = {
            "model": model,
            "messages": _to_openai_messages(messages),
            "stream": True,
        }
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
                            return
                        delta = _content_delta(data)
                        if delta:
                            yield delta
        except ModelManagerError as err:
            msg = f"model manager could not lease {model!r} for inference"
            raise InferenceError(msg) from err
        except httpx.HTTPError as err:
            msg = f"llama-server request failed for model {model!r}"
            raise InferenceError(msg) from err
