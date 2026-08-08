"""The gRPC-status → ``BodyFailure`` classifier every ``GrpcBodyGateway`` call routes through.

Split from ``gateway.py`` (which owns the calls) for the same reason ``status.rs`` is split from
``client.rs`` on the body side: the classifier is the shared thing, and one table beats four
copies of a match. Thin translation only, no business logic; the core decides what each kind is
worth telling the cortex (``cortex_core.body_failure``), and this decides only which kind a wire
status is.

**The rule that makes this possible** (ADR-0023's 2026-08-08 addendum): a body that answered never
says ``UNAVAILABLE``. tonic synthesizes that code locally when a channel cannot connect, and
grpc-python does not tag a synthesized status the way tonic does, so if the body also spent it on
a shut lid the brain could never tell *there is no body* from *the body is here and has no
display*. The body's host-state failures say ``FAILED_PRECONDITION`` instead, which leaves
``UNAVAILABLE`` on this seam meaning exactly one thing.

A body older than this change still interoperates: its ``UNAVAILABLE`` for a shut lid classifies
as ``UNREACHABLE``, which is the sentence the tool used to give every failure, so it degrades to
the old behaviour rather than breaking.
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

    Any code the table does not name falls to ``BodyFailure.FAULTED``: the honest uninformative
    answer, never a claim that the body could not be reached. That is a fallback rather than an
    omission, since the seam's own handlers spend only the codes above and a body that starts
    spending another one is reporting a fault by any reading.
    """
    return _KINDS.get(err.code(), BodyFailure.FAULTED)
