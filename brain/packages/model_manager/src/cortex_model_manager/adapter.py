"""The real ``ModelHost``: the port's four verbs over the supervisor's control API (ADR-0030 d3).

This half runs in the **brain** container and holds no process knowledge at all. It sends a
logical id and reads back one of the port's four states, which is the whole reason artifact paths,
ports and ``-ngl`` never cross the port: a deployment re-points a tier by changing the sidecar's
env, and the brain never learns.

Two policies, both deliberate:

- **Every failure is a ``ModelHostError``, and nothing is retried here.** A transport failure, a
  refusal, a body that will not decode, a state word this version does not know: all of them mean
  the same thing to the swap, which is "the model host did not answer the question", and the swap
  is what decides whether that aborts a handoff or fails a restore. Retrying inside the adapter
  would hide a dead supervisor behind the load timeout instead of failing the swap fast.
- **A FAILED state is a normal answer, logged loudly.** The health gate returns FAILED at once
  rather than waiting out its bound, and the sidecar's ``detail`` is the only place the exit code
  appears on the brain's side, so it is logged where the swap's own failure note will be read.
- **A missing device reading is a normal answer too, and never an error.** The fourth verb asks
  how much of the card is free, and a daemon with no GPU (or one too old to report it) says so
  with a body that carries neither figure. Refusing on that belongs to the swap, which knows
  whether anything asked for a fit; the adapter's job is only to say what came back. The fifth
  verb reads the daemon's own timing bounds off the same body and answers the same way, so a
  daemon older than those fields leaves the composition root's pairing check with nothing to
  compare rather than with a number it invented.
"""

import logging
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from cortex_core import ControlBounds, DeviceMemory, ModelHostError, ModelHostState

_logger = logging.getLogger(__name__)


def _about(model: str) -> str:
    """How a control call names the model it is about, in a failure a human has to read."""
    return f"model {model!r}"


def _seconds(value: object) -> float | None:
    """A second count off the wire, or ``None`` for anything this version cannot read as one.

    A bool is refused although Python calls it an int, and so is a negative: both would reduce
    the worst case the caller checks its own deadline against, and a bound that flatters itself
    is worse than an absent one, which at least says so.
    """
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        return None
    return float(value)


class HttpModelHost:
    """``ModelHost`` over the ``model-host`` sidecar at ``endpoint`` (compose-network URL).

    The client is injected so its timeout is set once at the composition root. Unlike the
    generation clients, it must have a real read deadline: a control call that hung would hang a
    swap step under no bound at all.
    """

    def __init__(self, endpoint: str, client: httpx.AsyncClient) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._client = client

    async def start(self, model: str) -> None:
        """Ask the sidecar to begin loading ``model``; readiness is a later ``status`` question."""
        await self._act(model, "start")

    async def stop(self, model: str) -> None:
        """Ask the sidecar to end ``model``; it answers once the child is reaped, not before."""
        await self._act(model, "stop")

    async def status(self, model: str) -> ModelHostState:
        """What the sidecar says ``model``'s process is doing right now."""
        payload = await self._request("GET", self._model_path(model), _about(model))
        return self._read(model, payload)

    async def device_memory(self) -> DeviceMemory | None:
        """How much of the sidecar's card is free, or ``None`` when it can see no card.

        Off ``GET /health``, which is the one route that takes no per-model lock: a swap asks this
        between an eviction and a load, and a question that queued behind a stop would add that
        stop's whole grace to the answer. A body from a daemon too old to carry the two fields
        reads as no card, which is the same fail-closed answer as a daemon that has none, and the
        right one either way: a brain that cannot get a reading must not act as if it fitted.
        """
        payload = await self._request("GET", "/health", "the device it runs on")
        free = payload.get("device_free_mib")
        total = payload.get("device_total_mib")
        if not isinstance(free, int) or not isinstance(total, int):
            _logger.info(
                "the model host reports no device memory: free=%r total=%r",
                free,
                total,
                extra={"free": free, "total": total},
            )
            return None
        return DeviceMemory(free_mib=free, total_mib=total)

    async def control_bounds(self) -> ControlBounds | None:
        """How long this sidecar's slowest control call may take, or ``None`` if it will not say.

        Off the same ``GET /health``, and asked once at wiring time rather than per call: these
        three are the sidecar's env, so they cannot change under a running container. A body
        missing any of them (a daemon older than the probe-timeout field, or one that is not this
        daemon at all) reads as no bounds, which leaves the deadline pairing unchecked instead of
        checked against a partial sum that would pass whatever the operator set.
        """
        payload = await self._request("GET", "/health", "the bounds of its own control calls")
        probe = _seconds(payload.get("probe_timeout_s"))
        grace = _seconds(payload.get("stop_grace_s"))
        reap = _seconds(payload.get("reap_timeout_s"))
        if probe is None or grace is None or reap is None:
            _logger.info(
                "the model host reports no control bounds: probe=%r grace=%r reap=%r",
                probe,
                grace,
                reap,
                extra={"probe": probe, "grace": grace, "reap": reap},
            )
            return None
        return ControlBounds(probe_timeout_s=probe, stop_grace_s=grace, reap_timeout_s=reap)

    async def _act(self, model: str, verb: str) -> None:
        """Run a lifecycle verb and read the state it left behind, for the log."""
        payload = await self._request("POST", f"{self._model_path(model)}/{verb}", _about(model))
        state = self._read(model, payload)
        _logger.info(
            "asked the model host for a lifecycle change: model=%s verb=%s state=%s",
            model,
            verb,
            state.value,
            extra={"model": model, "verb": verb, "state": state.value},
        )

    def _model_path(self, model: str) -> str:
        """The route for one logical id, escaped: an id is a name, never a path fragment."""
        return f"/models/{quote(model, safe='')}"

    async def _request(self, method: str, path: str, subject: str) -> dict[str, Any]:
        """One control call, with every failure shape collapsed into ``ModelHostError``.

        ``subject`` is what the call was about, already phrased for a message, because the four
        lifecycle routes ask about a model and the health route asks about the card.
        """
        try:
            response = await self._client.request(method, f"{self._endpoint}{path}")
        except httpx.HTTPError as err:
            msg = f"the model host at {self._endpoint!r} did not answer for {subject}: {err}"
            raise ModelHostError(msg) from err
        if response.status_code != HTTPStatus.OK:
            msg = (
                f"the model host refused {method} {path} for {subject} with HTTP "
                f"{response.status_code}: {response.text.strip()[:200]}"
            )
            raise ModelHostError(msg)
        try:
            body: object = response.json()
        except ValueError as err:
            msg = f"the model host answered unparseable JSON for {subject}"
            raise ModelHostError(msg) from err
        if not isinstance(body, dict):
            msg = f"the model host answered a {type(body).__name__}, not an object"
            raise ModelHostError(msg)
        return cast("dict[str, Any]", body)

    def _read(self, model: str, payload: dict[str, Any]) -> ModelHostState:
        """The state word from a control answer, refusing anything this version cannot name."""
        raw = payload.get("state")
        try:
            state = ModelHostState(raw)
        except ValueError as err:
            msg = f"the model host reported state {raw!r} for model {model!r}, which is not known"
            raise ModelHostError(msg) from err
        if state is ModelHostState.FAILED:
            detail = str(payload.get("detail", ""))
            _logger.error(
                "a hosted model process has failed: model=%s detail=%s",
                model,
                detail,
                extra={"model": model, "detail": detail},
            )
        return state
