"""Orchestrator configuration: env-driven, read only at the composition root.

Tool dispatch config lives in ``config_tools.py``, scheduling in ``config_schedule.py``,
subagents in ``config_subagents.py``, and the host body in ``config_body.py``, each split off at
this module's line cap.
"""

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
# The output guardrail's policy names, declared once and imported by the builder that maps each to
# its class, so a rename cannot leave the builder answering a value nothing can be set to. The
# cross-tree scan cannot reach this pair (it reads column-zero declarations, and these are a
# Pydantic field's annotation and a comparison inside a function), so the type is what ties them.
OutputGuardrailName = Literal["redact", "lookalike", "strict", "off"]

# The port BrainService listens on by default. Named rather than spelled inline because it is
# not only ours: the compose stack publishes it and dials it in its own healthcheck, and the
# host body's default endpoints carry it too, so `scripts/crosscheck.py` ties those to this.
DEFAULT_SEAM_PORT = 50051


class SeamServerConfig(BaseSettings):
    """Where (and to whom) the brain hosts BrainService.

    The security posture is ROADMAP assumption 5: loopback-only listeners plus an optional
    shared-secret token (ADR-0016). With `token` set, every call must carry it as
    `x-cortex-seam-token` metadata or is rejected UNAUTHENTICATED; empty (the default)
    disables the check and loopback-only remains the sole boundary.
    """

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
    # env CORTEX_VRAM_CORTEX_GB is the resident cortex's measured footprint, and the subagent GPU
    # headroom is the cap minus this. 8.6 GiB since 2026-08-07 (ADR-0012 re-measured-reservation
    # addendum), down from the 11.3 the 2026-06-29 lineup set: measured at the shipped tier shape
    # (16K context, -ngl 99, the projector loaded, --image-max-tokens 1024) the cortex peaks at
    # 8524 to 8573 MiB above the idle floor, and the two figures were never in the same unit, the
    # old one being nvidia-smi TOTAL used with the desktop's own gigabyte folded in while every
    # other term here is a tier's own cost. The margin above the peak is 233 MiB, which covers the
    # instrument's spread and the vision path's late allocation twice over.
    cortex_reservation_gb: float = Field(
        default=8.6, ge=0, validation_alias="CORTEX_VRAM_CORTEX_GB"
    )
    # env CORTEX_HISTORY_CHAR_BUDGET sets how many characters of session history one turn sends
    # to the model (the newest whole turns; ADR-0014). Default ≈ 12K tokens against the
    # 16K-token cortex context, leaving headroom for preamble/memories/tools/reply. 0 disables
    # windowing (the model gets the full stored history).
    history_char_budget: int = Field(default=48_000, ge=0)
    # env CORTEX_HISTORY_SUMMARY recaps the turns the window drops instead of losing them
    # (ADR-0038 decision 9): the cortex writes one paragraph accounting for the dropped prefix,
    # cached in the session store and folded forward as the boundary moves. Default ON since
    # 2026-08-06, the user's standing decision now carried by the numbers that had twice held it
    # back (ADR-0038 cheap-fold addendum): a fold decodes 61 to 163 tokens rather than 400 to
    # 850, costs 2.9 s to 5.6 s with no tail, says so on screen while it runs, and the opening
    # fact survived five compounding folds 3 times of 3. A deployment that would rather forget
    # than wait sets this false. Ignored when the budget is 0, there being no prefix to recap.
    history_summary: bool = True
    # env CORTEX_HISTORY_RECAP_MIN_CHARS is how much newly dropped conversation is worth a fold
    # (ADR-0038 cheap-fold addendum). Below it the fold waits for the next boundary move, which
    # picks up everything deferred since, so the cost is that those turns are briefly in neither
    # the window nor the account rather than lost. The default matches RECAP_MAX: below one
    # account's worth of new material there is less to fold in than the account being folded
    # into, and folding again is what compounds a recap's losses. 0 folds on every move.
    history_recap_min_chars: int = Field(default=2_000, ge=0)
    # env CORTEX_OUTPUT_GUARDRAIL is the model-independent laundering defense (ADR-0015):
    # `redact` (the default, so hardening is on out of the box) replaces URLs sourced verbatim
    # from untrusted tool results in the reply the user sees; `lookalike` (ADR-0015 fourteenth
    # addendum) adds every URL whose host is not plain ASCII on a tainted turn, which is the one
    # answer to a homoglyph host that no table can give, at the cost of an internationalized
    # domain named on such a turn; `strict` (ADR-0015 addendum) redacts every non-user URL on a
    # tainted turn; `off` restores the unguarded stream.
    output_guardrail: OutputGuardrailName = "redact"
    # env CORTEX_GENERATE_TITLES turns on brain-generated switcher titles (ADR-0021 titles
    # addendum): on a session's first turn the resident model writes a short title from the
    # opening exchange, which `list_sessions` prefers over the first-message derivation. Default
    # off, since it adds one inference call per new session on the shared GPU, so a deployment
    # opts in; the generated title is persisted, so it survives a model swap. A reasoning cortex
    # can spend its whole budget thinking and emit no title, in which case the first-message
    # derivation stands (reliable content wants thinking disabled, which the inference port does
    # not yet express; ADR-0021 titles addendum).
    generate_titles: bool = False


