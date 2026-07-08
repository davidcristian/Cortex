"""cortex_body_client: the brain's gRPC client of the body's BodyService (ADR-0023).

The typed ``BodyService`` client wrapper ADR-0003 reserved for Slice 9: ``GrpcBodyGateway``
implements the core's ``BodyGateway`` port over the committed seam stubs, so the brain can call
the host body (volume now; more OS actions later) behind the unchanged port.
"""

from cortex_body_client.gateway import GrpcBodyGateway

__all__ = ["GrpcBodyGateway"]
