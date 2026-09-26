"""llama-server stand-ins whose chat template takes one leading system message or every one."""

import json
from dataclasses import dataclass, field
from typing import cast

import httpx

APPLY_TEMPLATE = "/apply-template"
CHAT_COMPLETIONS = "/v1/chat/completions"

# The body a Qwen3.5 server on b10680-d7bd3bfca answered a second system message with.
TEMPLATE_REFUSAL: dict[str, object] = {
    "error": {
        "code": 500,
        "message": (
            "\n------------\nWhile executing CallExpression at line 85, column 32 in source:\n"
            "...first %}↵            {{- raise_exception('System message must be at the "
            "beginnin...\n                                           ^\n"
            "Error: Jinja Exception: System message must be at the beginning."
        ),
        "type": "server_error",
    }
}


def leading_systems(body: dict[str, object]) -> list[str]:
    """The texts of the system messages that open a request body, in order."""
    texts: list[str] = []
    for message in cast("list[dict[str, object]]", body["messages"]):
        if message["role"] != "system":
            break
        texts.append(cast("str", message["content"]))
    return texts


def turn_per_system(systems: list[str]) -> str:
    """A gemma-shaped prompt: each system message in a turn of its own."""
    turns = "".join(f"<|turn>system\n{text}<turn|>\n" for text in systems)
    return f"{turns}<|turn>user\n.<turn|>\n<|turn>model\n"


@dataclass
class TemplateServer:
    """A ``MockTransport`` handler for one llama-server that records every request it answers."""

    takes_several: bool
    reply: bytes
    probes: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    chats: list[dict[str, object]] = field(default_factory=list[dict[str, object]])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = cast("dict[str, object]", json.loads(request.content))
        systems = leading_systems(body)
        refuses = len(systems) > 1 and not self.takes_several
        if request.url.path == APPLY_TEMPLATE:
            self.probes.append(body)
            if refuses:
                return httpx.Response(500, json=TEMPLATE_REFUSAL)
            return httpx.Response(200, json={"prompt": turn_per_system(systems)})
        self.chats.append(body)
        if refuses:
            return httpx.Response(500, json=TEMPLATE_REFUSAL)
        return httpx.Response(200, content=self.reply)
