"""Ask whether the chat template behind an endpoint renders every leading system message."""

from typing import cast

import httpx

__all__ = ["SYSTEM_PROBE_TIMEOUT_S", "SystemProbeError", "delivers_system_messages"]

_APPLY_TEMPLATE_PATH = "/apply-template"

# Written as numbers rather than through httpx's enum, whose members are a code-and-phrase pair,
# which makes pyright read a comparison against a status code as unreachable.
_RENDERED_STATUS = 200
_TEMPLATE_RAISED_STATUS = 500

# The probe runs inside the model lease on every request that opens with several system messages.
# Its worst answer over four servers, idle and beside a generation, took 0.013 of this bound.
SYSTEM_PROBE_TIMEOUT_S = 2.0


class SystemProbeError(Exception):
    """The server gave no answer about its template that the probe can read."""


def _markers(count: int) -> list[str]:
    """One distinct text per system message, none a part of another."""
    return [f"cortex system part {index} of {count}" for index in range(1, count + 1)]


def _in_order(prompt: str, markers: list[str]) -> bool:
    """Whether every marker appears in ``prompt``, each after the one before it."""
    start = 0
    for marker in markers:
        found = prompt.find(marker, start)
        if found < 0:
            return False
        start = found + len(marker)
    return True


def _rendered_prompt(response: httpx.Response) -> str:
    """The ``prompt`` string of a rendered template, or ``SystemProbeError``."""
    try:
        answer: object = response.json()
    except ValueError as err:
        msg = "the template render answered with a body that is not JSON"
        raise SystemProbeError(msg) from err
    prompt = cast("dict[str, object]", answer).get("prompt") if isinstance(answer, dict) else None
    if not isinstance(prompt, str):
        msg = "the template render answered with no prompt string"
        raise SystemProbeError(msg)
    return prompt


async def delivers_system_messages(
    endpoint: str, model: str, count: int, client: httpx.AsyncClient
) -> bool:
    """Whether the template at ``endpoint`` renders ``count`` leading system messages in order.

    A template that raises (HTTP 500) is an answer, ``False``; any other unreadable reply raises.
    """
    markers = _markers(count)
    body: dict[str, object] = {
        "model": model,
        "messages": [
            *({"role": "system", "content": marker} for marker in markers),
            {"role": "user", "content": "."},
        ],
    }
    url = f"{endpoint.rstrip('/')}{_APPLY_TEMPLATE_PATH}"
    try:
        response = await client.post(url, json=body, timeout=SYSTEM_PROBE_TIMEOUT_S)
    except httpx.HTTPError as err:
        msg = f"the template render request failed: {type(err).__name__}: {err}"
        raise SystemProbeError(msg) from err
    if response.status_code == _TEMPLATE_RAISED_STATUS:
        return False
    if response.status_code != _RENDERED_STATUS:
        msg = f"the template render answered HTTP {response.status_code}"
        raise SystemProbeError(msg)
    return _in_order(_rendered_prompt(response), markers)
