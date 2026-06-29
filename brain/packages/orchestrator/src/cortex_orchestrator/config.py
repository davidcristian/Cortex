"""Orchestrator configuration: env-driven, read only at the composition root."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL
from cortex_session import DEFAULT_REDIS_URL

InferenceBackendName = Literal["echo", "llamacpp"]
MemoryBackendName = Literal["none", "pgvector"]
ToolsBackendName = Literal["none", "mcp"]
SubagentsBackendName = Literal["none", "llamacpp"]

# The logical id of the subagent tier (ADR-0004); deployments override via CORTEX_SUBAGENTS_MODEL.
DEFAULT_SUBAGENT_MODEL = "subagent"


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


class MemoryConfig(BaseSettings):
    """Whether turns recall/record durable memory (ADR-0008).

    ``none`` (the default) disables memory. The DB-less path CI and the no-GPU dev loop
    run, and the turn behaves exactly as in Slice 3. ``pgvector`` enables it and requires
    ``dsn`` (the Postgres URL) and ``embedder_endpoint`` (the base URL of the CPU embedding
    ``llama-server``).
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_MEMORY_")

    backend: MemoryBackendName = "none"
    dsn: str = ""
    embedder_endpoint: str = ""
    embedder_model: str = "embedding"

    @model_validator(mode="after")
    def _pgvector_needs_dsn_and_embedder(self) -> "MemoryConfig":
        if self.backend == "pgvector" and not (self.dsn and self.embedder_endpoint):
            msg = (
                "CORTEX_MEMORY_DSN and CORTEX_MEMORY_EMBEDDER_ENDPOINT are required when "
                "CORTEX_MEMORY_BACKEND=pgvector"
            )
            raise ValueError(msg)
        return self


class ToolsConfig(BaseSettings):
    """Whether the cortex can call tools over MCP (ADR-0009).

    ``none`` (the default) disables tools. CI and the no-GPU dev loop run with no MCP server.
    ``mcp`` enables the MCP client and requires ``endpoint`` (the streamable-http URL of the
    tool server, e.g. the filesystem sidecar in ``docker-compose.tools.yml``).
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_TOOLS_")

    backend: ToolsBackendName = "none"
    endpoint: str = ""

    @model_validator(mode="after")
    def _mcp_needs_an_endpoint(self) -> "ToolsConfig":
        if self.backend == "mcp" and not self.endpoint:
            msg = "CORTEX_TOOLS_ENDPOINT is required when CORTEX_TOOLS_BACKEND=mcp"
            raise ValueError(msg)
        return self


class SubagentsConfig(BaseSettings):
    """Whether the cortex can delegate to subagents (ADR-0010).

    ``none`` (the default) disables delegation. The cortex's tool set has no ``spawn_subagents``
    and the turn path is byte-for-byte the Slice 6 behavior, so CI and the no-GPU dev loop run
    subagent-free. ``llamacpp`` enables it and requires ``endpoint`` (the base URL of the CPU
    subagent ``llama-server`` in ``docker-compose.subagents.yml``). ``max_concurrency`` is the CPU
    budget, meaning how many subagents may run at once (RAM + concurrency, not VRAM; ADR-0004).
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_SUBAGENTS_")

    backend: SubagentsBackendName = "none"
    endpoint: str = ""
    model: str = DEFAULT_SUBAGENT_MODEL
    max_concurrency: int = Field(default=2, ge=1)

    @model_validator(mode="after")
    def _llamacpp_needs_an_endpoint(self) -> "SubagentsConfig":
        if self.backend == "llamacpp" and not self.endpoint:
            msg = "CORTEX_SUBAGENTS_ENDPOINT is required when CORTEX_SUBAGENTS_BACKEND=llamacpp"
            raise ValueError(msg)
        return self
