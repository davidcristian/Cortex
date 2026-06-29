"""LlamaCppBackend: the InferenceBackend port over llama-server's OpenAI HTTP API."""

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
    """Pull the assistant text delta out of one SSE ``data:`` JSON payload."""
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
    """InferenceBackend over a llama-server OpenAI-compatible endpoint (ADR-0005)."""

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
