"""Orchestrator configuration: env-driven, read only at the composition root."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import (
    DEFAULT_CORTEX_MODEL,
    MAX_TOOL_DISPATCHES,
    SPAWN_TOOL_NAME,
    ToolCostPolicy,
)
from cortex_orchestrator.converse import DEFAULT_CONFIRM_TIMEOUT_S, DEFAULT_MAX_BUFFERED_EVENTS
from cortex_session import DEFAULT_REDIS_URL

BodyBackendName = Literal["none", "grpc"]
InferenceBackendName = Literal["echo", "llamacpp"]
MemoryBackendName = Literal["none", "pgvector"]
MemoryScopeName = Literal["global", "session"]
MemoryRecallName = Literal["raw", "reranked", "mmr", "recency_mmr"]
MemoryTaintPolicyName = Literal["skip", "record"]
ToolsBackendName = Literal["none", "mcp"]

# What one `spawn_subagents` dispatch spends of a loop's dispatch budget (ADR-0009 cost
# addendum). A quarter of `MAX_TOOL_DISPATCHES`, so a turn may delegate four times: the tool
# takes a *batch* of instructions, so four dispatches is ample fan-out, while the flat price
# would have allowed thirty two batches of concurrent model runs from one turn. Priced here
# rather than in the core because what a spawn costs is a property of this deployment's
# hardware, not of the tool.
DEFAULT_SPAWN_COST = MAX_TOOL_DISPATCHES // 4


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
    # `redact` (the default, so hardening is on out of the box) replaces URLs sourced verbatim
    # from untrusted tool results in the reply the user sees; `strict` (ADR-0015 addendum)
    # redacts every non-user URL on a tainted turn; `off` restores the unguarded stream.
    output_guardrail: Literal["redact", "strict", "off"] = "redact"


class BodyConfig(BaseSettings):
    """Whether the cortex can call the host body over ``BodyService`` (ADR-0023).

    ``none`` (the default) disables the brain→body direction. CI and the no-body dev loop
    run without it, and the volume tools are simply not registered. ``grpc`` enables it and
    requires ``endpoint`` (``host:port`` of the host-native body's ``BodyService`` server; from
    the dockerized brain this is ``host.docker.internal:<port>``). The seam token is the shared
    ``CORTEX_SEAM_TOKEN`` (ADR-0016), attached by the client, so it lives in ``SeamServerConfig``
    and is not duplicated here.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_BODY_")

    backend: BodyBackendName = "none"
    endpoint: str = ""

    @model_validator(mode="after")
    def _grpc_needs_an_endpoint(self) -> "BodyConfig":
        if self.backend == "grpc" and not self.endpoint:
            msg = "CORTEX_BODY_ENDPOINT is required when CORTEX_BODY_BACKEND=grpc"
            raise ValueError(msg)
        return self


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

    ``recall`` (env ``CORTEX_MEMORY_RECALL``, ADR-0008 rerank addendum) picks the recall reranking
    policy: ``raw`` (the default) keeps v1 top-k cosine exactly; ``reranked`` blends similarity with
    a recency decay and drops near-duplicates, tuned by ``recall_half_life_days`` (30),
    ``recall_recency_weight`` (0.3, the blend's recency share), ``recall_dedup_threshold`` (0.98,
    the near-duplicate cosine), and ``recall_pool_factor`` (4, how many times ``k`` to over-fetch);
    ``mmr`` selects for maximal marginal relevance (query-relevance traded against diversity beyond
    the reranker's near-duplicate cutoff), tuned by ``recall_mmr_lambda`` (0.5, the relevance share,
    ``1`` pure relevance and ``0`` pure diversity) and the shared ``recall_pool_factor``;
    ``recency_mmr`` runs that MMR selection over the recency blend rather than raw similarity,
    combining both axes and reusing the recency and lambda knobs. The knobs are inert under ``raw``;
    each policy validates the ranges of the ones it uses when it is built.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_MEMORY_")

    backend: MemoryBackendName = "none"
    dsn: str = ""
    embedder_endpoint: str = ""
    embedder_model: str = "embedding"
    scope: MemoryScopeName = "global"
    on_tainted: MemoryTaintPolicyName = "skip"
    recall: MemoryRecallName = "raw"
    recall_half_life_days: float = 30.0
    recall_recency_weight: float = 0.3
    recall_dedup_threshold: float = 0.98
    recall_pool_factor: int = 4
    recall_mmr_lambda: float = 0.5

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
    ``CORTEX_TOOLS_GATED`` (a JSON name list, ADR-0022) names the remote tools the brain
    declares outbound/irreversible: the composition root stamps them ``gated``, so the
    dispatcher's confirm gate covers them and subagents never see them. The default covers
    ``send_email``, so enabling the email sidecar's write path without touching gating
    config still gates it (fail-closed pairing); an empty list disables the overlay.
    ``CORTEX_TOOLS_COSTS__<name>=<int>`` prices a tool against the loop's dispatch budget
    (ADR-0009 cost addendum), one per key so layered compose overrides each contribute the
    price of the tool they enable, and anything unpriced costs one. ``cost_policy`` is the
    effective result: it merges the built-in prices under whatever the user set. Built in is
    ``spawn_subagents``, the one wired tool whose single dispatch fans out into a batch of
    model runs and which no confirmation gate bounds; ``send_email`` is deliberately unpriced,
    because every send already needs the user's approval and a human saying yes thirty two
    times is the tighter bound. A price outside ``1..MAX_TOOL_DISPATCHES`` fails at boot.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_TOOLS_", env_nested_delimiter="__")

    backend: ToolsBackendName = "none"
    endpoint: str = ""
    endpoints: dict[str, str] = {}
    allow: dict[str, tuple[str, ...]] = {}
    on_unavailable: Literal["fail", "skip"] = "fail"
    gated: tuple[str, ...] = ("send_email",)
    costs: dict[str, int] = {}

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
        # A price outside 1..budget is a misconfiguration that hides rather than announces
        # itself: zero or less makes the tool free, so the budget stops bounding the one tool
        # a user cared enough to configure; above the budget makes it permanently
        # unaffordable, so it never runs and the first call closes the turn's budget. Both
        # would surface as puzzling runtime behavior, so they fail at boot instead.
        if bad := sorted(n for n, c in self.costs.items() if not 1 <= c <= MAX_TOOL_DISPATCHES):
            msg = f"CORTEX_TOOLS_COSTS must be 1..{MAX_TOOL_DISPATCHES}: {bad}"
            raise ValueError(msg)
        return self

    @property
    def cost_policy(self) -> ToolCostPolicy:
        """The effective prices as the core's policy value (ADR-0009 cost addendum).

        The built-in prices are merged **under** the user's, rather than being the field's
        default, because a nested-dict env key replaces the whole mapping: pricing one
        filesystem tool via `CORTEX_TOOLS_COSTS__READ_FILE` would otherwise silently drop
        `spawn_subagents` back to one, un-pricing the fan-out tool as a side effect of an
        unrelated knob. Restating a built-in price still overrides it, which is deliberate.
        """
        return ToolCostPolicy({SPAWN_TOOL_NAME: DEFAULT_SPAWN_COST} | self.costs)

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
