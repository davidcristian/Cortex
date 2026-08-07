"""Orchestrator configuration: env-driven, read only at the composition root.

Tool dispatch config lives in ``config_tools.py``, scheduling in ``config_schedule.py``, and
subagents in ``config_subagents.py``, each split off at this module's line cap.
"""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from cortex_core import DEFAULT_CORTEX_MODEL, MAX_IMAGE_BYTES, MAX_IMAGE_EDGE
from cortex_orchestrator.converse import DEFAULT_CONFIRM_TIMEOUT_S, DEFAULT_MAX_BUFFERED_EVENTS
from cortex_session import DEFAULT_REDIS_URL

BodyBackendName = Literal["none", "grpc"]
InferenceBackendName = Literal["echo", "llamacpp"]
VisionMode = Literal["auto", "on", "off"]
MemoryBackendName = Literal["none", "pgvector"]
MemoryScopeName = Literal["global", "session"]
MemoryRecallName = Literal["raw", "reranked", "mmr", "recency_mmr", "judge"]
MemoryTaintPolicyName = Literal["skip", "record"]


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
    # from untrusted tool results in the reply the user sees; `strict` (ADR-0015 addendum)
    # redacts every non-user URL on a tainted turn; `off` restores the unguarded stream.
    output_guardrail: Literal["redact", "strict", "off"] = "redact"
    # env CORTEX_GENERATE_TITLES turns on brain-generated switcher titles (ADR-0021 titles
    # addendum): on a session's first turn the resident model writes a short title from the
    # opening exchange, which `list_sessions` prefers over the first-message derivation. Default
    # off, since it adds one inference call per new session on the shared GPU, so a deployment
    # opts in; the generated title is persisted, so it survives a model swap. A reasoning cortex
    # can spend its whole budget thinking and emit no title, in which case the first-message
    # derivation stands (reliable content wants thinking disabled, which the inference port does
    # not yet express; ADR-0021 titles addendum).
    generate_titles: bool = False


class BodyConfig(BaseSettings):
    """Whether the cortex can call the host body over ``BodyService`` (ADR-0023).

    ``none`` (the default) disables the brain→body direction. CI and the no-body dev loop
    run without it, and the volume tools are simply not registered. ``grpc`` enables it and
    requires ``endpoint`` (``host:port`` of the host-native body's ``BodyService`` server; from
    the dockerized brain this is ``host.docker.internal:<port>``). The seam token is the shared
    ``CORTEX_SEAM_TOKEN`` (ADR-0016), attached by the client, so it lives in ``SeamServerConfig``
    and is not duplicated here.

    Three knobs bound a screen capture (ADR-0029). ``capture_max_edge`` and ``max_image_bytes``
    are what the brain asks the body for and, more importantly, what it holds the reply to: the
    body clamps both and an older body ignores both, so they are re-verified on receipt.
    ``max_image_bytes`` defaults to the same 6 MiB as the body's own ceiling, which is the point
    of sending it rather than trusting two constants to stay equal. ``capture_timeout_s`` is the
    only deadline on this seam, because a blit plus an encode is the only call that can park a
    host thread.

    ``capture_max_edge`` defaults to **2048 rather than to the body's own 1600**, which is the
    brain half of the measured legibility pair (ADR-0029's legibility addendum): with the model
    host's ``CORTEX_IMAGE_MAX_TOKENS`` at 1024, a 4K desktop goes from 6 to 8 of 47 ground-truth
    strings read to 36 to 38. It belongs on this side because the number that makes it worth
    paying for is the model's per-image token budget, which the body cannot know; a body asked
    for nothing keeps answering at its own conservative 1600, where a worst-case incompressible
    screen still encodes inside the byte ceiling. ``0`` still means "the body's own default", so
    a deployment can hand the choice back.

    All three are **bounded here so a misconfiguration fails at boot**, the way the model host's
    ports and context sizes do. Both capture bounds ride uint32 proto fields, so a negative or
    over-wide value is a request that cannot be built at all, and unbounded they turned every
    capture of that deployment into a turn-killing exception rather than a startup refusal.
    ``max_image_bytes`` may only tighten the domain ceiling (the body clamps to its own anyway,
    so a looser number is a bound nothing would honour), and ``capture_max_edge`` may not exceed
    the largest edge an ``ImagePart`` would accept, which the reply is checked against too.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_BODY_")

    backend: BodyBackendName = "none"
    endpoint: str = ""
    capture_max_edge: int = Field(default=2048, ge=0, le=MAX_IMAGE_EDGE)
    max_image_bytes: int = Field(default=MAX_IMAGE_BYTES, gt=0, le=MAX_IMAGE_BYTES)
    capture_timeout_s: float = Field(default=10.0, gt=0)

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

    ``vision`` (``CORTEX_VISION``) decides whether the screen-capture tool is advertised
    (ADR-0029). ``auto``, the default, probes ``GET {endpoint}/props`` on every advertisement
    and every call and believes the running server rather than a brain-side declaration, so a
    model host restarted without its projector stops being offered eyes without a brain restart;
    ``on`` and ``off`` fix the answer for CI, for a deterministic test, and for a user who wants
    capture off without editing compose.
    """

    model_config = SettingsConfigDict(env_prefix="CORTEX_INFERENCE_")

    backend: InferenceBackendName = "echo"
    endpoint: str = ""
    vision: VisionMode = Field(default="auto", validation_alias="CORTEX_VISION")

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
    combining both axes and reusing the recency and lambda knobs; ``judge`` asks the resident model
    to order the over-fetched pool by what each note actually says (ADR-0038), reusing
    ``recall_pool_factor`` and falling back to raw top-k cosine whenever the model cannot be reached
    or believed. ``judge`` is also the only policy that may return **nothing**, when the model reads
    the pool and answers that no candidate helps, and the turn then carries no recalled memories at
    all (ADR-0038 abstention addendum). The knobs are inert under ``raw``; each policy validates the
    ranges of the ones it uses when it is built.

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
    recall: MemoryRecallName = "raw"
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
