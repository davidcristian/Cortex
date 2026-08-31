"""The supervisor's HTTP control API: the wire behind the ``ModelHost`` port."""

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
    """The ASGI app driving ``supervisor``, starting ``boot_model`` when it comes up."""
    card: DeviceMemoryProbe = NoDeviceMemory() if device is None else device

    async def health(request: Request) -> Response:
        del request
        bounds = supervisor.control_bounds
        memory = await card.read()
        return JSONResponse(
            {
                "status": "ok",
                "models": list(supervisor.models),
                "boot_id": supervisor.boot_id,
                "probe_timeout_s": bounds.probe_timeout_s,
                "stop_grace_s": bounds.stop_grace_s,
                "reap_timeout_s": bounds.reap_timeout_s,
                # On this route rather than one of its own: it takes no per-model lock, so a
                # caller asking how much room is left never queues behind a stop.
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
    """Start the resident model on the way up; stop every child on the way down."""

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncGenerator[None]:
        del app
        try:
            await supervisor.start(boot_model)
        except SupervisorError:
            # Serve anyway: failing to come up would crash-loop under compose's restart policy
            # and bury the cause, and the brain's boot recovery starts the resident again.
            _logger.exception(
                "the boot-default model could not be started; serving without it",
                extra={"model": boot_model},
            )
        try:
            yield
        finally:
            # Children first: `close` shuts the probe client the supervisor was wired with.
            await supervisor.stop_all()
            await close()

    return lifespan


def _then_status(supervisor: ModelSupervisor, action: Callable[[str], Awaitable[None]]) -> _Action:
    """Run a verb, then report the state it left the model in, so one request yields one state."""

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
    """Encode a typed failure, logged with the id that asked for it (never a stack per request)."""
    level = logging.ERROR if code >= HTTPStatus.INTERNAL_SERVER_ERROR else logging.WARNING
    _logger.log(level, "a model-host request failed", extra={"model": model, "error": str(err)})
    return JSONResponse({"error": str(err)}, status_code=code)
