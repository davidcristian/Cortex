"""llama-server stand-ins whose chat template reads a reasoning effort, some of them or none."""

import json
from dataclasses import dataclass, field
from typing import cast

import httpx

PROPS = "/props"

# The capability block a Qwen3.8-27B server on b12375-9d25e0014 reports, the other keys left out.
QWEN38_CAPS: dict[str, object] = {
    "supports_reasoning_effort": True,
    "supports_system_role": True,
    "reasoning_effort_levels": ["low", "medium", "xhigh"],
}

# What a template that reads no effort reports: no level list and the capability false.
NO_EFFORT_CAPS: dict[str, object] = {
    "supports_reasoning_effort": False,
    "supports_system_role": True,
}

# The body a Qwen3.8 server answers a level outside its template's three with.
EFFORT_REFUSAL: dict[str, object] = {
    "error": {
        "code": 500,
        "message": (
            "Error: Jinja Exception: Unexpected reasoning effort max. Supported types are xhigh "
            "(default), medium, and low."
        ),
        "type": "server_error",
    }
}


@dataclass
class EffortServer:
    """A ``MockTransport`` handler for one llama-server that records every request it answers."""

    caps: dict[str, object]
    reply: bytes
    props_status: int = 200
    asked: list[str] = field(default_factory=list[str])
    chats: list[bytes] = field(default_factory=list[bytes])

    def takes(self) -> set[str]:
        """The effort names this server answers; it refuses a request that sends any other."""
        if self.caps.get("supports_reasoning_effort") is not True:
            return set()
        return {*cast("list[str]", self.caps.get("reasoning_effort_levels", [])), "high"}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == PROPS:
            self.asked.append(str(request.url))
            return httpx.Response(self.props_status, json={"chat_template_caps": self.caps})
        self.chats.append(request.content)
        body = cast("dict[str, object]", json.loads(request.content))
        if "reasoning_effort" in body and body["reasoning_effort"] not in self.takes():
            return httpx.Response(500, json=EFFORT_REFUSAL)
        return httpx.Response(200, content=self.reply)
