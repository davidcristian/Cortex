"""cortex_body_client: the brain's gRPC client of the body's BodyService."""

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
