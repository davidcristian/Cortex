"""Reading one llama-server streaming response back into core values (ADR-0005)."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import httpx

from cortex_core import DecodeCadence, InferenceError, ToolCall

__all__ = [
    "PendingCall",
    "consume_chunk",
    "finish_calls",
    "raise_for_status",
]

# How much of llama-server's error body to quote back. Long enough for its own message (a
# missing multimodal projector reads as its own hint rather than a bare 500) and short enough
# that a server which answers HTML never floods the log.
_ERROR_EXCERPT_CHARS = 300


async def raise_for_status(response: httpx.Response, model: str) -> None:
    """Raise on a non-2xx, quoting a bounded excerpt of the body."""
    if not response.is_error:
        return
    body = (await response.aread()).decode("utf-8", errors="replace").strip()
    excerpt = body[:_ERROR_EXCERPT_CHARS]
    detail = f": {excerpt}" if excerpt else ""
    msg = f"llama-server answered {response.status_code} for model {model!r}{detail}"
    raise InferenceError(msg)


@dataclass
class PendingCall:
    """A tool call being reassembled from streamed OpenAI ``tool_calls`` fragments."""

    id: str = ""
    name: str = ""
    arguments: str = ""


def _require_text(value: object, field: str) -> str | None:
    """A delta text field is a string or absent; anything else fails loud (a non-string is a
    protocol violation, never silently dropped, matching the store adapter's stance)."""
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"non-string {field} in streaming chunk: {value!r}"
        raise InferenceError(msg)
    return value


def _non_negative(value: object) -> float | None:
    """A JSON number that is neither a bool nor negative, else ``None``."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value >= 0 else None


def _cadence(data: Mapping[str, object]) -> DecodeCadence | None:
    """The completion's decode rate off llama.cpp's own ``timings``, or ``None`` (ADR-0030)."""
    raw = data.get("timings")
    if not isinstance(raw, dict):
        return None
    timings = cast("Mapping[str, object]", raw)
    rate = _non_negative(timings.get("predicted_per_second"))
    tokens = _non_negative(timings.get("predicted_n"))
    if rate is None or tokens is None:
        return None
    return DecodeCadence(tokens_per_second=rate, tokens=int(tokens))


def consume_chunk(
    payload: str, pending: dict[int, PendingCall]
) -> tuple[str | None, str | None, DecodeCadence | None]:
    """Return a chunk's ``(content, reasoning_content, cadence)``, any of which may be ``None``,
    folding any tool-call fragments into ``pending``.
    """
    try:
        data = json.loads(payload)
        cadence = _cadence(data)
        choices = data["choices"]
        if not choices:
            return None, None, cadence
        delta = choices[0]["delta"]
        for fragment in delta.get("tool_calls", ()):
            slot = pending.setdefault(fragment.get("index", 0), PendingCall())
            slot.id = fragment.get("id") or slot.id
            function = fragment.get("function")
            slot.name = function.get("name") or slot.name
            slot.arguments += function.get("arguments") or ""
        content = delta.get("content")
        reasoning = delta.get("reasoning_content")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError) as err:
        msg = f"malformed streaming chunk from llama-server: {payload!r}"
        raise InferenceError(msg) from err
    return _require_text(content, "content"), _require_text(reasoning, "reasoning_content"), cadence


def finish_calls(pending: dict[int, PendingCall]) -> list[ToolCall]:
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
