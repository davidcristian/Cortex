"""cortex_body_client: the brain's gRPC client of the body's BodyService (ADR-0023)."""

from cortex_body_client.gateway import GrpcBodyGateway

__all__ = ["GrpcBodyGateway"]
