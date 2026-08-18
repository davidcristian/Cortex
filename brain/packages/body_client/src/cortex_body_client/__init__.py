"""cortex_body_client: the brain's gRPC client of the body's BodyService (ADR-0023).

The typed ``BodyService`` client wrapper ADR-0003 reserved for Slice 9: ``GrpcBodyGateway``
implements the core's ``BodyGateway`` port over the committed seam stubs, so the brain can call
the host body (volume, the reminder toast, and a screen capture) behind the unchanged port.
``MAX_RECEIVE_BYTES`` is the one transport limit this seam raises, for the one direction that
carries a payload (ADR-0029). ``kind_of`` is the status-code classifier every call routes its
failures through, so the port's ``BodyGatewayError`` arrives carrying how far the call got.

The two deadline defaults are exported because the orchestrator's ``BodyConfig`` publishes them
as env knobs and must not restate the numbers: this package owns the calls, so it owns how long
they may take, and a settings module that spelled its own copy would be a second default nothing
holds to the first (ADR-0029's uniform-deadline addendum).
"""

from cortex_body_client.failures import kind_of
from cortex_body_client.gateway import (
    DEFAULT_CALL_TIMEOUT_S,
    DEFAULT_CAPTURE_TIMEOUT_S,
    MAX_RECEIVE_BYTES,
    GrpcBodyGateway,
)

__all__ = [
    "DEFAULT_CALL_TIMEOUT_S",
    "DEFAULT_CAPTURE_TIMEOUT_S",
    "MAX_RECEIVE_BYTES",
    "GrpcBodyGateway",
    "kind_of",
]
