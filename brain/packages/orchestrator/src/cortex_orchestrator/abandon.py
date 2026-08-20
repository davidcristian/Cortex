"""The line a call leaves behind when the caller stopped waiting for it (ADR-0024).

The body announces a deadline on every unary call it makes, and `grpc.aio` enforces it by
cancelling the servicer coroutine when the client drops the call. That much needs no brain code
and has always worked. What it leaves behind is nothing: an abandoned call unwinds through the
handler's own `finally` blocks and disappears, indistinguishable in the logs from a call that was
never made. So the brain does the one thing with the announced deadline that needs no per-RPC
judgement about what "not enough time left" means, and says the call was abandoned, with the
remaining time it can finally read printed beside it.

**The reading is printed, never judged.** `time_remaining()` answers three different facts and
this module decides between none of them: zero is the announced deadline expiring, arriving
exactly as designed (grpc clamps the reading there rather than letting it run negative); a value
above zero is a caller that stopped waiting early, which is the shipped body on every call, since
it enforces a bound strictly shorter than the one it announces (ADR-0024's grace margin); `None`
is a caller that announced no deadline at all, so what ended the call was a disconnect. An
operator reads the number; nothing here branches on it.

**Only the unary methods are watched, which is the fence rather than an oversight.** `Converse`
announces no deadline and must keep announcing none: a turn is long by design, and a stream that
reported an abandonment against a deadline would be the first half of enforcing a bound this seam
deliberately does not have. It is the one streaming method on the service, so "unary-unary or pass
it through untouched" is that fence written as code rather than as a list of ten method names
somebody has to keep current.

An interceptor rather than ten `try` blocks, for the reason the token interceptor is one
(`auth.py`): a unary method added to the service later is covered by construction, not by
remembering.
"""

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

# The shape of a unary-unary servicer behavior under `grpc.aio`. Spelled here because
# `grpc-stubs` types `RpcMethodHandler.unary_unary` with the *synchronous* server's signature,
# which returns the reply rather than a coroutine yielding it; every behavior this server holds
# is an `async def` on `BrainService`.
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
    """Logs every unary call the caller gave up on, and touches nothing else.

    Installed unconditionally by `create_server`, unlike the token interceptor beside it: there is
    no posture to configure here, only a line that is written or lost. A method with no
    unary-unary behavior (`Converse`, the service's one stream) and an unserviced method (the
    continuation resolving to `None`) are both handed back exactly as they arrived.
    """

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
