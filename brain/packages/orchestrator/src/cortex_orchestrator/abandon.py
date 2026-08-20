"""The line a call leaves behind when the caller stopped waiting for it (ADR-0024)."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar, cast

import grpc
from grpc import aio

_TRequest = TypeVar("_TRequest")
_TResponse = TypeVar("_TResponse")

_logger = logging.getLogger(__name__)

# What an abandoned call prints, as a constant so the suite asserts the line an operator greps
# for. It says who stopped rather than what expired, because the fields say which of the two
# it was and this sentence is true of both.
ABANDONED_MESSAGE = "the caller stopped waiting; this call was abandoned mid-flight"

type _UnaryBehavior = Callable[[object, aio.ServicerContext[object, object]], Awaitable[object]]


def _watched(behavior: _UnaryBehavior, method: str) -> _UnaryBehavior:
    """``behavior``, with an abandonment line on the way out of a cancellation."""

    async def watch(request: object, context: aio.ServicerContext[object, object]) -> object:
        try:
            return await behavior(request, context)
        except asyncio.CancelledError:
            # Re-raised, always: a cancelled coroutine that swallows its cancellation is a task
            # that outlives the request. This arm only makes the abandonment visible.
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
