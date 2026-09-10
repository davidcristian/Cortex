"""Whether the running model can see, discovered rather than declared."""

import logging
from collections.abc import Awaitable, Callable
from typing import cast

import httpx

from cortex_core import BodyGateway, CaptureBounds, VisionProbe
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.config_body import BodyConfig

_PROPS_PATH = "/props"

# The probe runs inside a user's turn, so its bound is the latency a turn may lose to a server
# that accepts a connection and then says nothing. Measured on the real stack, /props answers in
# 1.5 ms idle and 1.7 ms with a generation in flight, worst of 40 samples 2.5 ms.
PROBE_TIMEOUT_S = 2.0

_log = logging.getLogger(__name__)


def _reports_vision(props: object) -> bool:
    """Read ``modalities.vision`` out of a ``/props`` body, tolerating any other shape.

    Written defensively because the shape is the running server's to change between versions,
    and a strict read would lose vision on an upgrade rather than report it.
    """
    if not isinstance(props, dict):
        return False
    modalities: object = cast("dict[str, object]", props).get("modalities")
    if not isinstance(modalities, dict):
        return False
    return cast("dict[str, object]", modalities).get("vision") is True


def _build_name(props: object) -> str | None:
    """Read ``build_info`` out of a ``/props`` body: the engine's own name for its binary."""
    if not isinstance(props, dict):
        return None
    build: object = cast("dict[str, object]", props).get("build_info")
    return build if isinstance(build, str) else None


class PropsVisionProbe:
    """A ``VisionProbe`` over one ``GET /props``, asked afresh every time."""

    def __init__(self, endpoint: str, client: httpx.AsyncClient) -> None:
        self._url = f"{endpoint.rstrip('/')}{_PROPS_PATH}"
        self._client = client

    async def can_see(self) -> bool:
        """One ``GET /props``, with every failure answered ``False`` and logged."""
        try:
            response = await self._client.get(self._url)
            response.raise_for_status()
            props: object = response.json()
        except (httpx.HTTPError, ValueError) as err:
            _log.warning("vision probe failed", extra={"endpoint": self._url, "error": str(err)})
            return False
        vision = _reports_vision(props)
        _log.info(
            "vision probe answered",
            extra={"endpoint": self._url, "vision": vision, "build": _build_name(props)},
        )
        return vision


def build_vision(
    config: InferenceConfig, body_config: BodyConfig, body: BodyGateway | None
) -> tuple[CaptureBounds | None, VisionProbe | None, Callable[[], Awaitable[None]]]:
    """Resolve ``CORTEX_VISION`` into the tool's bounds, its live probe, and a closer."""
    if body is None or config.vision == "off":
        return None, None, noop_aclose
    bounds = CaptureBounds(
        max_edge=body_config.capture_max_edge, max_bytes=body_config.max_image_bytes
    )
    if config.vision == "on":
        return bounds, None, noop_aclose
    client = httpx.AsyncClient(timeout=PROBE_TIMEOUT_S)
    return bounds, PropsVisionProbe(config.endpoint, client), client.aclose
