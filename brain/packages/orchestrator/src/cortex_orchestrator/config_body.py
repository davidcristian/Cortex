"""Whether the cortex can call the host body over ``BodyService``, and how long it may wait."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_body_client import DEFAULT_CALL_TIMEOUT_S, DEFAULT_CAPTURE_TIMEOUT_S
from cortex_core import MAX_IMAGE_BYTES, MAX_IMAGE_EDGE

BodyBackendName = Literal["none", "grpc"]

# The edge the brain asks the body for. It asks for 2048 rather than the body's own 1600, the
# brain half of a measured pair: with the model host's image token budget at 1024, a 4K desktop
# goes from 6 to 8 of 47 ground-truth strings read to 36 to 38.
DEFAULT_CAPTURE_MAX_EDGE = 2048


class BodyConfig(BaseSettings):
    """Whether the cortex can call the host body over ``BodyService``."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_BODY_")

    backend: BodyBackendName = "none"
    endpoint: str = ""
    # 0 asks for nothing, and the body then answers at its own conservative 1600, where even an
    # incompressible screen encodes inside the byte ceiling.
    capture_max_edge: int = Field(default=DEFAULT_CAPTURE_MAX_EDGE, ge=0, le=MAX_IMAGE_EDGE)
    max_image_bytes: int = Field(default=MAX_IMAGE_BYTES, gt=0, le=MAX_IMAGE_BYTES)
    # Two deadlines because the calls differ: a capture is legitimately slow, while every other
    # call is fast when it works and unbounded when it is not, the body running each handler on
    # a blocking thread that a COM call can park for as long as the host takes.
    capture_timeout_s: float = Field(default=DEFAULT_CAPTURE_TIMEOUT_S, gt=0)
    call_timeout_s: float = Field(default=DEFAULT_CALL_TIMEOUT_S, gt=0)

    @model_validator(mode="after")
    def _grpc_needs_an_endpoint(self) -> "BodyConfig":
        if self.backend == "grpc" and not self.endpoint:
            msg = "CORTEX_BODY_ENDPOINT is required when CORTEX_BODY_BACKEND=grpc"
            raise ValueError(msg)
        return self
