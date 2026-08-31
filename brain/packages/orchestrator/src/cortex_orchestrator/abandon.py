"""Logging the calls whose caller stopped waiting for them."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

import grpc
from grpc import aio

_TRequest = TypeVar("_TRequest")
_TResponse = TypeVar("_TResponse")

_logger = logging.getLogger(__name__)

ABANDONED_MESSAGE = "the caller stopped waiting; this call was abandoned mid-flight"

# Declared here because ``grpc-stubs`` types ``RpcMethodHandler.unary_unary`` with the
# synchronous server's signature, which returns the reply rather than a coroutine yielding it.
type _UnaryBehavior = Callable[[object, aio.ServicerContext[object, object]], Awaitable[object]]


def _watched(behavior: _UnaryBehavior, method: str) -> _UnaryBehavior:
    """``behavior``, with an abandonment line on the way out of a cancellation."""

    async def watch(request: object, context: aio.ServicerContext[object, object]) -> object:
        try:
            return await behavior(request, context)
        except asyncio.CancelledError:
            _logger.warning(
                ABANDONED_MESSAGE,
                extra={"method": method, "time_remaining": context.time_remaining()},
            )
            raise

    return watch


class AbandonedCallInterceptor(aio.ServerInterceptor):
    """Logs every unary call the caller gave up on, and touches nothing else."""

    async def intercept_service(
        self,
        continuation: Callable[
            [grpc.HandlerCallDetails],
            Awaitable["grpc.RpcMethodHandler[_TRequest, _TResponse] | None"],
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> "grpc.RpcMethodHandler[_TRequest, _TResponse] | None":
        """Wrap a unary-unary handler in the watch; pass everything else through untouched."""
        handler = await continuation(handler_call_details)
        if handler is None or handler.unary_unary is None:
            return handler
        return grpc.unary_unary_rpc_method_handler(
            _watched(cast("_UnaryBehavior", handler.unary_unary), handler_call_details.method),
            request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer,
        )
