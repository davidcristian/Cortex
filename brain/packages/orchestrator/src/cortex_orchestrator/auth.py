"""Seam authentication: the shared-secret token interceptor (assumption 5, ADR-0016).

The seam's security posture is loopback-only listeners **plus** a shared-secret token via
env, and this module is the token half. When `CORTEX_SEAM_TOKEN` is set, the server rejects
every call whose metadata does not carry the matching `x-cortex-seam-token` value with
`UNAUTHENTICATED`, before any servicer code runs. An interceptor rather than per-RPC checks
so the rule is structural: a method added to the service later is covered by construction,
not by remembering. Comparison is constant-time (`secrets.compare_digest`). An empty token
disables the interceptor entirely at the composition root (`create_server`), and loopback-only
remains the outer boundary either way.
"""

import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

import grpc
from grpc import aio

# The metadata key the body's client attaches the token under (lowercase per gRPC rules).
# Its home is the seam facade (ADR-0023); this interceptor reads it to authorize inbound calls.
from cortex_seam import SEAM_TOKEN_HEADER

# What a rejected caller sees; deliberately silent on whether the token was absent or wrong.
_DENIED_DETAIL = "invalid or missing seam token"

_TRequest = TypeVar("_TRequest")
_TResponse = TypeVar("_TResponse")

# One aborting-handler constructor per RPC shape, keyed by (request_streaming,
# response_streaming). The rejection must match the intercepted method's shape or gRPC
# cannot deliver the status. Data, not branches: all four exist, the service uses two today.
_HANDLER_FACTORIES = {
    (False, False): grpc.unary_unary_rpc_method_handler,
    (False, True): grpc.unary_stream_rpc_method_handler,
    (True, False): grpc.stream_unary_rpc_method_handler,
    (True, True): grpc.stream_stream_rpc_method_handler,
}


async def _deny_unary(request: object, context: aio.ServicerContext[object, object]) -> object:
    """The rejection behavior for a unary-response method: abort (which always raises)."""
    del request
    await context.abort(grpc.StatusCode.UNAUTHENTICATED, _DENIED_DETAIL)


async def _deny_stream(
    request: object, context: aio.ServicerContext[object, object]
) -> AsyncIterator[object]:
    """The rejection behavior for a stream-response method: abort before any event."""
    del request
    await context.abort(grpc.StatusCode.UNAUTHENTICATED, _DENIED_DETAIL)
    yield None  # pragma: no cover - unreachable (abort raises); only shapes the generator


def _rejection_like[TRequest, TResponse](
    handler: "grpc.RpcMethodHandler[TRequest, TResponse]",
) -> "grpc.RpcMethodHandler[TRequest, TResponse]":
    """An UNAUTHENTICATED-aborting handler of the same shape as ``handler``."""
    behavior = _deny_stream if handler.response_streaming else _deny_unary
    factory = _HANDLER_FACTORIES[(handler.request_streaming, handler.response_streaming)]
    return factory(
        behavior,
        request_deserializer=handler.request_deserializer,
        response_serializer=handler.response_serializer,
    )


class SeamTokenInterceptor(aio.ServerInterceptor):
    """Rejects any seam call not bearing the shared secret (fail closed, ADR-0016).

    Constructed only when a non-empty token is configured; every RPC on the server then
    requires the matching ``x-cortex-seam-token`` metadata value. The check runs before the
    servicer, and a mismatch aborts with ``UNAUTHENTICATED`` through a handler of the
    intercepted method's own shape.
    """

    def __init__(self, token: str) -> None:
        self._token = token.encode()

    async def intercept_service(
        self,
        continuation: Callable[
            [grpc.HandlerCallDetails],
            Awaitable["grpc.RpcMethodHandler[_TRequest, _TResponse] | None"],
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> "grpc.RpcMethodHandler[_TRequest, _TResponse] | None":
        """Pass an authorized call through untouched; reshape everything else into a denial."""
        handler = await continuation(handler_call_details)
        if handler is None or self._authorized(handler_call_details):
            return handler
        return _rejection_like(handler)

    def _authorized(self, details: grpc.HandlerCallDetails) -> bool:
        """Whether the call's metadata carries the token; constant-time on the compare."""
        for key, value in details.invocation_metadata or ():
            if key == SEAM_TOKEN_HEADER:
                presented = value.encode() if isinstance(value, str) else bytes(value)
                return secrets.compare_digest(presented, self._token)
        return False
