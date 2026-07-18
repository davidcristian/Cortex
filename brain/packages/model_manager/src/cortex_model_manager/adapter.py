"""The real ``ModelHost``: the port's three verbs over the supervisor's control API (ADR-0030 d3).

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
"""

import logging
from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from cortex_core import ModelHostError, ModelHostState

_logger = logging.getLogger(__name__)


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
        return self._read(model, await self._request("GET", self._model_path(model), model))

    async def _act(self, model: str, verb: str) -> None:
        """Run a lifecycle verb and read the state it left behind, for the log."""
        payload = await self._request("POST", f"{self._model_path(model)}/{verb}", model)
        state = self._read(model, payload)
        _logger.info(
            "asked the model host for a lifecycle change",
            extra={"model": model, "verb": verb, "state": state.value},
        )

    def _model_path(self, model: str) -> str:
        """The route for one logical id, escaped: an id is a name, never a path fragment."""
        return f"/models/{quote(model, safe='')}"

    async def _request(self, method: str, path: str, model: str) -> dict[str, Any]:
        """One control call, with every failure shape collapsed into ``ModelHostError``."""
        try:
            response = await self._client.request(method, f"{self._endpoint}{path}")
        except httpx.HTTPError as err:
            msg = f"the model host at {self._endpoint!r} did not answer for model {model!r}: {err}"
            raise ModelHostError(msg) from err
        if response.status_code != HTTPStatus.OK:
            msg = (
                f"the model host refused {method} {path} for model {model!r} with HTTP "
                f"{response.status_code}: {response.text.strip()[:200]}"
            )
            raise ModelHostError(msg)
        try:
            body: object = response.json()
        except ValueError as err:
            msg = f"the model host answered unparseable JSON for model {model!r}"
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
            _logger.error(
                "a hosted model process has failed",
                extra={"model": model, "detail": str(payload.get("detail", ""))},
            )
        return state
