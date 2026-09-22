"""Authenticating a call on the brain's interface: the shared-secret token interceptor."""

import secrets
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

import grpc
from grpc import aio

from cortex_seam import SEAM_TOKEN_HEADER

# Deliberately does not say whether the token was absent or wrong.
_DENIED_DETAIL = "invalid or missing token"

_TRequest = TypeVar("_TRequest")
_TResponse = TypeVar("_TResponse")

# One aborting handler per RPC shape. The rejection must match the intercepted method's shape
# or gRPC cannot deliver the status, so all four exist though the service uses two.
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
    """Rejects any call that does not bear the shared secret (fail closed)."""

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
        """Whether the call's metadata has the token; the comparison is constant-time."""
        for key, value in details.invocation_metadata or ():
            if key == SEAM_TOKEN_HEADER:
                presented = value.encode() if isinstance(value, str) else bytes(value)
                return secrets.compare_digest(presented, self._token)
        return False
