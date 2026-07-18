"""The supervisor's HTTP control API: the wire behind the ``ModelHost`` port (ADR-0030 d3).

Four routes and no more, because this API can start and stop processes on the container that
holds the GPU and the models mount, and its client is the brain, which runs model-influenced code:

    GET  /health                  the daemon is up, the roster it serves, and its stop bounds
    GET  /models/{id}             one model's state (stopped | loading | ready | failed)
    POST /models/{id}/start       begin loading it (idempotent)
    POST /models/{id}/stop        end it, returning once it is reaped (idempotent)

**A request carries a logical id and nothing else.** No path, no argv, no flag, no layer count is
readable from a body or a query, so the worst a compromised client can do is start and stop the
models the deployment already declared in the daemon's own env. That is the whole point of
decision 3's rejected alternatives: a docker socket or a compose-aware controller would hand the
same client host-root, where a child-process supervisor's blast radius is its own container.

An unknown id is a 404 and a supervisor failure is a 503, which the adapter turns into the port's
``ModelHostError`` either way; the body's ``detail`` is what the log and the runbook read.
"""

import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from http import HTTPStatus

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

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
) -> Starlette:
    """The ASGI app driving ``supervisor``, starting ``boot_model`` when it comes up."""

    async def health(request: Request) -> Response:
        del request
        bounds = supervisor.stop_bounds
        return JSONResponse(
            {
                "status": "ok",
                "models": list(supervisor.models),
                "stop_grace_s": bounds.stop_grace_s,
                "reap_timeout_s": bounds.reap_timeout_s,
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
    """Start the standing resident on the way up; stop every child on the way down.

    The boot start is ADR-0030 decision 3's "at boot the daemon starts the cortex", which is what
    makes a stack that never escalates behave as the always-on service did. The shutdown stop is
    the graceful half of not leaking a process that holds VRAM; the ungraceful half is the
    container runtime, which kills a child whose supervisor's container is gone.
    """

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
