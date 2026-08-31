"""Whether the running model can see, discovered rather than declared (ADR-0029).

``llama-server`` reports its own modalities at ``GET /props`` once a multimodal projector is
loaded, so the brain asks it rather than relying on a brain-side boolean. The two can disagree,
and both directions of that disagreement are bad: declaring vision the server does not have
means a mid-turn error after the capture has already been taken and the user already notified,
which is the full privacy cost for zero benefit; declaring it absent when the server has it
means the capability is never offered.

The answer used to be taken once, at startup, and frozen into the built-in set. It is now asked
per advertisement and per call (``SightedToolRegistry``), because the process it describes is not
the brain's: the model host recreates a ``llama-server`` child with whatever argv its own boot
gave it, so a redeployment that drops the projector flips this server's answer under a brain that
never restarts. Reproduced 2026-08-06 against the real stack, where the stale advertisement cost a
real screen read and a real 500.

``CORTEX_VISION=auto|on|off`` overrides. ``auto`` (the default) probes. ``on`` and ``off`` exist
so CI and a deterministic test can fix the answer without a server, and so a user can switch
capture off outright without editing compose; both are answered here, with no probe built at
all, which is what makes them free of the network.

A probe failure counts as no vision. Failing closed here is the safe default: the tool is not
advertised, the user is never asked to pay a privacy cost for a picture nothing can read, and the
warning names the endpoint so the cause is visible in the log.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import cast

import httpx

from cortex_core import BodyGateway, CaptureBounds, VisionProbe
from cortex_orchestrator.builders import noop_aclose
from cortex_orchestrator.config import InferenceConfig
from cortex_orchestrator.config_body import BodyConfig

_PROPS_PATH = "/props"

# The probe now sits inside a user's turn rather than at startup, so its leash is the latency a
# turn may lose to a server that accepts a connection and then says nothing. Measured on the
# real stack 2026-08-06: /props answers in 1.5 ms idle and 1.7 ms with a generation in flight,
# worst of 40 samples 2.5 ms. Two seconds is three orders of magnitude above that and still
# short enough that a wedged server delays a turn rather than appearing to hang it.
PROBE_TIMEOUT_S = 2.0

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


class PropsVisionProbe:
    """A ``VisionProbe`` over one ``GET /props``, asked afresh every time.

    Holds a client and an endpoint and nothing else: no remembered verdict, no expiry to reason
    about, and so nothing that could outlive the process it describes. The client is owned by the
    composition root (``build_vision`` returns its closer) rather than created per call, because
    a probe per turn over a fresh connection would pay a handshake for a request measured in
    milliseconds.
    """

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
        _log.info("vision probe answered", extra={"endpoint": self._url, "vision": vision})
        return vision


def build_vision(
    config: InferenceConfig, body_config: BodyConfig, body: BodyGateway | None
) -> tuple[CaptureBounds | None, VisionProbe | None, Callable[[], Awaitable[None]]]:
    """Resolve ``CORTEX_VISION`` into the tool's bounds, its live probe, and a closer.

    Three answers, one per mode, and the pair says which of them was given:

    - no body, or ``off``: no bounds, so ``capture_screen`` is never registered at all. Nothing
      can take a picture, so there is nothing to ask a model server about.
    - ``on``: bounds and no probe. The owner has fixed the answer, which is what the switch is
      for, and the tool is advertised unconditionally as it was before any of this.
    - ``auto``: bounds and a probe. The tool is registered and the registry asks the running
      server on every advertisement and every call. A deployment therefore corrects itself in
      both directions without a restart: the tool appears once a projector is loaded beside the
      model and disappears once one is not.
    """
    if body is None or config.vision == "off":
        return None, None, noop_aclose
    bounds = CaptureBounds(
        max_edge=body_config.capture_max_edge, max_bytes=body_config.max_image_bytes
    )
    if config.vision == "on":
        return bounds, None, noop_aclose
    client = httpx.AsyncClient(timeout=PROBE_TIMEOUT_S)
    return bounds, PropsVisionProbe(config.endpoint, client), client.aclose
