"""Orchestrator configuration: env-driven, read only at the composition root."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL
from cortex_session import DEFAULT_REDIS_URL

InferenceBackendName = Literal["echo", "llamacpp"]


class SeamServerConfig(BaseSettings):
    """Where the brain hosts BrainService (loopback-only per ROADMAP assumption 5)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SEAM_")

    host: str = "127.0.0.1"
    port: int = 50051

    @property
    def bind_address(self) -> str:
        """The `host:port` string handed to grpc's `add_insecure_port`."""
        return f"{self.host}:{self.port}"


class BrainRuntimeConfig(BaseSettings):
    """Runtime wiring knobs: which store holds the state, which model answers.

    Read exclusively by the composition root (`wiring.run_from_env`). The core and
    the adapters receive plain values, never settings objects or env access.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_", validate_by_name=True)

    # env CORTEX_REDIS_URL is where the session state lives (the one hard rule).
    redis_url: str = DEFAULT_REDIS_URL
    # env CORTEX_MODEL_CORTEX is a LOGICAL model id (ADR-0004), never a file path.
    # The dictated env name breaks the prefix pattern, hence the explicit alias.
    cortex_model: str = Field(default=DEFAULT_CORTEX_MODEL, validation_alias="CORTEX_MODEL_CORTEX")


class InferenceConfig(BaseSettings):
    """Which InferenceBackend answers turns (ADR-0007 decision 4).

    ``echo`` (the default) is the GPU-less scripted fake, what CI and the no-GPU dev
    loop run. ``llamacpp`` selects the real adapter and requires ``endpoint`` (the base
    URL of the resident model's ``llama-server``, set by ``docker-compose.gpu.yml``).
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_INFERENCE_")

    backend: InferenceBackendName = "echo"
    endpoint: str = ""

    @model_validator(mode="after")
    def _llamacpp_needs_an_endpoint(self) -> "InferenceConfig":
        if self.backend == "llamacpp" and not self.endpoint:
            msg = "CORTEX_INFERENCE_ENDPOINT is required when CORTEX_INFERENCE_BACKEND=llamacpp"
            raise ValueError(msg)
        return self
