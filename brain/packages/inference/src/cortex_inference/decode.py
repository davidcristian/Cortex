"""Read one llama-server streaming response back into core values.

How a malformed answer is handled, which differs by field, is in docs/modules/brain-inference.md.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import httpx

from cortex_core import DecodeCadence, InferenceError, MalformedToolCallError, ToolCall
from cortex_core.inference import DecodeStop, StopReason

__all__ = [
    "ChunkRead",
    "PendingCall",
    "consume_chunk",
    "finish_calls",
    "raise_for_status",
]

# llama.cpp's finish-reason words mapped onto the core's closed set. All three were read off a
# running server; any other word becomes ``StopReason.UNKNOWN``.
_STOP_REASONS = {
    "stop": StopReason.FINISHED,
    "length": StopReason.CAPPED,
    "tool_calls": StopReason.CALLED,
}

# Long enough for llama-server's own message (a missing multimodal projector reads as its own
# hint rather than a bare 500) and short enough that a server answering HTML cannot flood the log.
_ERROR_EXCERPT_CHARS = 300


async def raise_for_status(response: httpx.Response, model: str) -> None:
    """Raise on a non-2xx, quoting a bounded excerpt of the body.

    Reading the body here is safe because the request has already failed, so nothing the stream
    still needs is consumed.
    """
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
    """A delta text field is a string or absent; anything else raises, a non-string being a protocol
    violation that must not be dropped.
    """
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
    """The completion's decode rate off llama.cpp's own ``timings``, or ``None``."""
    raw = data.get("timings")
    if not isinstance(raw, dict):
        return None
    timings = cast("Mapping[str, object]", raw)
    rate = _non_negative(timings.get("predicted_per_second"))
    tokens = _non_negative(timings.get("predicted_n"))
    if rate is None or tokens is None:
        return None
    return DecodeCadence(tokens_per_second=rate, tokens=int(tokens))


def _build(data: Mapping[str, object]) -> str | None:
    """The engine build the chunk names in ``system_fingerprint``, or ``None``."""
    build = data.get("system_fingerprint")
    return build if isinstance(build, str) and build else None


def _stop(choice: Mapping[str, object]) -> DecodeStop | None:
    """The completion's stop reason off llama.cpp's ``finish_reason``, or ``None``."""
    raw = choice.get("finish_reason")
    if raw is None:
        return None
    if not isinstance(raw, str):
        return DecodeStop(StopReason.UNKNOWN)
    return DecodeStop(_STOP_REASONS.get(raw, StopReason.UNKNOWN))


@dataclass(frozen=True, slots=True)
class ChunkRead:
    """What one streamed chunk held, each field ``None`` when the chunk had nothing for it."""

    content: str | None = None
    reasoning: str | None = None
    cadence: DecodeCadence | None = None
    stop: DecodeStop | None = None
    build: str | None = None


def consume_chunk(payload: str, pending: dict[int, PendingCall]) -> ChunkRead:
    """Read one chunk into a ``ChunkRead``, folding any tool-call fragments into ``pending``."""
    try:
        data = json.loads(payload)
        cadence = _cadence(data)
        build = _build(data)
        choices = data["choices"]
        if not choices:
            return ChunkRead(cadence=cadence, build=build)
        stop = _stop(choices[0])
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
    return ChunkRead(
        content=_require_text(content, "content"),
        reasoning=_require_text(reasoning, "reasoning_content"),
        cadence=cadence,
        stop=stop,
        build=build,
    )


def finish_calls(pending: dict[int, PendingCall]) -> list[ToolCall]:
    """Turn the reassembled fragments into ``ToolCall``s, parsing each JSON argument string."""
    calls: list[ToolCall] = []
    for slot in pending.values():
        try:
            arguments: Mapping[str, object] = json.loads(slot.arguments) if slot.arguments else {}
        except json.JSONDecodeError as err:
            msg = f"malformed tool-call arguments from llama-server: {slot.arguments!r}"
            raise MalformedToolCallError(msg) from err
        calls.append(ToolCall(id=slot.id, name=slot.name, arguments=arguments))
    return calls
