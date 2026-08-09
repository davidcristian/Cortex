"""Config behavior: defaults and env overrides for the settings models."""

import os

import pytest
from pydantic import ValidationError

from cortex_core import (
    ALWAYS_SALIENT,
    ESCALATE_GATE_REASON,
    ESCALATE_TOOL_NAME,
    MAX_TOOL_DISPATCHES,
    REPEAT_SALIENCE,
    SPAWN_TOOL_NAME,
    PlacementRequest,
    PlacementTarget,
    VramBudgetPlacer,
)
from cortex_core.tool_budget import DEFAULT_TOOL_COST
from cortex_orchestrator import (
    BodyConfig,
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
    SubagentRosterEntry,
    SubagentsConfig,
    ToolsConfig,
)
from cortex_orchestrator.config_tools import DEFAULT_SPAWN_COST


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CORTEX_SEAM_HOST",
        "CORTEX_SEAM_PORT",
        "CORTEX_SEAM_CONVERSE_BUFFER",
        "CORTEX_REDIS_URL",
        "CORTEX_MODEL_CORTEX",
        "CORTEX_HISTORY_CHAR_BUDGET",
        "CORTEX_INFERENCE_BACKEND",
        "CORTEX_INFERENCE_ENDPOINT",
        "CORTEX_MEMORY_BACKEND",
        "CORTEX_MEMORY_DSN",
        "CORTEX_MEMORY_EMBEDDER_ENDPOINT",
        "CORTEX_MEMORY_EMBEDDER_MODEL",
        "CORTEX_TOOLS_BACKEND",
        "CORTEX_TOOLS_ENDPOINT",
        "CORTEX_TOOLS_ON_UNAVAILABLE",
        "CORTEX_SUBAGENTS_BACKEND",
        "CORTEX_SUBAGENTS_ENDPOINT",
        "CORTEX_SUBAGENTS_MODEL",
        "CORTEX_SUBAGENTS_MAX_CONCURRENCY",
        "CORTEX_BODY_BACKEND",
        "CORTEX_BODY_ENDPOINT",
        "CORTEX_BODY_CAPTURE_MAX_EDGE",
        "CORTEX_BODY_MAX_IMAGE_BYTES",
        "CORTEX_BODY_CAPTURE_TIMEOUT_S",
        "CORTEX_VISION",
    ):
        monkeypatch.delenv(name, raising=False)
    # The per-sidecar tool vars are open-ended (one per <name>); sweep by prefix.
    for name in list(os.environ):
        if name.startswith(("CORTEX_TOOLS_ENDPOINTS__", "CORTEX_TOOLS_ALLOW__")):
            monkeypatch.delenv(name, raising=False)


@pytest.mark.usefixtures("clean_env")
def test_seam_defaults_are_loopback_50051() -> None:
    config = SeamServerConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 50051
    assert config.bind_address == "127.0.0.1:50051"
    assert config.converse_buffer == 256  # the converse.py default, one knob (backpressure)
    assert config.token == ""  # auth off by default, so loopback-only stays the boundary


@pytest.mark.usefixtures("clean_env")
def test_seam_env_sets_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_TOKEN", "s3-seam-secret")
    assert SeamServerConfig().token == "s3-seam-secret"  # noqa: S105 - test fixture value


@pytest.mark.usefixtures("clean_env")
def test_seam_env_overrides_the_converse_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_CONVERSE_BUFFER", "8")
    assert SeamServerConfig().converse_buffer == 8


@pytest.mark.usefixtures("clean_env")
def test_seam_rejects_a_non_positive_converse_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_CONVERSE_BUFFER", "0")
    with pytest.raises(ValidationError, match="converse_buffer"):
        SeamServerConfig()


@pytest.mark.usefixtures("clean_env")
def test_seam_env_overrides_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_HOST", "192.0.2.7")
    monkeypatch.setenv("CORTEX_SEAM_PORT", "50910")
    config = SeamServerConfig()
    assert config.host == "192.0.2.7"
    assert config.port == 50910
    assert config.bind_address == "192.0.2.7:50910"


@pytest.mark.usefixtures("clean_env")
def test_seam_explicit_arguments_beat_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_PORT", "50910")
    config = SeamServerConfig(port=0)
    assert config.port == 0


