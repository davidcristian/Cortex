"""Whether the cortex can call the host body over ``BodyService``, and how long it may wait."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_body_client import DEFAULT_CALL_TIMEOUT_S, DEFAULT_CAPTURE_TIMEOUT_S
from cortex_core import MAX_IMAGE_BYTES, MAX_IMAGE_EDGE

BodyBackendName = Literal["none", "grpc"]


class BodyConfig(BaseSettings):
    """Whether the cortex can call the host body over ``BodyService`` (ADR-0023)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_BODY_")

    backend: BodyBackendName = "none"
    endpoint: str = ""
    capture_max_edge: int = Field(default=2048, ge=0, le=MAX_IMAGE_EDGE)
    max_image_bytes: int = Field(default=MAX_IMAGE_BYTES, gt=0, le=MAX_IMAGE_BYTES)
    capture_timeout_s: float = Field(default=DEFAULT_CAPTURE_TIMEOUT_S, gt=0)
    call_timeout_s: float = Field(default=DEFAULT_CALL_TIMEOUT_S, gt=0)

    @model_validator(mode="after")
    def _grpc_needs_an_endpoint(self) -> "BodyConfig":
        if self.backend == "grpc" and not self.endpoint:
            msg = "CORTEX_BODY_ENDPOINT is required when CORTEX_BODY_BACKEND=grpc"
            raise ValueError(msg)
        return self
