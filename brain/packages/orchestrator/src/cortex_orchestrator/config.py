"""Orchestrator configuration: env-driven, read only at the composition root."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL
from cortex_orchestrator.converse import DEFAULT_CONFIRM_TIMEOUT_S, DEFAULT_MAX_BUFFERED_EVENTS
from cortex_orchestrator.dsn import authority_is_readable
from cortex_session import DEFAULT_REDIS_URL

InferenceBackendName = Literal["echo", "llamacpp"]
VisionMode = Literal["auto", "on", "off"]
TraceBudgetMode = Literal["auto", "on", "off"]
MemoryBackendName = Literal["none", "pgvector"]
MemoryScopeName = Literal["global", "session"]
MemoryRecallName = Literal["raw", "reranked", "mmr", "recency_mmr", "judge"]
MemoryTaintPolicyName = Literal["skip", "record"]
OutputGuardrailName = Literal["redact", "lookalike", "strict", "off"]

DEFAULT_VISION_MODE: VisionMode = "auto"

DEFAULT_RPC_PORT = 50051

DEFAULT_RPC_HOST = "127.0.0.1"


class RpcServerConfig(BaseSettings):
    """Where (and to whom) the brain hosts BrainService."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_SEAM_")

    host: str = DEFAULT_RPC_HOST
    port: int = DEFAULT_RPC_PORT
    token: str = ""
    converse_buffer: int = Field(default=DEFAULT_MAX_BUFFERED_EVENTS, gt=0)
    confirm_timeout_s: float = Field(default=DEFAULT_CONFIRM_TIMEOUT_S, gt=0)

    @property
    def bind_address(self) -> str:
        """The `host:port` string handed to grpc's `add_insecure_port`."""
        return f"{self.host}:{self.port}"


class BrainRuntimeConfig(BaseSettings):
    """Runtime wiring settings: which store holds the state, which model answers."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_", validate_by_name=True)

    redis_url: str = DEFAULT_REDIS_URL
    cortex_model: str = Field(default=DEFAULT_CORTEX_MODEL, validation_alias="CORTEX_MODEL_CORTEX")
    vram_soft_cap_gb: float = Field(default=14.0, gt=0)
    # The resident cortex's measured footprint, and the subagent GPU headroom is the soft cap
    # minus this. At the shipped tier shape it peaks at 8524 to 8573 MiB above the idle floor,
    # so 8.6 GiB leaves 233 MiB over the peak.
    cortex_reservation_gb: float = Field(
        default=8.6, ge=0, validation_alias="CORTEX_VRAM_CORTEX_GB"
    )
    # About 12K tokens against the cortex's 16K-token context, which leaves room for the
    # preamble, the recalled memories, the tool specs and the reply. 0 disables windowing.
    history_char_budget: int = Field(default=48_000, ge=0)
    history_summary: bool = True
    # Matches ``RECAP_MAX``: below one account's worth of new material there is less to fold in
    # than the account being folded into, and folding again is what compounds a recap's losses.
    history_recap_min_chars: int = Field(default=2_000, ge=0)
    output_guardrail: OutputGuardrailName = "redact"
    generate_titles: bool = False


class InferenceConfig(BaseSettings):
    """Which InferenceBackend answers turns."""

    model_config = SettingsConfigDict(env_prefix="CORTEX_INFERENCE_", validate_by_name=True)

    backend: InferenceBackendName = "echo"
    endpoint: str = ""
    vision: VisionMode = Field(default=DEFAULT_VISION_MODE, validation_alias="CORTEX_VISION")
    # Whether a request may set its own trace budget as llama.cpp's ``reasoning_budget_tokens``.
    # ``auto`` asks the endpoint once at wiring, the answer being a property of the binary behind
    # it rather than of the argv a model host last started a child with.
    send_trace_budget: TraceBudgetMode = Field(
        default="auto", validation_alias="CORTEX_INFERENCE_TRACE_LEVER"
    )
    stall_timeout_s: float = Field(default=120.0, gt=0)

    @model_validator(mode="after")
    def _llamacpp_needs_an_endpoint(self) -> "InferenceConfig":
        if self.backend == "llamacpp" and not self.endpoint:
            msg = "CORTEX_INFERENCE_ENDPOINT is required when CORTEX_INFERENCE_BACKEND=llamacpp"
            raise ValueError(msg)
        return self


# Deliberately not a ``ValueError``, the type every other settings class here raises: pydantic
# renders the validated input beside the message, and this class's input holds the DSN, so a
# refusal raised that way would print the credential.
class MemoryConfigError(Exception):
    """A memory configuration is refused, in words naming variables and never values."""


class MemoryConfig(BaseSettings):
    """Whether turns recall/record durable memory."""

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
    recall_audit_file: str = ""

    @model_validator(mode="after")
    def _pgvector_needs_dsn_and_embedder(self) -> "MemoryConfig":
        if self.backend == "pgvector" and not (self.dsn and self.embedder_endpoint):
            msg = (
                "CORTEX_MEMORY_DSN and CORTEX_MEMORY_EMBEDDER_ENDPOINT are required when "
                "CORTEX_MEMORY_BACKEND=pgvector"
            )
            raise MemoryConfigError(msg)
        return self

    @model_validator(mode="after")
    def _dsn_authority_is_readable(self) -> "MemoryConfig":
        if self.backend == "pgvector" and not authority_is_readable(self.dsn):
            msg = (
                "CORTEX_MEMORY_DSN has an authority the Postgres driver cannot read; "
                "percent-encode any password character that would end a URL's authority"
            )
            raise MemoryConfigError(msg)
        return self