@pytest.mark.usefixtures("clean_env")
def test_runtime_defaults_match_the_dictated_contract() -> None:
    config = BrainRuntimeConfig()
    assert config.redis_url == "redis://127.0.0.1:6379/0"
    assert config.cortex_model == "cortex"  # a LOGICAL model id (ADR-0004), never a path
    assert config.vram_soft_cap_gb == 14.0  # the deliberate GPU budget (ADR-0004)
    # The cortex tier's own peak cost, measured at its shipped shape (ADR-0012
    # re-measured-reservation addendum), not the total-used figure the 2026-06-29 lineup set.
    assert config.cortex_reservation_gb == 8.6
    assert config.history_char_budget == 48_000  # ≈12K of the 16K-token context (ADR-0014)
    assert config.output_guardrail == "redact"  # the laundering defense ships on (ADR-0015)
    assert config.generate_titles is False  # opt-in: an extra inference call per new session
    # On is a measured decision and the user's: a fold now decodes 61 to 163 tokens for 2.9 s to
    # 5.6 s with no tail, announces itself on screen, and an opening fact survived five
    # compounding folds 3 times of 3 (ADR-0038 cheap-fold addendum).
    assert config.history_summary is True
    # A fold's floor, in the unit the budget it wraps is denominated in: below one stored
    # account's worth of new material there is less to fold in than the account folded into.
    assert config.history_recap_min_chars == 2_000


@pytest.mark.usefixtures("clean_env")
def test_the_shipped_budget_places_one_subagent_on_the_gpu_and_overflows_the_next() -> None:
    """What the three shipped numbers mean together, stated as placements, not as arithmetic.

    The ask is the deployment's own (``SubagentsConfig``, equal to what
    ``docker-compose.subagents.yml`` sets), so this reads the shipped budget rather than a
    figure written here. One spawn fits the headroom the re-measured cortex reservation leaves
    and the next does not, which is the fit the single GPU tier process can actually serve.
    """
    runtime = BrainRuntimeConfig()
    ask = SubagentsConfig().vram_gb
    placer = VramBudgetPlacer(
        soft_cap_gb=runtime.vram_soft_cap_gb,
        cortex_reservation_gb=runtime.cortex_reservation_gb,
    )
    first = placer.place(PlacementRequest("a", vram_gb=ask, cpus=1.0, memory_gb=1.0))
    second = placer.place(PlacementRequest("b", vram_gb=ask, cpus=1.0, memory_gb=1.0))
    assert first.target is PlacementTarget.GPU
    assert second.target is PlacementTarget.CPU


@pytest.mark.usefixtures("clean_env")
def test_the_shipped_subagent_ask_covers_the_tier_it_was_measured_from() -> None:
    """The ask is a reservation, so it must sit above the tier's peak rather than at it.

    Measured 2026-08-08 on this stack's card, the GPU-placed subagent tier costs 3338 to 3410
    MiB above a bracketed floor at its shipped shape. The ask must cover the higher end and keep
    a margin over it wider than the sampler's in-phase spread (110 MiB) plus the floor bracket's
    disagreement (20 MiB), and must not be so wide that it stops fitting the headroom, which is
    the placement the test above pins.
    """
    measured_peak_mib = 3410
    margin_mib = SubagentsConfig().vram_gb * 1024 - measured_peak_mib
    assert margin_mib >= 130


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_overrides_the_history_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_HISTORY_CHAR_BUDGET", "1000")
    assert BrainRuntimeConfig().history_char_budget == 1000


@pytest.mark.usefixtures("clean_env")
def test_runtime_rejects_a_negative_history_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    # 0 is the documented off switch; anything below it is a config mistake.
    monkeypatch.setenv("CORTEX_HISTORY_CHAR_BUDGET", "-1")
    with pytest.raises(ValidationError, match="history_char_budget"):
        BrainRuntimeConfig()


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_turns_the_history_summary_off(monkeypatch: pytest.MonkeyPatch) -> None:
    # The knob a deployment that would rather forget than wait reaches for; the default is on.
    monkeypatch.setenv("CORTEX_HISTORY_SUMMARY", "false")
    assert BrainRuntimeConfig().history_summary is False


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_sets_how_much_dropped_text_is_worth_a_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 0 folds on every boundary move, which is what the summary did before it had a floor.
    monkeypatch.setenv("CORTEX_HISTORY_RECAP_MIN_CHARS", "0")
    assert BrainRuntimeConfig().history_recap_min_chars == 0


@pytest.mark.usefixtures("clean_env")
def test_runtime_rejects_a_negative_recap_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_HISTORY_RECAP_MIN_CHARS", "-1")
    with pytest.raises(ValidationError, match="history_recap_min_chars"):
        BrainRuntimeConfig()


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_enables_brain_generated_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_GENERATE_TITLES", "true")
    assert BrainRuntimeConfig().generate_titles is True


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_disables_the_output_guardrail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_OUTPUT_GUARDRAIL", "off")
    assert BrainRuntimeConfig().output_guardrail == "off"


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_selects_strict_guardrail(monkeypatch: pytest.MonkeyPatch) -> None:
    # The opt-in strict mode (ADR-0015 addendum): redact every non-user URL on a tainted turn.
    monkeypatch.setenv("CORTEX_OUTPUT_GUARDRAIL", "strict")
    assert BrainRuntimeConfig().output_guardrail == "strict"


