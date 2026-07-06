"""Orchestrator configuration: env-driven, read only at the composition root."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL
from cortex_orchestrator.converse import DEFAULT_MAX_BUFFERED_EVENTS
from cortex_session import DEFAULT_REDIS_URL

InferenceBackendName = Literal["echo", "llamacpp"]
MemoryBackendName = Literal["none", "pgvector"]
MemoryScopeName = Literal["global", "session"]
MemoryTaintPolicyName = Literal["skip", "record"]
ToolsBackendName = Literal["none", "mcp"]
SubagentsBackendName = Literal["none", "llamacpp"]

# The logical id of the subagent tier (ADR-0004); deployments override via CORTEX_SUBAGENTS_MODEL.
DEFAULT_SUBAGENT_MODEL = "subagent"

# What the spawn spec advertises for the default entry unless the deployment overrides it
# (CORTEX_SUBAGENTS_MODEL_DESCRIPTION). Trade-off text only. Safety never rides a description
# (ADR-0017 is enforced in the core, whatever this says).
DEFAULT_SUBAGENT_DESCRIPTION = "the injection-robust default; safe for any subtask"


class SeamServerConfig(BaseSettings):
    """Where (and to whom) the brain hosts BrainService.

    The security posture is ROADMAP assumption 5: loopback-only listeners plus an optional
    shared-secret token (ADR-0016). With `token` set, every call must carry it as
    `x-cortex-seam-token` metadata or is rejected UNAUTHENTICATED; empty (the default)
    disables the check and loopback-only remains the sole boundary.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_SEAM_")

    host: str = "127.0.0.1"
    port: int = 50051
    # env CORTEX_SEAM_TOKEN is the shared secret both sides read from env (never the repo).
    token: str = ""
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
    # env CORTEX_HISTORY_CHAR_BUDGET sets how many characters of session history one turn sends
    # to the model (the newest whole turns; ADR-0014). Default ≈ 12K tokens against the
    # 16K-token cortex context, leaving headroom for preamble/memories/tools/reply. 0 disables
    # windowing (the model gets the full stored history).
    history_char_budget: int = Field(default=48_000, ge=0)
    # env CORTEX_OUTPUT_GUARDRAIL is the model-independent laundering defense (ADR-0015):
    # `redact` (the default, so hardening is on out of the box) replaces URLs sourced from
    # untrusted tool results in the reply the user sees; `off` restores the unguarded stream.
    output_guardrail: Literal["redact", "off"] = "redact"


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

    ``scope`` (env ``CORTEX_MEMORY_SCOPE``, ADR-0008 scoping addendum) picks the recall
    namespace policy: ``global`` (the default) keeps the founding one-global-space behavior, so
    recall spans every conversation; ``session`` isolates each conversation's memory to itself.
    It applies only when a backend is set; ``none`` records/recalls nothing regardless.

    ``on_tainted`` (env ``CORTEX_MEMORY_ON_TAINTED``, ADR-0019) is the tainted-turn recording
    policy: ``skip`` (the default) drops a turn that read untrusted content from memory (ADR-0013);
    ``record`` records it with the untrusted-provenance marker so recall fences it. It governs only
    writing. A tainted memory already stored is always fenced on recall regardless.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_MEMORY_")

    backend: MemoryBackendName = "none"
    dsn: str = ""
    embedder_endpoint: str = ""
    embedder_model: str = "embedding"
    scope: MemoryScopeName = "global"
    on_tainted: MemoryTaintPolicyName = "skip"

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
    """Whether the cortex can call tools over MCP (ADR-0009, refinements addendum).

    ``none`` (the default) disables tools. CI and the no-GPU dev loop run with no MCP server.
    ``mcp`` enables the MCP client and requires tool-server endpoint(s), one of two forms:
    the singular ``endpoint`` (one streamable-http URL), or one ``endpoints`` entry per
    sidecar (``CORTEX_TOOLS_ENDPOINTS__<name>=<url>``), so layered compose overrides each
    contribute their own key and coexist. ``CORTEX_TOOLS_ALLOW__<name>=<JSON name list>``
    optionally restricts what ``<name>`` advertises (the read-only filesystem allowlist).
    Setting both forms is ambiguous and rejected, as is an allowlist naming no endpoint.
    ``CORTEX_TOOLS_ON_UNAVAILABLE`` picks the dead-sidecar policy: ``fail`` (the default)
    fails tool listing loudly; ``skip`` serves the healthy sidecars and logs the dead one
    on every walk (ADR-0009 degraded-mode addendum), degraded but never silent.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_TOOLS_", env_nested_delimiter="__")

    backend: ToolsBackendName = "none"
    endpoint: str = ""
    endpoints: dict[str, str] = {}
    allow: dict[str, tuple[str, ...]] = {}
    on_unavailable: Literal["fail", "skip"] = "fail"

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
        """Every configured endpoint by name, sorted by name so precedence is deterministic.

        The order fixes the `AggregateToolRegistry` collision policy (first-wins by sorted
        name), independent of env enumeration order. The singular ``endpoint`` becomes the
        sole entry ``default``.
        """
        if self.endpoints:
            return dict(sorted(self.endpoints.items()))
        if self.endpoint:
            return {"default": self.endpoint}
        return {}


class SubagentRosterEntry(BaseModel):
    """One alternate subagent model: a ``CORTEX_SUBAGENTS_ROSTER__<name>`` JSON value (ADR-0018).

    ``endpoint`` (required, non-empty) is the entry's CPU ``llama-server`` base URL; an empty
    ``gpu_endpoint`` falls back to it (normalized in ``named_roster``, per the interim one-executor
    stance, ADR-0012 deferral). The resource numbers default like the flat fields;
    ``description`` is the trade-off text the spawn spec advertises verbatim (it informs the
    cortex's optimization, never safety, since ADR-0017 is enforced in the core).
    """

    endpoint: str = Field(min_length=1)
    gpu_endpoint: str = ""
    vram_gb: float = Field(default=2.0, gt=0)
    cpus: float = Field(default=2.0, gt=0)
    memory_gb: float = Field(default=2.0, gt=0)
    description: str = ""


class SubagentsConfig(BaseSettings):
    """Whether the cortex can delegate to subagents (ADR-0010, ADR-0012, ADR-0018).

    ``none`` (the default) disables delegation. The cortex's tool set has no ``spawn_subagents``
    and the turn path is byte-for-byte the Slice 6 behavior, so CI and the no-GPU dev loop run
    subagent-free. ``llamacpp`` enables GPU-first placement (ADR-0012) and requires both
    ``gpu_endpoint`` (the GPU subagent ``llama-server``, ``-ngl 99``) and ``endpoint`` (the CPU
    overflow ``llama-server``, ``-ngl 0``), each a base URL in ``docker-compose.subagents.yml``.

    ``vram_gb``/``cpus``/``memory_gb`` are one subagent's resource ask (VRAM footprint the placer
    fit-tests, and the per-container ``--cpus``/``--memory`` the scheduler sums); ``cpu_budget``/
    ``mem_budget_gb`` are the soft admission ceilings (sum of admitted asks ≤ target). The user
    measures the real numbers on the host; the defaults are GPU-less-safe placeholders.

    The flat fields above define the roster's **default entry** as the injection-robust ADR-0004
    pick the wiring pins untrusted-content spawns to (ADR-0017); ``model`` names it and
    ``model_description`` is its advertised text. ``CORTEX_SUBAGENTS_ROSTER__<name>`` adds one
    **alternate** model per key (a JSON ``SubagentRosterEntry``), so layered compose overrides
    each contribute their own entry (ADR-0018). A roster key naming the default is rejected, since
    the default's resources come from the flat fields, one source of truth.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_SUBAGENTS_", env_nested_delimiter="__")

    backend: SubagentsBackendName = "none"
    endpoint: str = ""
    gpu_endpoint: str = ""
    model: str = DEFAULT_SUBAGENT_MODEL
    model_description: str = DEFAULT_SUBAGENT_DESCRIPTION
    vram_gb: float = Field(default=2.0, gt=0)
    cpus: float = Field(default=2.0, gt=0)
    memory_gb: float = Field(default=2.0, gt=0)
    cpu_budget: float = Field(default=4.0, gt=0)
    mem_budget_gb: float = Field(default=8.0, gt=0)
    roster: dict[str, SubagentRosterEntry] = {}

    @model_validator(mode="after")
    def _llamacpp_needs_both_endpoints(self) -> "SubagentsConfig":
        if self.backend == "llamacpp" and not (self.endpoint and self.gpu_endpoint):
            msg = (
                "CORTEX_SUBAGENTS_ENDPOINT and CORTEX_SUBAGENTS_GPU_ENDPOINT are required when "
                "CORTEX_SUBAGENTS_BACKEND=llamacpp"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _roster_must_not_shadow_the_default(self) -> "SubagentsConfig":
        if self.model in self.roster:
            msg = (
                f"CORTEX_SUBAGENTS_ROSTER__{self.model} collides with CORTEX_SUBAGENTS_MODEL; "
                "the default entry's resources come from the flat fields"
            )
            raise ValueError(msg)
        return self

    @property
    def named_roster(self) -> dict[str, SubagentRosterEntry]:
        """Every roster entry by name, with the flat-field default first and alternates sorted.

        Empty unless ``backend`` is ``llamacpp`` (the flat endpoints are only validated there).
        The default entry is synthesized from the flat fields; each alternate's empty
        ``gpu_endpoint`` is normalized to its ``endpoint``, so the builders read ready-to-dial
        values. The mapping is keyed (order carries no semantics) but default-first reads
        naturally in logs and tests.
        """
        if self.backend != "llamacpp":
            return {}
        default = SubagentRosterEntry(
            endpoint=self.endpoint,
            gpu_endpoint=self.gpu_endpoint,
            vram_gb=self.vram_gb,
            cpus=self.cpus,
            memory_gb=self.memory_gb,
            description=self.model_description,
        )
        alternates = {
            name: entry.model_copy(update={"gpu_endpoint": entry.gpu_endpoint or entry.endpoint})
            for name, entry in sorted(self.roster.items())
        }
        return {self.model: default} | alternates
