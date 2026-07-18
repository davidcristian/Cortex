"""cortex_body_client: the brain's gRPC client of the body's BodyService (ADR-0023).

The typed ``BodyService`` client wrapper ADR-0003 reserved for Slice 9: ``GrpcBodyGateway``
implements the core's ``BodyGateway`` port over the committed seam stubs, so the brain can call
the host body (volume, the reminder toast, and a screen capture) behind the unchanged port.
``MAX_RECEIVE_BYTES`` is the one transport limit this seam raises, for the one direction that
carries a payload (ADR-0029).
"""

from cortex_body_client.gateway import MAX_RECEIVE_BYTES, GrpcBodyGateway

__all__ = ["MAX_RECEIVE_BYTES", "GrpcBodyGateway"]