@pytest.mark.usefixtures("clean_env")
def test_runtime_rejects_an_unknown_guardrail_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_OUTPUT_GUARDRAIL", "maybe")
    with pytest.raises(ValidationError, match="output_guardrail"):
        BrainRuntimeConfig()


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_overrides_redis_url_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("CORTEX_MODEL_CORTEX", "cortex-experimental")
    monkeypatch.setenv("CORTEX_VRAM_SOFT_CAP_GB", "12.0")
    monkeypatch.setenv("CORTEX_VRAM_CORTEX_GB", "9.5")
    config = BrainRuntimeConfig()
    assert config.redis_url == "redis://redis:6379/0"
    assert config.cortex_model == "cortex-experimental"
    assert config.vram_soft_cap_gb == 12.0
    assert config.cortex_reservation_gb == 9.5


@pytest.mark.usefixtures("clean_env")
def test_runtime_explicit_arguments_beat_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_REDIS_URL", "redis://ignored:1/9")
    monkeypatch.setenv("CORTEX_MODEL_CORTEX", "ignored")
    config = BrainRuntimeConfig(redis_url="redis://explicit:6379/1", cortex_model="explicit")
    assert config.redis_url == "redis://explicit:6379/1"
    assert config.cortex_model == "explicit"


@pytest.mark.usefixtures("clean_env")
def test_inference_defaults_to_echo_without_an_endpoint() -> None:
    config = InferenceConfig()
    assert config.backend == "echo"
    assert config.endpoint == ""
    # Vision is discovered rather than declared, so the default has to be the probing mode: an
    # `off` default would silently cost every deployment the capability, and `on` would advertise
    # a screen read to a model that cannot see. Pinned to the literal for that reason.
    assert config.vision == "auto"
    # Likewise a literal: the worst measured contended time to first token (17.5 s) scaled by the
    # deep tier's own cost reaches 45.5 s, and two minutes carries that same factor again as
    # margin, that tier streaming through this very client after a handoff and never having had
    # its first token measured. It bounds the gap between chunks, never a generation's length.
    assert config.stall_timeout_s == 120.0


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize("mode", ["on", "off", "auto"])
def test_the_vision_mode_is_settable_to_each_of_its_three_answers(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("CORTEX_VISION", mode)
    assert InferenceConfig().vision == mode


@pytest.mark.usefixtures("clean_env")
def test_inference_env_selects_llamacpp_with_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_INFERENCE_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_INFERENCE_ENDPOINT", "http://llama-cortex:8080")
    config = InferenceConfig()
    assert config.backend == "llamacpp"
    assert config.endpoint == "http://llama-cortex:8080"


@pytest.mark.usefixtures("clean_env")
def test_inference_llamacpp_without_endpoint_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_INFERENCE_BACKEND", "llamacpp")
    with pytest.raises(ValidationError, match="CORTEX_INFERENCE_ENDPOINT is required"):
        InferenceConfig()


@pytest.mark.usefixtures("clean_env")
def test_the_resident_stall_ceiling_is_settable_and_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A slower card raises it; zero would refuse every stream on its first read."""
    monkeypatch.setenv("CORTEX_INFERENCE_STALL_TIMEOUT_S", "45.5")
    assert InferenceConfig().stall_timeout_s == 45.5
    monkeypatch.setenv("CORTEX_INFERENCE_STALL_TIMEOUT_S", "-1")
    with pytest.raises(ValidationError, match="stall_timeout_s"):
        InferenceConfig()


@pytest.mark.usefixtures("clean_env")
def test_body_defaults_to_disabled() -> None:
    config = BodyConfig()
    assert config.backend == "none"
    assert config.endpoint == ""
    # The capture knobs, against literals rather than against the constants production reads:
    # comparing a default to the very name it was assigned from proves which value was published
    # and nothing about what it is. 2048 is the brain half of the measured legibility pair (the
    # body's own default is 1600 and would be what a 0 here asked for), 6291456 is the 6 MiB
    # domain ceiling this side enforces, and 10 seconds is the only deadline on this seam.
    assert (config.capture_max_edge, config.max_image_bytes, config.capture_timeout_s) == (
        2048,
        6291456,
        10.0,
    )


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    ("name", "value"),
    [
        # Both bounds ride uint32 proto fields, so these are values no request could carry; the
        # byte budget may also only tighten the domain ceiling, never loosen it.
        ("CORTEX_BODY_CAPTURE_MAX_EDGE", "-1"),
        ("CORTEX_BODY_CAPTURE_MAX_EDGE", "8193"),
        ("CORTEX_BODY_MAX_IMAGE_BYTES", "0"),
        ("CORTEX_BODY_MAX_IMAGE_BYTES", "6291457"),
        ("CORTEX_BODY_MAX_IMAGE_BYTES", "5000000000"),
        ("CORTEX_BODY_CAPTURE_TIMEOUT_S", "0"),
        ("CORTEX_BODY_CAPTURE_TIMEOUT_S", "-3"),
    ],
)
def test_a_capture_bound_outside_the_seam_fails_at_boot(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    """Unbounded, each of these turned every capture into a turn-killing exception instead: the
    request could not be built, and neither the tool nor the dispatcher catches a ValueError."""
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        BodyConfig()


@pytest.mark.usefixtures("clean_env")
def test_a_tightened_capture_bound_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The control arm: the same knobs inside the seam's own limits are ordinary configuration."""
    monkeypatch.setenv("CORTEX_BODY_CAPTURE_MAX_EDGE", "1280")
    monkeypatch.setenv("CORTEX_BODY_MAX_IMAGE_BYTES", "2000000")
    monkeypatch.setenv("CORTEX_BODY_CAPTURE_TIMEOUT_S", "2.5")
    config = BodyConfig()
    assert (config.capture_max_edge, config.max_image_bytes, config.capture_timeout_s) == (
        1280,
        2_000_000,
        2.5,
    )


@pytest.mark.usefixtures("clean_env")
def test_body_env_selects_grpc_with_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_BODY_BACKEND", "grpc")
    monkeypatch.setenv("CORTEX_BODY_ENDPOINT", "host.docker.internal:50151")
    config = BodyConfig()
    assert config.backend == "grpc"
    assert config.endpoint == "host.docker.internal:50151"


@pytest.mark.usefixtures("clean_env")
def test_body_grpc_without_endpoint_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_BODY_BACKEND", "grpc")
    with pytest.raises(ValidationError, match="CORTEX_BODY_ENDPOINT is required"):
        BodyConfig()


@pytest.mark.usefixtures("clean_env")
def test_memory_defaults_to_disabled() -> None:
    config = MemoryConfig()
    assert config.backend == "none"
    assert config.dsn == ""
    assert config.embedder_endpoint == ""
    assert config.scope == "global"  # recall spans conversations unless opted out
    assert config.on_tainted == "skip"  # a tainted turn is dropped from memory by default
    # The model rank ships on (ADR-0038 turn-cost addendum): measured better on the corpus that
    # could have refuted it, and worth 0.515 s of time to first token on a recalling turn.
    assert config.recall == "judge"


@pytest.mark.usefixtures("clean_env")
def test_memory_scope_env_selects_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_SCOPE", "session")
    assert MemoryConfig().scope == "session"


@pytest.mark.usefixtures("clean_env")
def test_memory_on_tainted_env_selects_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_ON_TAINTED", "record")
    assert MemoryConfig().on_tainted == "record"  # opt into provenance-marked recording (ADR-0019)


@pytest.mark.usefixtures("clean_env")
def test_memory_env_selects_pgvector_with_dsn_and_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_BACKEND", "pgvector")
    monkeypatch.setenv("CORTEX_MEMORY_DSN", "postgresql://cortex@db/cortex")
    monkeypatch.setenv("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://llama-embed:8081")
    config = MemoryConfig()
    assert config.backend == "pgvector"
    assert config.dsn == "postgresql://cortex@db/cortex"
    assert config.embedder_endpoint == "http://llama-embed:8081"


@pytest.mark.usefixtures("clean_env")
def test_memory_pgvector_without_dsn_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_BACKEND", "pgvector")
    monkeypatch.setenv("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://llama-embed:8081")
    with pytest.raises(ValidationError, match="CORTEX_MEMORY_DSN and CORTEX_MEMORY_EMBEDDER"):
        MemoryConfig()


@pytest.mark.usefixtures("clean_env")
def test_tools_defaults_to_disabled() -> None:
    config = ToolsConfig()
    assert config.backend == "none"
    assert config.endpoint == ""
    assert config.endpoints == {}
    assert config.allow == {}
    assert config.named_endpoints == {}
    assert config.on_unavailable == "fail"  # a dead sidecar is loud unless opted into skip


@pytest.mark.usefixtures("clean_env")
def test_tools_env_selects_the_skip_degraded_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_ON_UNAVAILABLE", "skip")
    assert ToolsConfig().on_unavailable == "skip"


@pytest.mark.usefixtures("clean_env")
def test_tools_rejects_an_unknown_unavailable_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_ON_UNAVAILABLE", "retry")
    with pytest.raises(ValidationError, match="on_unavailable"):
        ToolsConfig()


@pytest.mark.usefixtures("clean_env")
def test_tools_env_selects_mcp_with_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINT", "http://fs:9000/mcp")
    config = ToolsConfig()
    assert config.backend == "mcp"
    assert config.endpoint == "http://fs:9000/mcp"
    # The singular form is the sole named endpoint, so the wiring has one code path.
    assert config.named_endpoints == {"default": "http://fs:9000/mcp"}


@pytest.mark.usefixtures("clean_env")
def test_tools_mcp_without_endpoint_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    with pytest.raises(ValidationError, match="CORTEX_TOOLS_ENDPOINT or CORTEX_TOOLS_ENDPOINTS"):
        ToolsConfig()


@pytest.mark.usefixtures("clean_env")
def test_tools_named_endpoints_merge_and_sort(monkeypatch: pytest.MonkeyPatch) -> None:
    """One env var per sidecar (compose overrides merge key-wise), sorted-name precedence."""
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINTS__FILESYSTEM", "http://mcp-filesystem:9000/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINTS__EMAIL", "http://mcp-email:9100/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ALLOW__FILESYSTEM", '["read_text_file", "list_directory"]')
    config = ToolsConfig()
    assert list(config.named_endpoints) == ["email", "filesystem"]  # sorted, not env order
    assert config.named_endpoints["filesystem"] == "http://mcp-filesystem:9000/mcp"
    assert config.allow == {"filesystem": ("read_text_file", "list_directory")}


@pytest.mark.usefixtures("clean_env")
def test_tools_both_endpoint_forms_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINT", "http://fs:9000/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINTS__EMAIL", "http://mcp-email:9100/mcp")
    with pytest.raises(ValidationError, match="not both"):
        ToolsConfig()


@pytest.mark.usefixtures("clean_env")
def test_tools_allowlist_must_name_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINTS__FILESYSTEM", "http://mcp-filesystem:9000/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ALLOW__GHOST", '["read_text_file"]')
    with pytest.raises(ValidationError, match=r"names no configured endpoint: \['ghost'\]"):
        ToolsConfig()


@pytest.mark.usefixtures("clean_env")
def test_subagents_default_to_disabled() -> None:
    config = SubagentsConfig()
    assert config.backend == "none"
    assert config.endpoint == ""
    assert config.gpu_endpoint == ""
    assert config.model == "subagent"  # a LOGICAL id (ADR-0004), never a path
    # The VRAM ask is the measured one and equals what docker-compose.subagents.yml sets; the CPU
    # and memory asks stay GPU-less-safe placeholders the maintainer measures (ADR-0012).
    assert (config.vram_gb, config.cpus, config.memory_gb) == (3.5, 2.0, 2.0)
    assert (config.cpu_budget, config.mem_budget_gb) == (4.0, 8.0)
    # Against the literal rather than the constant it was assigned from. Ten minutes is twice the
    # longest whole subtask measured on the shipped CPU entry, which is what a queued peer can
    # legitimately sit behind; a tighter number would abort slow work instead of wedged work.
    assert config.stall_timeout_s == 600.0
    # Likewise a literal: one hour is twice the 1800 s the last spawn of a full batch waits under
    # exactly these budgets, so the shipped bound refuses a pool that is not draining rather than
    # one that is merely slow.
    assert config.admission_wait_s == 3600.0


@pytest.mark.usefixtures("clean_env")
def test_subagents_env_selects_llamacpp_with_endpoints_and_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", "http://llama-subagent-cpu:8082")
    monkeypatch.setenv("CORTEX_SUBAGENTS_GPU_ENDPOINT", "http://llama-subagent-gpu:8083")
    monkeypatch.setenv("CORTEX_SUBAGENTS_MODEL", "qwen3-2b")
    monkeypatch.setenv("CORTEX_SUBAGENTS_VRAM_GB", "2.5")
    monkeypatch.setenv("CORTEX_SUBAGENTS_CPU_BUDGET", "6.0")
    config = SubagentsConfig()
    assert config.backend == "llamacpp"
    assert config.endpoint == "http://llama-subagent-cpu:8082"
    assert config.gpu_endpoint == "http://llama-subagent-gpu:8083"
    assert config.model == "qwen3-2b"
    assert config.vram_gb == 2.5
    assert config.cpu_budget == 6.0


@pytest.mark.usefixtures("clean_env")
def test_subagents_llamacpp_without_both_endpoints_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", "http://llama-subagent-cpu:8082")  # GPU missing
    with pytest.raises(ValidationError, match="CORTEX_SUBAGENTS_GPU_ENDPOINT are required"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_subagents_budget_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_CPU_BUDGET", "0")
    with pytest.raises(ValidationError, match="cpu_budget"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_the_subagent_stall_ceiling_is_settable_and_must_be_positive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deployment on faster CPUs tightens it; zero would mean a stream that may never read."""
    monkeypatch.setenv("CORTEX_SUBAGENTS_STALL_TIMEOUT_S", "90")
    assert SubagentsConfig().stall_timeout_s == 90.0
    monkeypatch.setenv("CORTEX_SUBAGENTS_STALL_TIMEOUT_S", "0")
    with pytest.raises(ValidationError, match="stall_timeout_s"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_the_admission_wait_is_settable_including_zero_and_refuses_a_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero is a policy here, unlike the ceiling above: never queue, refuse what does not fit.

    A deployment whose batches are smaller than the shipped cap can tighten the hour; one that
    would rather hear "busy" than wait at all sets zero. Negative is the only nonsense, and it
    would read like a generous bound while refusing every queued spawn.
    """
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "900")
    assert SubagentsConfig().admission_wait_s == 900.0
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "0")
    assert SubagentsConfig().admission_wait_s == 0.0
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "-1")
    with pytest.raises(ValidationError, match="admission_wait_s"):
        SubagentsConfig()


