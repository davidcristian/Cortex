"""Build one llama-server chat-completion request out of core values."""

import json
from collections.abc import Sequence

from cortex_core import Message, Role, ToolSpec, data_uri
from cortex_core.inference import GenerationBounds, JsonSchema

__all__ = [
    "TRACE_BUDGET_KEY",
    "build_payload",
    "message_content",
    "to_openai_message",
    "to_openai_tools",
]

# What llama.cpp calls a per-request trace budget on the wire. ``trace_probe.py`` asks a server
# whether it parses this key, so the probe and the request must name the same thing.
TRACE_BUDGET_KEY = "reasoning_budget_tokens"


def message_content(message: Message) -> object:
    """A message's ``content``: a plain string, or a content-parts array when it has images."""
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
            "content": message_content(message),
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
    return {"role": message.role.value, "content": message_content(message)}


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
    send_trace_budget: bool = False,
) -> dict[str, object]:
    """The streaming chat-completion request body.

    Messages always; tools, a constrained ``response_format`` and ``bounds`` only when present, so
    a turn with none of them sends byte for byte the request this repo sent before they existed.
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
        # The key is sent only where the deployment declared or the boot probe measured that the
        # engine parses ``reasoning_budget_tokens``, since a build that does not parse it drops
        # the value without reporting anything.
        if send_trace_budget and bounds.trace_tokens is not None:
            payload[TRACE_BUDGET_KEY] = bounds.trace_tokens
    return payload
