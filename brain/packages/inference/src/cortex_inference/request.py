"""Building one llama-server chat-completion request out of core values (ADR-0005).

The request half of the llama.cpp adapter, split from ``backend.py`` when the decode-cadence arm
took that file to the 300-line cap. The seam between the three modules is the direction a value
travels: this maps core vocabulary onto the wire, ``decode.py`` maps the wire back onto core
vocabulary, and ``backend.py`` owns the lease, the HTTP call, and the order events come out in.

Nothing here holds business logic or state: every function is a total mapping from the arguments
it is given. The names are module-public rather than underscored because the split made them
cross a module boundary, which is the one thing a leading underscore is supposed to forbid; they
remain package-internal, since ``cortex_inference`` exports only ``LlamaCppBackend``.
"""

import json
from collections.abc import Sequence

from cortex_core import Message, Role, ToolSpec, data_uri
from cortex_core.inference import GenerationBounds, JsonSchema

__all__ = ["build_payload", "to_openai_message", "to_openai_tools", "tool_content"]


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
) -> dict[str, object]:
    """The streaming chat-completion request body: messages always, tools, a constrained
    ``response_format`` and the request's ``bounds`` only when present (ADR-0009/0028, ADR-0038
    cheap-fold addendum), so an unbounded unconstrained tool-less turn is byte-for-byte the
    original request.

    ``bounds`` renders as two independent keys. ``max_tokens`` is the OpenAI field llama-server
    reads as ``n_predict`` for this request, overriding the server's own ``-1``.
    ``chat_template_kwargs: {"enable_thinking": false}`` is the per-request half of the lever the
    subagent tier takes per server (``--chat-template-kwargs``, ADR-0010). It is the only half a
    request has, and it is advisory: measured on the two shipped picks it holds on a plain request
    and, on the subagent pick, is a coin toss once the request carries a ``response_format``, the
    model deliberating straight through it on 4 draws in 5. The key reaches the template either
    way; what a schema adds is a grammar that leaves the thought open whatever the template was
    told, so what decides a pick is whether its own template has already closed it, measured over
    the whole lineup (ADR-0005 switch-is-advisory addendum). The lever that holds whatever the
    request looks like is the tier's own ``--reasoning-budget``, and this adapter deliberately
    does not send one: the spelling this repo tried, ``reasoning_budget``, is ignored on a request
    body in both directions (ADR-0005 trace-budget addendum). A build that reads
    ``reasoning_budget_tokens`` off the body has since been measured to end the thought on exactly
    the shape the switch loses, so this payload could carry a lever that holds; that is a decision
    for the port owning the switch rather than for this mapping, and it is open in the
    deferred-refinements backlog.
    A ``thinking=True`` bound emits no key at all rather than an explicit ``true``: the server's
    template default is what a user-facing reply already gets, and saying so louder would change
    the request for every deployment whose template spells the flag differently.

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
    return payload
