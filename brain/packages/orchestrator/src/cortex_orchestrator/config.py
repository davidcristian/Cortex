"""Orchestrator configuration: env-driven, read only at the composition root."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL
from cortex_orchestrator.converse import DEFAULT_CONFIRM_TIMEOUT_S, DEFAULT_MAX_BUFFERED_EVENTS
from cortex_session import DEFAULT_REDIS_URL

InferenceBackendName = Literal["echo", "llamacpp"]
VisionMode = Literal["auto", "on", "off"]
MemoryBackendName = Literal["none", "pgvector"]
MemoryScopeName = Literal["global", "session"]
MemoryRecallName = Literal["raw", "reranked", "mmr", "recency_mmr", "judge"]
MemoryTaintPolicyName = Literal["skip", "record"]
OutputGuardrailName = Literal["redact", "lookalike", "strict", "off"]

# Which answer the capture tool's advertisement takes when nothing overrides it. Named for the
# reason the port below is: the body override ships it again as a substitution default, so the
# scan can hold the two together only if one of them is a declaration it can read.
DEFAULT_VISION_MODE: VisionMode = "auto"

DEFAULT_SEAM_PORT = 50051


class SeamServerConfig(BaseSettings):
    """Where (and to whom) the brain hosts BrainService."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SEAM_")

    host: str = "127.0.0.1"
    port: int = DEFAULT_SEAM_PORT
    # env CORTEX_SEAM_TOKEN is the shared secret both sides read from env (never the repo).
    token: str = ""
    # env CORTEX_SEAM_CONVERSE_BUFFER sets how many ServerEvents one Converse stream may
    # buffer unread before generation stalls (bounded backpressure; converse.py).
    converse_buffer: int = Field(default=DEFAULT_MAX_BUFFERED_EVENTS, gt=0)
    # env CORTEX_SEAM_CONFIRM_TIMEOUT_S sets how long a gated tool call waits for the user's
    # answer to a ConfirmRequest before it is denied (fail-closed, ADR-0022). Generous for
    # a human decision, bounded so an unattended overlay cannot hang a turn forever.
    confirm_timeout_s: float = Field(default=DEFAULT_CONFIRM_TIMEOUT_S, gt=0)

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
    cortex_reservation_gb: float = Field(
        default=8.6, ge=0, validation_alias="CORTEX_VRAM_CORTEX_GB"
    )
    history_char_budget: int = Field(default=48_000, ge=0)
    history_summary: bool = True
    history_recap_min_chars: int = Field(default=2_000, ge=0)
    output_guardrail: OutputGuardrailName = "redact"
    generate_titles: bool = False


class InferenceConfig(BaseSettings):
    """Which InferenceBackend answers turns (ADR-0007 decision 4)."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_INFERENCE_")

    backend: InferenceBackendName = "echo"
    endpoint: str = ""
    vision: VisionMode = Field(default=DEFAULT_VISION_MODE, validation_alias="CORTEX_VISION")
    stall_timeout_s: float = Field(default=120.0, gt=0)

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
    scope: MemoryScopeName = "global"
    on_tainted: MemoryTaintPolicyName = "skip"
    recall: MemoryRecallName = "judge"
    recall_half_life_days: float = 30.0
    recall_recency_weight: float = 0.3
    recall_dedup_threshold: float = 0.98
    recall_pool_factor: int = 4
    recall_mmr_lambda: float = 0.5
    recall_audit: bool = False

    @model_validator(mode="after")
    def _pgvector_needs_dsn_and_embedder(self) -> "MemoryConfig":
        if self.backend == "pgvector" and not (self.dsn and self.embedder_endpoint):
            msg = (
                "CORTEX_MEMORY_DSN and CORTEX_MEMORY_EMBEDDER_ENDPOINT are required when "
                "CORTEX_MEMORY_BACKEND=pgvector"
            )
            raise ValueError(msg)
        return self
