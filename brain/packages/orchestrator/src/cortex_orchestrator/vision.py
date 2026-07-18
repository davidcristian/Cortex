"""Whether the running model can see, discovered rather than declared (ADR-0029)."""

import logging
from typing import cast

import httpx

_PROPS_PATH = "/props"

# The probe blocks startup, so it gets a short leash: a server that cannot answer in this long
# is a server the first turn would have failed against anyway.
PROBE_TIMEOUT_S = 5.0

_log = logging.getLogger(__name__)


def _reports_vision(props: object) -> bool:
    """Read ``modalities.vision`` out of a ``/props`` body, tolerating any other shape."""
    if not isinstance(props, dict):
        return False
    modalities: object = cast("dict[str, object]", props).get("modalities")
    if not isinstance(modalities, dict):
        return False
    return cast("dict[str, object]", modalities).get("vision") is True


async def probe_vision(endpoint: str, *, client: httpx.AsyncClient | None = None) -> bool:
    """Ask the model server at ``endpoint`` whether it has a vision tower loaded."""
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
