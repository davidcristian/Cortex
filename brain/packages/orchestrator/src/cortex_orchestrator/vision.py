"""Whether the running model can see, discovered rather than declared (ADR-0029).

``llama-server`` reports its own modalities at ``GET /props`` once a multimodal projector is
loaded, so the composition root asks it instead of believing a brain-side boolean. The two can
disagree, and both directions of that disagreement are bad: declaring vision the server does
not have means a mid-turn error after the capture has already been taken and the user already
notified, which is the full privacy cost for zero benefit; declaring it absent when the server
has it means the capability is never offered.

``CORTEX_VISION=auto|on|off`` overrides. ``auto`` (the default) probes. ``on`` and ``off``
exist so CI and a deterministic test can fix the answer without a server, and so a user can
switch capture off outright without editing compose.

A probe failure counts as **no vision**. Failing closed here is the honest default: the tool is
simply not advertised, the user is never asked to pay a privacy cost for a picture nothing can
read, and the warning names the endpoint so the cause is visible in the log.

Split out of ``builders.py``, which is near the line cap, following the ``config_tools`` /
``memory_builders`` / ``subagent_builders`` precedent.
"""

import logging
from typing import cast

import httpx

_PROPS_PATH = "/props"

# The probe blocks startup, so it gets a short leash: a server that cannot answer in this long
# is a server the first turn would have failed against anyway.
PROBE_TIMEOUT_S = 5.0

_log = logging.getLogger(__name__)


def _reports_vision(props: object) -> bool:
    """Read ``modalities.vision`` out of a ``/props`` body, tolerating any other shape.

    Written defensively on purpose: this parses a live server's JSON, the shape is that
    server's to change between versions, and the failure mode of a strict read would be losing
    vision on an upgrade rather than reporting it.
    """
    if not isinstance(props, dict):
        return False
    modalities: object = cast("dict[str, object]", props).get("modalities")
    if not isinstance(modalities, dict):
        return False
    return cast("dict[str, object]", modalities).get("vision") is True


async def probe_vision(endpoint: str, *, client: httpx.AsyncClient | None = None) -> bool:
    """Ask the model server at ``endpoint`` whether it has a vision tower loaded.

    ``client`` is injected by tests; in production the probe owns a short-lived client, because
    it runs once at startup and holding one for the rest of the process would outlive its only
    use.
    """
    if client is not None:
        return await _ask(client, endpoint)
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as owned:
        return await _ask(owned, endpoint)


async def _ask(client: httpx.AsyncClient, endpoint: str) -> bool:
    """One ``GET /props``, with every failure answered ``False`` and logged."""
    url = f"{endpoint.rstrip('/')}{_PROPS_PATH}"
    try:
        response = await client.get(url)
        response.raise_for_status()
        props: object = response.json()
    except (httpx.HTTPError, ValueError) as err:
        _log.warning("vision probe failed", extra={"endpoint": url, "error": str(err)})
        return False
    vision = _reports_vision(props)
    _log.info("vision probe answered", extra={"endpoint": url, "vision": vision})
    return vision


async def vision_enabled(
    mode: str, endpoint: str, *, client: httpx.AsyncClient | None = None
) -> bool:
    """Resolve ``CORTEX_VISION`` into the one boolean the builders need."""
    if mode == "on":
        return True
    if mode == "off":
        return False
    return await probe_vision(endpoint, client=client)
