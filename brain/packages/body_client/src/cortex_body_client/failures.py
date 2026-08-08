"""Turn a gRPC status into a ``BodyFailure``, for every ``GrpcBodyGateway`` call."""

from collections.abc import Mapping

import grpc
from grpc import aio

from cortex_core import BodyFailure

_KINDS: Mapping[grpc.StatusCode, BodyFailure] = {
    # No answer arrived: no route, or none in the time the call allowed.
    grpc.StatusCode.UNAVAILABLE: BodyFailure.UNREACHABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED: BodyFailure.UNREACHABLE,
    # The body answered and declined, by kill switch or by the shared token.
    grpc.StatusCode.PERMISSION_DENIED: BodyFailure.REFUSED,
    grpc.StatusCode.UNAUTHENTICATED: BodyFailure.REFUSED,
    # The body answered and has no such RPC: an older body, or one built without the capability.
    grpc.StatusCode.UNIMPLEMENTED: BodyFailure.UNSUPPORTED,
    # The body answered and the host state it needs is not there: no display, no audio endpoint.
    grpc.StatusCode.FAILED_PRECONDITION: BodyFailure.UNREADY,
    # The work was done and its result will not fit the interface's budget.
    grpc.StatusCode.RESOURCE_EXHAUSTED: BodyFailure.OVERSIZE,
}


def kind_of(err: aio.AioRpcError) -> BodyFailure:
    """Classify one gRPC failure into the port's error currency."""
    return _KINDS.get(err.code(), BodyFailure.FAULTED)
