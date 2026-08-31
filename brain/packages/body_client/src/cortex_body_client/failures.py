"""The gRPC-status → ``BodyFailure`` classifier every ``GrpcBodyGateway`` call routes through.

Split from ``gateway.py`` so one table serves all four calls, the same split ``status.rs`` and
``client.rs`` have on the body side. Thin translation only, no business logic: the core decides
what each kind is worth telling the cortex (``cortex_core.body_failure``), and this decides only
which kind a wire status is.

A body that answered never says ``UNAVAILABLE`` (ADR-0023's 2026-08-08 addendum). tonic
synthesizes that code locally when a channel cannot connect, and grpc-python does not tag a
synthesized status the way tonic does, so a body that also spent it on a shut lid would leave the
brain unable to tell "there is no body" from "the body is here and has no display". The body's
host-state failures say ``FAILED_PRECONDITION`` instead, which leaves ``UNAVAILABLE`` on this seam
meaning one thing.

A body older than that change still interoperates: its ``UNAVAILABLE`` for a shut lid classifies
as ``UNREACHABLE``, the sentence the tool used to give every failure.
"""

from collections.abc import Mapping

import grpc
from grpc import aio

from cortex_core import BodyFailure

_KINDS: Mapping[grpc.StatusCode, BodyFailure] = {
    # No answer arrived: no route, or none in the time the call allowed.
    grpc.StatusCode.UNAVAILABLE: BodyFailure.UNREACHABLE,
    grpc.StatusCode.DEADLINE_EXCEEDED: BodyFailure.UNREACHABLE,
    # The body answered and declined, by kill switch or by seam token.
    grpc.StatusCode.PERMISSION_DENIED: BodyFailure.REFUSED,
    grpc.StatusCode.UNAUTHENTICATED: BodyFailure.REFUSED,
    # The body answered and has no such RPC: an older body, or one built without the capability.
    grpc.StatusCode.UNIMPLEMENTED: BodyFailure.UNSUPPORTED,
    # The body answered and the host state it needs is not there (no display, no audio endpoint).
    grpc.StatusCode.FAILED_PRECONDITION: BodyFailure.UNREADY,
    # The work was done and its result will not fit the seam's budget.
    grpc.StatusCode.RESOURCE_EXHAUSTED: BodyFailure.OVERSIZE,
}


def kind_of(err: aio.AioRpcError) -> BodyFailure:
    """Classify one gRPC failure into the port's error currency.

    Any code the table does not name falls to ``BodyFailure.FAULTED`` rather than to a claim that
    the body could not be reached. The seam's own handlers spend only the codes above, so a body
    that starts spending another one is reporting a fault.
    """
    return _KINDS.get(err.code(), BodyFailure.FAULTED)
