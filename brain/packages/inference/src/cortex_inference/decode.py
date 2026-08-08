"""Reading one llama-server streaming response back into core values (ADR-0005).

The response half of the llama.cpp adapter, split from ``backend.py`` when the decode-cadence arm
took that file to the 300-line cap. Its counterpart is ``request.py``; the seam between them is
the direction a value travels, and ``backend.py`` keeps the lease, the HTTP call, and the order
events come out in.

Two different stances toward a malformed answer live here, and the difference is deliberate:

- **Reply content, reasoning, and tool calls fail loud.** A chunk this module cannot parse raises
  ``InferenceError`` rather than being skipped, because a silently dropped chunk loses reply text
  or a tool call, which is the failure mode the store adapter refuses too.
- **The decode cadence fails quiet.** It is a diagnostic that arrives after the answer, so a
  server whose ``timings`` object is missing, oddly shaped, or negative yields no cadence and
  changes nothing else. Killing a finished reply over a telemetry field would trade the thing the
  user asked for against the thing the operator would have liked, and ``CadenceWatch`` already
  understands "no reading" as its own answer rather than as a pass.
"""

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
    """A JSON number that is neither a bool nor negative, else ``None``.

    ``bool`` is excluded explicitly because it is a subclass of ``int`` in Python, so a server
    answering ``true`` where a rate belongs would otherwise arrive as 1.0 tokens per second and
    read as the most catastrophic spill imaginable.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if value >= 0 else None


def _cadence(data: Mapping[str, object]) -> DecodeCadence | None:
    """The completion's decode rate off llama.cpp's own ``timings``, or ``None`` (ADR-0030).

    llama-server puts one ``timings`` object on the **final** streamed chunk of an ordinary
    ``/v1/chat/completions`` request, verified against build ``b10298-15586e2d7``: exactly one
    chunk of a twelve-chunk stream carried it. ``predicted_per_second`` is the server's own
    arithmetic and is taken rather than recomputed from ``predicted_ms``, because the rate the
    runbook's measured table is written in is that field. ``predicted_n`` is floored to an int
    rather than required to be one, a server reporting a whole number as a float being no
    protocol violation.

    Anything unexpected reads as no cadence, per this module's quiet stance: a build that omits
    ``timings``, a field of the wrong type, or a negative figure. Silence here is honest, since
    the port lets a backend report no cadence at all.
    """
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
    folding any tool-call fragments into ``pending``. A reasoning model (the cortex, ADR-0020)
    streams ``reasoning_content`` (its thinking) before ``content`` (its reply); both are surfaced.
    The cadence rides the last chunk only (ADR-0030 spill-watch addendum).

    Malformed JSON or an unexpected shape raises ``InferenceError``. A silently skipped chunk
    would drop reply text or a tool call, exactly the failure mode the store adapter refuses.
    The cadence is read **before** the choices are, because a build that closes a stream with a
    choice-less chunk would otherwise never be asked for its timings.
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
