"""The supervisor's HTTP control API: the wire behind the ``ModelHost`` port (ADR-0030 d3)."""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from http import HTTPStatus

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from cortex_model_manager.device_memory import DeviceMemoryProbe, NoDeviceMemory
from cortex_model_manager.supervisor import (
    ModelStatus,
    ModelSupervisor,
    SupervisorError,
    UnknownModelError,
)

_logger = logging.getLogger(__name__)

_Action = Callable[[str], Awaitable[ModelStatus]]


async def nothing_to_close() -> None:
    """The default shutdown hook, for a wiring whose adapters hold no resources of their own."""


def build_app(
    supervisor: ModelSupervisor,
    *,
    boot_model: str,
    close: Callable[[], Awaitable[None]] = nothing_to_close,
    device: DeviceMemoryProbe | None = None,
) -> Starlette:
    """The ASGI app driving ``supervisor``, starting ``boot_model`` when it comes up.

    ``device`` reads the card this daemon's children load onto; omitted, the daemon answers that
    it has none, which is what a CPU-only deployment truthfully has.
    """
    card: DeviceMemoryProbe = NoDeviceMemory() if device is None else device

    async def health(request: Request) -> Response:
        del request
        bounds = supervisor.control_bounds
        # Deliberately on this route and not a new one: it takes no per-model lock, so a caller
        # asking how much room is left can never queue behind a stop the way a `status` can, and
        # the brain reads it inside a swap step where that would cost a whole grace period.
        memory = await card.read()
        return JSONResponse(
            {
                "status": "ok",
                "models": list(supervisor.models),
                "boot_id": supervisor.boot_id,
                # All three terms of the pairing rule, in the order the rule states them: a
                # reader given only the two stop bounds can tune to a compliant-looking sum that
                # the queued probe then carries past the brain's deadline.
                "probe_timeout_s": bounds.probe_timeout_s,
                "stop_grace_s": bounds.stop_grace_s,
                "reap_timeout_s": bounds.reap_timeout_s,
                "device_free_mib": None if memory is None else memory.free_mib,
                "device_total_mib": None if memory is None else memory.total_mib,
            }
        )

    async def status(request: Request) -> Response:
        return await _answer(supervisor.status, request)

    async def start(request: Request) -> Response:
        return await _answer(_then_status(supervisor, supervisor.start), request)

    async def stop(request: Request) -> Response:
        return await _answer(_then_status(supervisor, supervisor.stop), request)

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/models/{model}", status, methods=["GET"]),
            Route("/models/{model}/start", start, methods=["POST"]),
            Route("/models/{model}/stop", stop, methods=["POST"]),
        ],
        lifespan=model_host_lifespan(supervisor, boot_model, close),
    )


def model_host_lifespan(
    supervisor: ModelSupervisor, boot_model: str, close: Callable[[], Awaitable[None]]
) -> Callable[[Starlette], AbstractAsyncContextManager[None]]:
    """Start the standing resident on the way up; stop every child on the way down."""

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None]:
        del app
        try:
            await supervisor.start(boot_model)
        except SupervisorError:
            # Serve anyway, loudly. Failing to come up would crash-loop under compose's restart
            # policy and hide the cause; a control API that answers can be asked what went wrong,
            # and the brain's own boot recovery starts the standing resident again regardless.
            _logger.exception(
                "the boot-default model could not be started; serving without it",
                extra={"model": boot_model},
            )
        try:
            yield
        finally:
            # Children first: the probe client is what tells a stop whether a child is still
            # serving, so closing it before the last stop would blind the shutdown.
            await supervisor.stop_all()
            await close()

    return lifespan


def _then_status(supervisor: ModelSupervisor, action: Callable[[str], Awaitable[None]]) -> _Action:
    """Run a verb, then report what it left behind, so a caller sees one state per request."""

    async def act(model: str) -> ModelStatus:
        await action(model)
        return await supervisor.status(model)

    return act


async def _answer(action: _Action, request: Request) -> Response:
    """Run one action for the id in the path and encode its outcome, typed failures included."""
    model = str(request.path_params["model"])
    try:
        status = await action(model)
    except UnknownModelError as err:
        return _refused(model, err, HTTPStatus.NOT_FOUND)
    except SupervisorError as err:
        return _refused(model, err, HTTPStatus.SERVICE_UNAVAILABLE)
    return JSONResponse(
        {"model": status.model, "state": status.state.value, "detail": status.detail}
    )


def _refused(model: str, err: SupervisorError, code: HTTPStatus) -> Response:
    """Encode a typed refusal, logged with the id that asked for it (never a stack per request)."""
    _logger.warning("a model-host request failed", extra={"model": model, "error": str(err)})
    return JSONResponse({"error": str(err)}, status_code=code)