class InferenceConfig(BaseSettings):
    """Which InferenceBackend answers turns (ADR-0007 decision 4).

    ``echo`` (the default) is the GPU-less scripted fake, what CI and the no-GPU dev
    loop run. ``llamacpp`` selects the real adapter and requires ``endpoint`` (the base
    URL of the resident model's ``llama-server``, set by ``docker-compose.gpu.yml``).

    ``vision`` (``CORTEX_VISION``) decides whether the screen-capture tool is advertised
    (ADR-0029). ``auto``, the default, probes ``GET {endpoint}/props`` on every advertisement
    and every call and believes the running server rather than a brain-side declaration, so a
    model host restarted without its projector stops being offered eyes without a brain restart;
    ``on`` and ``off`` fix the answer for CI, for a deterministic test, and for a user who wants
    capture off without editing compose.

    ``stall_timeout_s`` (``CORTEX_INFERENCE_STALL_TIMEOUT_S``) is how long a resident-tier
    generation may send nothing before the adapter gives up on it (ADR-0005 stall-ceiling
    addendum). It bounds the gap between chunks and never the generation, so it must clear the
    worst legitimate time to first token rather than the longest reply: the default is derived
    from the 17.5 s a contended cortex took to its first token and from the deep tier's own
    cost, that tier streaming through the same client after a handoff.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_INFERENCE_")

    backend: InferenceBackendName = "echo"
    endpoint: str = ""
    vision: VisionMode = Field(default="auto", validation_alias="CORTEX_VISION")
    stall_timeout_s: float = Field(default=120.0, gt=0)

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
    policy: ``raw`` keeps v1 top-k cosine exactly; ``reranked`` blends similarity with
    a recency decay and drops near-duplicates, tuned by ``recall_half_life_days`` (30),
    ``recall_recency_weight`` (0.3, the blend's recency share), ``recall_dedup_threshold`` (0.98,
    the near-duplicate cosine), and ``recall_pool_factor`` (4, how many times ``k`` to over-fetch);
    ``mmr`` selects for maximal marginal relevance (query-relevance traded against diversity beyond
    the reranker's near-duplicate cutoff), tuned by ``recall_mmr_lambda`` (0.5, the relevance share,
    ``1`` pure relevance and ``0`` pure diversity) and the shared ``recall_pool_factor``;
    ``recency_mmr`` runs that MMR selection over the recency blend rather than raw similarity,
    combining both axes and reusing the recency and lambda knobs; ``judge`` (**the default since
    the turn-cost addendum**) asks the resident model to order the over-fetched pool by what each
    note actually says (ADR-0038), reusing ``recall_pool_factor`` and falling back to raw top-k
    cosine whenever the model cannot be reached or believed. ``judge`` is also the only policy that
    may return **nothing**, when the model reads the pool and answers that no candidate helps, and
    the turn then carries no recalled memories at all (ADR-0038 abstention addendum). The knobs are
    inert under ``raw``; each policy validates the ranges of the ones it uses when it is built.

    **The default is a rank, so a recalling turn spends a bounded cortex call before it answers.**
    Measured end to end on the 24 GB card over 48 turns an arm, the rank alone costs 0.877 s at the
    pool a turn asks for, and the turn's own time to first token rises 0.515 s (95% CI 0.116 to
    0.915, against a raw-versus-raw noise floor whose interval spans zero), the difference being
    the shorter memory block a rank that keeps 1.17 notes hands the reply against the cosine's 5.
    It is paid on every recalling turn, since nothing caches a rank. A deployment that wants the
    founding behavior back sets ``CORTEX_MEMORY_RECALL=raw``, and ``recall_audit`` below reports
    which policy actually ranked each recall either way.

    ``recall_audit`` (env ``CORTEX_MEMORY_RECALL_AUDIT``, ADR-0038) turns on the recall trail: one
    structured log line per recall carrying the pool size, the rank basis, and each kept hit's id,
    score and rank key, never any text. ``False`` (the default) is the founding silent recall path.
    """

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
