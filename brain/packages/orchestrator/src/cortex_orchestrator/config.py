"""Orchestrator configuration: env-driven, read only at the composition root."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL
from cortex_orchestrator.converse import DEFAULT_MAX_BUFFERED_EVENTS
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
    # env CORTEX_SEAM_CONVERSE_BUFFER sets how many ServerEvents one Converse stream may
    # buffer unread before generation stalls (bounded backpressure; converse.py).
    converse_buffer: int = Field(default=DEFAULT_MAX_BUFFERED_EVENTS, gt=0)

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
    # env CORTEX_VRAM_SOFT_CAP_GB is the deliberate GPU budget (ADR-0004, 14 GB); the
    # SubagentPlacer fit-tests subagents against it (ADR-0012), enforced from this slice on.
    vram_soft_cap_gb: float = Field(default=14.0, gt=0)
    # env CORTEX_VRAM_CORTEX_GB is the resident cortex's measured footprint (~11.3 GB, ADR-0004
    # addendum); the subagent GPU headroom is the cap minus this.
    cortex_reservation_gb: float = Field(
        default=11.3, ge=0, validation_alias="CORTEX_VRAM_CORTEX_GB"
    )


class InferenceConfig(BaseSettings):
    """Which InferenceBackend answers turns (ADR-0007 decision 4)."""

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
    """Whether turns recall/record durable memory (ADR-0008)."""

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
    """Whether the cortex can call tools over MCP (ADR-0009, refinements addendum)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_TOOLS_", env_nested_delimiter="__")

    backend: ToolsBackendName = "none"
    endpoint: str = ""
    endpoints: dict[str, str] = {}
    allow: dict[str, tuple[str, ...]] = {}

    @model_validator(mode="after")
    def _mcp_needs_unambiguous_endpoints(self) -> "ToolsConfig":
        if self.backend == "mcp" and not (self.endpoint or self.endpoints):
            msg = (
                "CORTEX_TOOLS_ENDPOINT or CORTEX_TOOLS_ENDPOINTS__<name> is required "
                "when CORTEX_TOOLS_BACKEND=mcp"
            )
            raise ValueError(msg)
        if self.endpoint and self.endpoints:
            msg = "set CORTEX_TOOLS_ENDPOINT or CORTEX_TOOLS_ENDPOINTS__<name>, not both"
            raise ValueError(msg)
        if unmatched := set(self.allow) - set(self.named_endpoints):
            msg = f"CORTEX_TOOLS_ALLOW names no configured endpoint: {sorted(unmatched)}"
            raise ValueError(msg)
        return self

    @property
    def named_endpoints(self) -> dict[str, str]:
        """Every configured endpoint by name, sorted by name so precedence is deterministic."""
        if self.endpoints:
            return dict(sorted(self.endpoints.items()))
        if self.endpoint:
            return {"default": self.endpoint}
        return {}


class SubagentsConfig(BaseSettings):
    """Whether the cortex can delegate to subagents (ADR-0010, ADR-0012)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SUBAGENTS_")

    backend: SubagentsBackendName = "none"
    endpoint: str = ""
    gpu_endpoint: str = ""
    model: str = DEFAULT_SUBAGENT_MODEL
    vram_gb: float = Field(default=2.0, gt=0)
    cpus: float = Field(default=2.0, gt=0)
    memory_gb: float = Field(default=2.0, gt=0)
    cpu_budget: float = Field(default=4.0, gt=0)
    mem_budget_gb: float = Field(default=8.0, gt=0)

    @model_validator(mode="after")
    def _llamacpp_needs_both_endpoints(self) -> "SubagentsConfig":
        if self.backend == "llamacpp" and not (self.endpoint and self.gpu_endpoint):
            msg = (
                "CORTEX_SUBAGENTS_ENDPOINT and CORTEX_SUBAGENTS_GPU_ENDPOINT are required when "
                "CORTEX_SUBAGENTS_BACKEND=llamacpp"
            )
            raise ValueError(msg)
        return self
