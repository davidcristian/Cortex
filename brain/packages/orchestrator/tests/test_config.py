"""Config behavior: defaults and env overrides for the settings models."""

import os

import pytest
from pydantic import ValidationError

from cortex_core import (
    ALWAYS_SALIENT,
    MAX_TOOL_DISPATCHES,
    REPEAT_SALIENCE,
    SPAWN_TOOL_NAME,
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
    assert config.cortex_reservation_gb == 11.3  # gemma-4-12B footprint (ADR-0004 addendum)
    assert config.history_char_budget == 48_000  # ≈12K of the 16K-token context (ADR-0014)
    assert config.output_guardrail == "redact"  # the laundering defense ships on (ADR-0015)


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
def test_body_defaults_to_disabled() -> None:
    config = BodyConfig()
    assert config.backend == "none"
    assert config.endpoint == ""


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
    # GPU-less-safe placeholders; the maintainer measures the real numbers on the host (ADR-0012).
    assert (config.vram_gb, config.cpus, config.memory_gb) == (2.0, 2.0, 2.0)
    assert (config.cpu_budget, config.mem_budget_gb) == (4.0, 8.0)


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


def test_tools_gated_defaults_to_send_email() -> None:
    # The fail-closed pairing (ADR-0022): enabling the email sidecar's write path without
    # touching gating config still gates it.
    assert ToolsConfig().gated == ("send_email",)


def test_tools_env_overrides_the_gated_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATED", '["send_email", "set_volume"]')
    assert ToolsConfig().gated == ("send_email", "set_volume")


def test_tools_env_empties_the_gated_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATED", "[]")
    assert ToolsConfig().gated == ()


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
