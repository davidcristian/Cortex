"""Ask which name, if any, the chat template behind an endpoint takes for a reasoning effort."""

from typing import cast

import httpx

from cortex_core.inference import ReasoningEffort
from cortex_inference.probe_bound import ProbeTimeoutError, answered_within

__all__ = ["EFFORT_PROBE_TIMEOUT_S", "EffortProbeError", "effort_wire_name"]

_PROPS_PATH = "/props"

# Written as a number rather than through httpx's enum, as ``system_probe.py`` explains.
_ANSWERED_STATUS = 200

# The names one level may be sent under, the first the server lists being the one sent. The
# Qwen3.8 template renders ``high`` as ``xhigh``, and its server lists ``xhigh`` alone of the two.
_WIRE_NAMES: dict[ReasoningEffort, tuple[str, ...]] = {
    ReasoningEffort.LOW: ("low",),
    ReasoningEffort.MEDIUM: ("medium",),
    ReasoningEffort.HIGH: ("high", "xhigh"),
}

# The probe runs inside the model lease on every request that names an effort, so the bound is
# over the whole answer.
EFFORT_PROBE_TIMEOUT_S = 2.0


class EffortProbeError(Exception):
    """The server gave no answer about its template's effort levels that the probe can read."""


def _template_caps(response: httpx.Response) -> dict[str, object]:
    """The ``chat_template_caps`` object of a ``/props`` body, or ``EffortProbeError``."""
    try:
        answer: object = response.json()
    except ValueError as err:
        msg = "the server's properties are not JSON"
        raise EffortProbeError(msg) from err
    caps = (
        cast("dict[str, object]", answer).get("chat_template_caps")
        if isinstance(answer, dict)
        else None
    )
    if not isinstance(caps, dict):
        msg = "the server's properties name no template capabilities"
        raise EffortProbeError(msg)
    return cast("dict[str, object]", caps)


def _wire_name(caps: dict[str, object], effort: ReasoningEffort) -> str | None:
    """The name ``effort`` is sent under, or ``None`` where the template takes none of its names."""
    if caps.get("supports_reasoning_effort") is not True:
        return None
    names = _WIRE_NAMES[effort]
    levels = caps.get("reasoning_effort_levels")
    if not isinstance(levels, list):
        return names[0]
    listed = cast("list[object]", levels)
    return next((name for name in names if name in listed), None)


async def effort_wire_name(
    endpoint: str, effort: ReasoningEffort, client: httpx.AsyncClient
) -> str | None:
    """What ``reasoning_effort`` says for ``effort`` at ``endpoint``, or ``None`` to send nothing.

    An answer the probe cannot read raises ``EffortProbeError``.
    """
    url = f"{endpoint.rstrip('/')}{_PROPS_PATH}"
    try:
        response = await answered_within(
            EFFORT_PROBE_TIMEOUT_S, client.get(url, timeout=EFFORT_PROBE_TIMEOUT_S)
        )
    except (httpx.HTTPError, ProbeTimeoutError) as err:
        msg = f"the properties request failed: {type(err).__name__}: {err}"
        raise EffortProbeError(msg) from err
    if response.status_code != _ANSWERED_STATUS:
        msg = f"the properties request answered HTTP {response.status_code}"
        raise EffortProbeError(msg)
    return _wire_name(_template_caps(response), effort)
