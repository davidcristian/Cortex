"""Building one llama-server chat-completion request out of core values (ADR-0005).

The request half of the llama.cpp adapter, split from ``backend.py`` when the decode-cadence arm
took that file to the 300-line cap. The seam between the three modules is the direction a value
travels: this maps core vocabulary onto the wire, ``decode.py`` maps the wire back onto core
vocabulary, and ``backend.py`` owns the lease, the HTTP call, and the order events come out in.

Nothing here holds business logic or state: every function is a total mapping from the arguments
it is given. The names are module-public rather than underscored because the split made them
cross a module boundary, which is the one thing a leading underscore is supposed to forbid; they
remain package-internal, since the package exports only the adapter and the one probe a
composition root asks before building it (``lever.py``).
"""

import json
from collections.abc import Sequence

from cortex_core import Message, Role, ToolSpec, data_uri
from cortex_core.inference import GenerationBounds, JsonSchema

__all__ = [
    "TRACE_BUDGET_KEY",
    "build_payload",
    "to_openai_message",
    "to_openai_tools",
    "tool_content",
]

# What llama.cpp calls a per-request trace budget on the wire. Declared here, where it is spent,
# and read by ``lever.py``, which asks a server whether it knows it; one spelling, because the
# probe that answers for a key and the request that carries it must be asking about one thing.
# The engine accepts ``thinking_budget_tokens`` for the same setting (measured, 0 traces on 3
# draws of 3), and this repo sends one name rather than both: a second key on every request buys
# nothing on a build that reads either and is a second thing to keep true.
TRACE_BUDGET_KEY = "reasoning_budget_tokens"


def tool_content(message: Message) -> object:
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


def to_openai_message(message: Message) -> dict[str, object]:
    """Map one core ``Message`` onto an OpenAI chat message, tool structure included."""
    if message.role is Role.TOOL:
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": tool_content(message),
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


def to_openai_tools(tools: Sequence[ToolSpec]) -> list[dict[str, object]]:
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


def build_payload(
    model: str,
    messages: Sequence[Message],
    tools: Sequence[ToolSpec],
    schema: JsonSchema | None,
    bounds: GenerationBounds | None,
    *,
    trace_lever: bool = False,
) -> dict[str, object]:
    """The streaming chat-completion request body: messages always, tools, a constrained
    ``response_format`` and the request's ``bounds`` only when present (ADR-0009/0028, ADR-0038
    cheap-fold addendum), so an unbounded unconstrained tool-less turn is byte-for-byte the
    original request.

    ``bounds`` renders as three independent keys. ``max_tokens`` is the OpenAI field llama-server
    reads as ``n_predict`` for this request, overriding the server's own ``-1``.
    ``chat_template_kwargs: {"enable_thinking": false}`` is the per-request half of the lever the
    subagent tier takes per server (``--chat-template-kwargs``, ADR-0010). It is advisory:
    measured on the two shipped picks it holds on a plain request and, on the subagent pick, does
    nothing once the request carries a ``response_format``, the model deliberating straight
    through it. The key reaches the template either
    way; what a schema adds is a grammar that leaves the thought open whatever the template was
    told, so what decides a pick is whether its own template has already closed it, measured over
    the whole lineup (ADR-0005 switch-is-advisory addendum).
    A ``thinking=True`` bound emits no key at all rather than an explicit ``true``: the server's
    template default is what a user-facing reply already gets, and saying so louder would change
    the request for every deployment whose template spells the flag differently.

    ``reasoning_budget_tokens`` is the third, and it is the half that holds: llama.cpp reads it
    off the body as a sampler, falling back to the tier's ``--reasoning-budget`` only where the
    request says nothing (ADR-0005 request-lever addendum). ``bounds.trace_tokens`` is rendered
    verbatim, a zero included, and a bound naming none renders nothing, so the tier keeps
    deciding for every caller that has not asked. The **spelling matters and was measured**: the
    one this repo tried first, ``reasoning_budget``, is ignored on a request body on every build
    tested, the newest included (ADR-0005 trace-budget addendum, re-measured under the
    request-lever one at 5 draws of 5).

    ``trace_lever`` is what stops that key from being a knob that lies. An engine that does not
    know it ignores it in silence, which is the failure this repo dislikes most, and the tier flag
    of the same name fails a server at startup instead; so the key is carried only where the
    deployment declared or the composition root measured that this engine reads one
    (``CORTEX_INFERENCE_TRACE_LEVER``). The default is off, which is this repo's request
    unchanged. Nothing here reads ``bounds.thinking`` to decide it: a switch and a count are two
    facts and a caller that wanted a bounded trace named the count.

    Nothing is asked for on behalf of the decode cadence (ADR-0030 spill-watch addendum). This
    build answers a plain streaming request with a ``timings`` object on its final chunk already,
    verified against llama.cpp ``b10298-15586e2d7``, so the adapter reads what is offered rather
    than asking for more and changing every request in the repo to get it.
    """
    payload: dict[str, object] = {
        "model": model,
        "messages": [to_openai_message(message) for message in messages],
        "stream": True,
    }
    if tools:
        payload["tools"] = to_openai_tools(tools)
    if schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "reply", "schema": dict(schema), "strict": True},
        }
    if bounds is not None:
        if bounds.max_tokens is not None:
            payload["max_tokens"] = bounds.max_tokens
        if not bounds.thinking:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        if trace_lever and bounds.trace_tokens is not None:
            payload[TRACE_BUDGET_KEY] = bounds.trace_tokens
    return payload
