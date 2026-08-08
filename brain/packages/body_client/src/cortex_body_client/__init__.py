"""cortex_body_client: the brain's gRPC client of the body's BodyService (ADR-0023)."""

from cortex_body_client.failures import kind_of
from cortex_body_client.gateway import MAX_RECEIVE_BYTES, GrpcBodyGateway

__all__ = ["MAX_RECEIVE_BYTES", "GrpcBodyGateway", "kind_of"]