def _llamacpp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", "http://llama-subagent-cpu:8082")
    monkeypatch.setenv("CORTEX_SUBAGENTS_GPU_ENDPOINT", "http://llama-subagent-gpu:8083")


@pytest.mark.usefixtures("clean_env")
def test_subagents_roster_entries_parse_from_env_json(monkeypatch: pytest.MonkeyPatch) -> None:
    # One CORTEX_SUBAGENTS_ROSTER__<name> JSON object per alternate model (ADR-0018); the
    # env-name suffix becomes the lowercase entry name, exactly as the tools endpoints do.
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv(
        "CORTEX_SUBAGENTS_ROSTER__QWEN",
        '{"endpoint": "http://qwen:8083", "memory_gb": 1.5, "description": "small and fast"}',
    )
    monkeypatch.setenv("CORTEX_SUBAGENTS_MODEL_DESCRIPTION", "the sturdy one")
    config = SubagentsConfig()
    assert config.roster == {
        "qwen": SubagentRosterEntry(
            endpoint="http://qwen:8083", memory_gb=1.5, description="small and fast"
        )
    }
    assert config.model_description == "the sturdy one"


@pytest.mark.usefixtures("clean_env")
def test_subagents_named_roster_synthesizes_the_default_from_the_flat_fields() -> None:
    config = SubagentsConfig(
        backend="llamacpp",
        endpoint="http://cpu:8082",
        gpu_endpoint="http://gpu:8082",
        vram_gb=5.5,
        memory_gb=3.0,
        roster={
            "qwen": SubagentRosterEntry(endpoint="http://qwen:8083"),
            "big": SubagentRosterEntry(
                endpoint="http://big:8084", gpu_endpoint="http://big-gpu:8085"
            ),
        },
    )
    named = config.named_roster
    assert list(named) == ["subagent", "big", "qwen"]  # the default first, alternates sorted
    default = named["subagent"]
    assert (default.endpoint, default.gpu_endpoint) == ("http://cpu:8082", "http://gpu:8082")
    assert (default.vram_gb, default.memory_gb) == (5.5, 3.0)
    assert "injection-robust" in default.description  # the advertised default text
    # An alternate's empty gpu_endpoint is normalized to its endpoint; a set one is kept.
    assert named["qwen"].gpu_endpoint == "http://qwen:8083"
    assert named["big"].gpu_endpoint == "http://big-gpu:8085"


@pytest.mark.usefixtures("clean_env")
def test_subagents_named_roster_is_empty_when_delegation_is_disabled() -> None:
    assert SubagentsConfig().named_roster == {}


@pytest.mark.usefixtures("clean_env")
def test_subagents_roster_key_naming_the_default_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The default entry's resources come from the flat fields. A roster entry shadowing it
    # would be a second source of truth.
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv("CORTEX_SUBAGENTS_MODEL", "qwen")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ROSTER__QWEN", '{"endpoint": "http://qwen:8083"}')
    with pytest.raises(ValidationError, match="collides with CORTEX_SUBAGENTS_MODEL"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    ("knob", "value"),
    [("CORTEX_SUBAGENTS_CPUS", "8.0"), ("CORTEX_SUBAGENTS_MEMORY_GB", "16.0")],
)
def test_subagents_reject_a_default_ask_larger_than_the_whole_budget(
    monkeypatch: pytest.MonkeyPatch, knob: str, value: str
) -> None:
    """A spawn the scheduler could only ever refuse is a wiring error, caught at boot."""
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv(knob, value)  # against the 4.0 cpu / 8.0 GB budget defaults
    with pytest.raises(ValidationError, match="no spawn of it could ever be admitted"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_subagents_reject_a_roster_alternate_larger_than_the_whole_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every entry is checked, not just the flat-field default: an alternate carries its own ask."""
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv(
        "CORTEX_SUBAGENTS_ROSTER__QWEN", '{"endpoint": "http://qwen:8083", "cpus": 9.0}'
    )
    with pytest.raises(ValidationError, match="subagent 'qwen' asks for"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_subagents_accept_an_ask_equal_to_the_whole_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scheduler admits an exactly-budget charge (alone), so the boot check must too."""
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv("CORTEX_SUBAGENTS_CPUS", "4.0")
    monkeypatch.setenv("CORTEX_SUBAGENTS_MEMORY_GB", "8.0")
    assert SubagentsConfig().named_roster["subagent"].cpus == 4.0


@pytest.mark.usefixtures("clean_env")
def test_subagents_ignore_the_budget_check_while_delegation_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With backend=none no scheduler exists, so a stale ask blocks nothing (empty roster)."""
    monkeypatch.setenv("CORTEX_SUBAGENTS_CPUS", "99.0")
    assert SubagentsConfig().named_roster == {}


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize("entry", ['{"description": "no endpoint"}', '{"endpoint": ""}'])
def test_subagents_roster_entry_requires_an_endpoint(
    monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv("CORTEX_SUBAGENTS_ROSTER__QWEN", entry)
    with pytest.raises(ValidationError, match="endpoint"):
        SubagentsConfig()


def test_seam_confirm_timeout_defaults_generous() -> None:
    assert SeamServerConfig().confirm_timeout_s == 120.0


def test_seam_env_overrides_the_confirm_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_CONFIRM_TIMEOUT_S", "7.5")
    assert SeamServerConfig().confirm_timeout_s == 7.5


def test_seam_rejects_a_non_positive_confirm_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_CONFIRM_TIMEOUT_S", "0")
    with pytest.raises(ValidationError):
        SeamServerConfig()


def test_tools_gated_defaults_to_escalate_and_send_email() -> None:
    # The fail-closed pairing (ADR-0022): enabling the email sidecar's write path without
    # touching gating config still gates it. The escalate built-in joins as the dispatcher's
    # backstop behind its own always-gated advertised flag (ADR-0030 decision 1).
    assert ToolsConfig().gated == (ESCALATE_TOOL_NAME, "send_email")


def test_tools_env_overrides_the_gated_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATED", '["send_email", "set_volume"]')
    assert ToolsConfig().gated == ("send_email", "set_volume")


def test_tools_env_empties_the_gated_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATED", "[]")
    assert ToolsConfig().gated == ()


def test_gate_reasons_default_to_the_escalate_card_text() -> None:
    # The one per-tool reason wired out of the box (ADR-0030 decision 1): the generic
    # "outbound or irreversible" line is false about a model swap, so the escalate card says
    # what is actually being approved; every other gated tool keeps the generic reason.
    policy = ToolsConfig().dispatch_policy
    assert policy.gate_reasons == {ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON}


def test_gate_reasons_env_sets_one_tool_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATE_REASONS__SEND_EMAIL", "this sends email as you")
    assert ToolsConfig().gate_reason_map == {
        ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON,
        "send_email": "this sends email as you",
    }


def test_setting_one_gate_reason_does_not_silently_drop_the_escalate_one() -> None:
    # Same merge argument as cost_policy: a nested-dict env key replaces the whole mapping,
    # so the built-in escalate reason is merged under the user's, never kept as the default.
    merged = ToolsConfig(gate_reasons={"send_email": "sends as you"}).gate_reason_map
    assert merged[ESCALATE_TOOL_NAME] == ESCALATE_GATE_REASON
    assert merged["send_email"] == "sends as you"


def test_restating_the_escalate_gate_reason_overrides_it() -> None:
    # The merge is a floor, not a lock: a user who names the tool explicitly means it.
    merged = ToolsConfig(gate_reasons={ESCALATE_TOOL_NAME: "my own words"}).gate_reason_map
    assert merged[ESCALATE_TOOL_NAME] == "my own words"


def test_a_blank_gate_reason_fails_at_boot() -> None:
    # A blank reason would render an empty confirm-card line: a consent surface that no
    # longer says what is being approved fails loudly at boot, not silently on screen.
    with pytest.raises(ValidationError, match=r"GATE_REASONS must be non-empty.*send_email"):
        ToolsConfig(gate_reasons={"send_email": "   "})


def test_tools_costs_price_only_the_fan_out_tool_by_default() -> None:
    # `spawn_subagents` is the one wired tool whose single dispatch becomes a batch of model
    # runs and which no confirmation gate bounds (ADR-0009 cost addendum). `send_email` is
    # deliberately unpriced: every send already needs the user's approval.
    policy = ToolsConfig().cost_policy
    assert policy.cost_of(SPAWN_TOOL_NAME) == DEFAULT_SPAWN_COST
    assert DEFAULT_SPAWN_COST * 4 == MAX_TOOL_DISPATCHES  # four delegations a turn
    assert policy.cost_of("send_email") == DEFAULT_TOOL_COST


def test_tools_env_prices_one_tool_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # The per-key form (not a JSON blob) is what lets layered compose overrides each
    # contribute the price of the tool they enable. Env keys are matched case-insensitively,
    # so the compose-style uppercase name reaches the lowercase tool name.
    monkeypatch.setenv("CORTEX_TOOLS_COSTS__READ_FILE", "3")
    assert ToolsConfig().costs == {"read_file": 3}


def test_pricing_one_tool_does_not_silently_unprice_the_built_in_one() -> None:
    # A nested-dict env key replaces the whole mapping, so a built-in price kept as the
    # field's default would vanish the moment a user priced anything else, un-pricing the
    # fan-out tool as a side effect of an unrelated knob. The policy merges instead.
    policy = ToolsConfig(costs={"read_file": 3}).cost_policy
    assert policy.cost_of("read_file") == 3
    assert policy.cost_of(SPAWN_TOOL_NAME) == DEFAULT_SPAWN_COST
    assert policy.cost_of("anything_else") == DEFAULT_TOOL_COST


def test_restating_a_built_in_price_overrides_it() -> None:
    # The merge is a floor, not a lock: a user who names the tool explicitly means it.
    assert ToolsConfig(costs={SPAWN_TOOL_NAME: 2}).cost_policy.cost_of(SPAWN_TOOL_NAME) == 2


@pytest.mark.parametrize("cost", [0, -2, MAX_TOOL_DISPATCHES + 1])
def test_a_tool_cost_outside_the_budget_range_fails_at_boot(cost: int) -> None:
    # Both ends hide rather than announce themselves at runtime: free means the budget stops
    # bounding that tool, and unaffordable means it never runs and the first call closes the
    # turn's budget. Neither is worth debugging from behavior, so the brain refuses to start.
    expected = rf"CORTEX_TOOLS_COSTS must be 1\.\.{MAX_TOOL_DISPATCHES}: \['read_file'\]"
    with pytest.raises(ValidationError, match=expected):
        ToolsConfig(costs={"read_file": cost})


def test_salience_defaults_to_refusing_a_repeat() -> None:
    # A bound ships on, like the round cap and the dispatch budget before it: one that ships
    # off protects nobody, and its escape hatch is the knob below.
    assert ToolsConfig().salience_policy is REPEAT_SALIENCE


def test_salience_off_restores_the_unfiltered_loop() -> None:
    # The core takes a policy object; the composition root maps the string, the
    # record_tainted_memory precedent.
    assert ToolsConfig(salience="off").salience_policy is ALWAYS_SALIENT


def test_an_unknown_salience_name_fails_at_boot() -> None:
    # A typo would otherwise silently keep the default, which is the failure mode a knob whose
    # whole purpose is to turn a bound off must not have.
    with pytest.raises(ValidationError):
        ToolsConfig(salience="sometimes")  # pyright: ignore[reportArgumentType]


def test_the_dispatch_policy_carries_all_three_declarations() -> None:
    # One value is what the dispatcher and both its builders take, so a declaration cannot
    # reach the cortex and miss subagents (or the reverse) by being threaded separately.
    policy = ToolsConfig(
        gated=("send_email",), costs={"read_file": 3}, salience="off"
    ).dispatch_policy
    assert policy.gated_names == frozenset({"send_email"})
    assert policy.costs.cost_of("read_file") == 3
    assert policy.salience is ALWAYS_SALIENT
