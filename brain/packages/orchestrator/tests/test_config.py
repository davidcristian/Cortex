import os

import pytest
from pydantic import ValidationError

from cortex_core import (
    ALWAYS_SALIENT,
    DEFAULT_TOOL_CALL_TIMEOUT_S,
    ESCALATE_GATE_REASON,
    ESCALATE_TOOL_NAME,
    MAX_IDENTICAL_DISPATCHES,
    MAX_TOOL_DISPATCHES,
    SPAWN_TOOL_NAME,
    AttemptBounds,
    PlacementRequest,
    PlacementTarget,
    RepeatSalience,
    VramBudgetPlacer,
)
from cortex_core.tool_budget import DEFAULT_TOOL_COST
from cortex_orchestrator import (
    BodyConfig,
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    MemoryConfigError,
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
        "CORTEX_BODY_CALL_TIMEOUT_S",
        "CORTEX_VISION",
    ):
        monkeypatch.delenv(name, raising=False)
    for name in list(os.environ):
        if name.startswith(("CORTEX_TOOLS_ENDPOINTS__", "CORTEX_TOOLS_ALLOW__")):
            monkeypatch.delenv(name, raising=False)


@pytest.mark.usefixtures("clean_env")
def test_seam_defaults_are_loopback_50051() -> None:
    config = SeamServerConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 50051
    assert config.bind_address == "127.0.0.1:50051"
    assert config.converse_buffer == 256
    assert config.token == ""


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
    assert config.cortex_model == "cortex"
    assert config.vram_soft_cap_gb == 14.0
    assert config.cortex_reservation_gb == 8.6
    assert config.history_char_budget == 48_000
    assert config.output_guardrail == "redact"
    assert config.generate_titles is False
    assert config.history_summary is True
    assert config.history_recap_min_chars == 2_000


@pytest.mark.usefixtures("clean_env")
def test_the_shipped_budget_places_one_subagent_on_the_gpu_and_overflows_the_next() -> None:
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
    measured_peak_mib = 3410
    margin_mib = SubagentsConfig().vram_gb * 1024 - measured_peak_mib
    assert margin_mib >= 130


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_overrides_the_history_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_HISTORY_CHAR_BUDGET", "1000")
    assert BrainRuntimeConfig().history_char_budget == 1000


@pytest.mark.usefixtures("clean_env")
def test_runtime_rejects_a_negative_history_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_HISTORY_CHAR_BUDGET", "-1")
    with pytest.raises(ValidationError, match="history_char_budget"):
        BrainRuntimeConfig()


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_turns_the_history_summary_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_HISTORY_SUMMARY", "false")
    assert BrainRuntimeConfig().history_summary is False


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_sets_how_much_dropped_text_is_worth_a_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setenv("CORTEX_OUTPUT_GUARDRAIL", "strict")
    assert BrainRuntimeConfig().output_guardrail == "strict"


@pytest.mark.usefixtures("clean_env")
def test_runtime_env_selects_the_lookalike_guardrail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_OUTPUT_GUARDRAIL", "lookalike")
    assert BrainRuntimeConfig().output_guardrail == "lookalike"


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
    assert config.vision == "auto"
    assert config.stall_timeout_s == 120.0


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize("mode", ["on", "off", "auto"])
def test_the_vision_mode_is_settable_to_each_of_its_three_answers(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("CORTEX_VISION", mode)
    assert InferenceConfig().vision == mode


@pytest.mark.usefixtures("clean_env")
def test_the_trace_budget_mode_is_read_from_the_deployments_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_INFERENCE_TRACE_LEVER", "on")
    assert InferenceConfig().send_trace_budget == "on"


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
    # Compared against literals rather than the constants production reads, so the check says what
    # a deployment gets rather than restating a declaration. A 0 capture edge asks the body for its
    # own default instead, and the body's own default is 1600.
    assert (
        config.capture_max_edge,
        config.max_image_bytes,
        config.capture_timeout_s,
        config.call_timeout_s,
    ) == (2048, 6291456, 10.0, 5.0)


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CORTEX_BODY_CAPTURE_MAX_EDGE", "-1"),
        ("CORTEX_BODY_CAPTURE_MAX_EDGE", "8193"),
        ("CORTEX_BODY_MAX_IMAGE_BYTES", "0"),
        ("CORTEX_BODY_MAX_IMAGE_BYTES", "6291457"),
        ("CORTEX_BODY_MAX_IMAGE_BYTES", "5000000000"),
        ("CORTEX_BODY_CAPTURE_TIMEOUT_S", "0"),
        ("CORTEX_BODY_CAPTURE_TIMEOUT_S", "-3"),
        ("CORTEX_BODY_CALL_TIMEOUT_S", "0"),
        ("CORTEX_BODY_CALL_TIMEOUT_S", "-3"),
    ],
)
def test_a_capture_bound_outside_the_seam_fails_at_boot(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        BodyConfig()


@pytest.mark.usefixtures("clean_env")
def test_a_tightened_capture_bound_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_BODY_CAPTURE_MAX_EDGE", "1280")
    monkeypatch.setenv("CORTEX_BODY_MAX_IMAGE_BYTES", "2000000")
    monkeypatch.setenv("CORTEX_BODY_CAPTURE_TIMEOUT_S", "2.5")
    monkeypatch.setenv("CORTEX_BODY_CALL_TIMEOUT_S", "1.5")
    config = BodyConfig()
    assert (
        config.capture_max_edge,
        config.max_image_bytes,
        config.capture_timeout_s,
        config.call_timeout_s,
    ) == (1280, 2_000_000, 2.5, 1.5)


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
    assert config.scope == "global"
    assert config.on_tainted == "skip"
    assert config.recall == "judge"


@pytest.mark.usefixtures("clean_env")
def test_memory_scope_env_selects_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_SCOPE", "session")
    assert MemoryConfig().scope == "session"


@pytest.mark.usefixtures("clean_env")
def test_memory_on_tainted_env_selects_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_ON_TAINTED", "record")
    assert MemoryConfig().on_tainted == "record"


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
    with pytest.raises(MemoryConfigError, match="CORTEX_MEMORY_DSN and CORTEX_MEMORY_EMBEDDER"):
        MemoryConfig()


@pytest.mark.usefixtures("clean_env")
def test_memory_pgvector_takes_a_dsn_the_driver_can_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_BACKEND", "pgvector")
    monkeypatch.setenv("CORTEX_MEMORY_DSN", "postgresql://cortex:hunter@postgres:5432/cortex")
    monkeypatch.setenv("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://llama-embed:8081")
    assert MemoryConfig().dsn == "postgresql://cortex:hunter@postgres:5432/cortex"


@pytest.mark.usefixtures("clean_env")
def test_memory_dsn_the_driver_cannot_read_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_BACKEND", "pgvector")
    monkeypatch.setenv("CORTEX_MEMORY_DSN", "postgresql://cortex:hun/ter@postgres:5432/cortex")
    monkeypatch.setenv("CORTEX_MEMORY_EMBEDDER_ENDPOINT", "http://llama-embed:8081")
    with pytest.raises(MemoryConfigError) as refused:
        MemoryConfig()
    message = str(refused.value)
    assert "CORTEX_MEMORY_DSN" in message
    assert "hun" not in message
    assert "postgresql" not in message


@pytest.mark.usefixtures("clean_env")
def test_memory_dsn_is_unread_while_the_backend_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_DSN", "postgresql://cortex:hun/ter@postgres:5432/cortex")
    assert MemoryConfig().backend == "none"


@pytest.mark.usefixtures("clean_env")
def test_tools_defaults_to_disabled() -> None:
    config = ToolsConfig()
    assert config.backend == "none"
    assert config.endpoint == ""
    assert config.endpoints == {}
    assert config.allow == {}
    assert config.named_endpoints == {}
    assert config.on_unavailable == "fail"


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
    assert config.named_endpoints == {"default": "http://fs:9000/mcp"}


@pytest.mark.usefixtures("clean_env")
def test_tools_mcp_without_endpoint_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    with pytest.raises(ValidationError, match="CORTEX_TOOLS_ENDPOINT or CORTEX_TOOLS_ENDPOINTS"):
        ToolsConfig()


@pytest.mark.usefixtures("clean_env")
def test_tools_named_endpoints_merge_and_sort(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINTS__FILESYSTEM", "http://mcp-filesystem:9000/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINTS__EMAIL", "http://mcp-email:9100/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ALLOW__FILESYSTEM", '["read_text_file", "list_directory"]')
    config = ToolsConfig()
    assert list(config.named_endpoints) == ["email", "filesystem"]
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
    assert config.model == "subagent"
    assert (config.vram_gb, config.cpus, config.memory_gb) == (3.5, 2.0, 3.0)
    assert (config.cpu_budget, config.mem_budget_gb) == (4.0, 8.0)
    assert config.stall_timeout_s == 600.0
    assert config.admission_wait_s == 7200.0


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
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", "http://llama-subagent-cpu:8082")
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
    monkeypatch.setenv("CORTEX_SUBAGENTS_STALL_TIMEOUT_S", "90")
    assert SubagentsConfig().stall_timeout_s == 90.0
    monkeypatch.setenv("CORTEX_SUBAGENTS_STALL_TIMEOUT_S", "0")
    with pytest.raises(ValidationError, match="stall_timeout_s"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_the_admission_wait_is_settable_including_zero_and_refuses_a_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "6000")
    assert SubagentsConfig().admission_wait_s == 6000.0
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "0")
    assert SubagentsConfig().admission_wait_s == 0.0
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "-1")
    with pytest.raises(ValidationError, match="admission_wait_s"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_the_total_generation_cap_is_settable_and_both_halves_must_be_real_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_MAX_TOKENS", "512")
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "900")
    config = SubagentsConfig()
    assert config.attempt_bounds == AttemptBounds(max_tokens=512, timeout_s=900.0)
    monkeypatch.setenv("CORTEX_SUBAGENTS_MAX_TOKENS", "0")
    with pytest.raises(ValidationError, match="max_tokens"):
        SubagentsConfig()
    monkeypatch.setenv("CORTEX_SUBAGENTS_MAX_TOKENS", "512")
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "0")
    with pytest.raises(ValidationError, match="run_timeout_s"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_a_run_deadline_that_would_hide_the_stall_ceiling_fails_the_brain_at_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_STALL_TIMEOUT_S", "600")
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "600")
    with pytest.raises(ValidationError, match="must be greater than"):
        SubagentsConfig()
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "601")
    assert SubagentsConfig().run_timeout_s == 601.0


@pytest.mark.usefixtures("clean_env")
def test_a_hold_no_queued_peer_would_outlast_fails_the_brain_at_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "1800")
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "900")
    with pytest.raises(ValidationError, match="which must be less than"):
        SubagentsConfig()
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "2400")
    with pytest.raises(ValidationError, match="which must be less than"):
        SubagentsConfig()
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "899.5")
    assert SubagentsConfig().run_timeout_s == 899.5


@pytest.mark.usefixtures("clean_env")
def test_what_the_wait_is_compared_with_is_the_hold_and_not_one_attempts_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "1800")
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "1000")
    with pytest.raises(ValidationError, match=r"can hold its room for 2000\.0 s"):
        SubagentsConfig()
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "2001")
    assert SubagentsConfig().attempt_bounds.timeout_s == 1000.0


@pytest.mark.usefixtures("clean_env")
def test_a_pool_that_never_queues_keeps_whatever_deadline_it_was_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_ADMISSION_WAIT_S", "0")
    monkeypatch.setenv("CORTEX_SUBAGENTS_RUN_TIMEOUT_S", "3000")
    config = SubagentsConfig()
    assert config.admission_wait_s == 0.0
    assert config.run_timeout_s == 3000.0


def _llamacpp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SUBAGENTS_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", "http://llama-subagent-cpu:8082")
    monkeypatch.setenv("CORTEX_SUBAGENTS_GPU_ENDPOINT", "http://llama-subagent-gpu:8083")


@pytest.mark.usefixtures("clean_env")
def test_subagents_roster_entries_parse_from_env_json(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert list(named) == ["subagent", "big", "qwen"]
    default = named["subagent"]
    assert (default.endpoint, default.gpu_endpoint) == ("http://cpu:8082", "http://gpu:8082")
    assert (default.vram_gb, default.memory_gb) == (5.5, 3.0)
    assert "injection-robust" in default.description
    assert named["qwen"].gpu_endpoint == "http://qwen:8083"
    assert named["big"].gpu_endpoint == "http://big-gpu:8085"


@pytest.mark.usefixtures("clean_env")
def test_subagents_named_roster_is_empty_when_delegation_is_disabled() -> None:
    assert SubagentsConfig().named_roster == {}


@pytest.mark.usefixtures("clean_env")
def test_subagents_roster_key_naming_the_default_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv("CORTEX_SUBAGENTS_MODEL", "qwen")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ROSTER__QWEN", '{"endpoint": "http://qwen:8083"}')
    with pytest.raises(ValidationError, match="collides with CORTEX_SUBAGENTS_MODEL"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
@pytest.mark.parametrize(
    ("variable", "value"),
    [("CORTEX_SUBAGENTS_CPUS", "8.0"), ("CORTEX_SUBAGENTS_MEMORY_GB", "16.0")],
)
def test_subagents_reject_a_default_ask_larger_than_the_whole_budget(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValidationError, match="no spawn of it could ever be admitted"):
        SubagentsConfig()


@pytest.mark.usefixtures("clean_env")
def test_subagents_reject_a_roster_alternate_larger_than_the_whole_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    _llamacpp_env(monkeypatch)
    monkeypatch.setenv("CORTEX_SUBAGENTS_CPUS", "4.0")
    monkeypatch.setenv("CORTEX_SUBAGENTS_MEMORY_GB", "8.0")
    assert SubagentsConfig().named_roster["subagent"].cpus == 4.0


@pytest.mark.usefixtures("clean_env")
def test_subagents_ignore_the_budget_check_while_delegation_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert ToolsConfig().gated == (ESCALATE_TOOL_NAME, "send_email")


def test_tools_env_overrides_the_gated_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATED", '["send_email", "set_volume"]')
    assert ToolsConfig().gated == ("send_email", "set_volume")


def test_tools_env_empties_the_gated_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATED", "[]")
    assert ToolsConfig().gated == ()


def test_gate_reasons_default_to_the_escalate_card_text() -> None:
    policy = ToolsConfig().dispatch_policy
    assert policy.gate_reasons == {ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON}


def test_gate_reasons_env_sets_one_tool_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATE_REASONS__SEND_EMAIL", "this sends email as you")
    assert ToolsConfig().gate_reason_map == {
        ESCALATE_TOOL_NAME: ESCALATE_GATE_REASON,
        "send_email": "this sends email as you",
    }


def test_setting_one_gate_reason_does_not_silently_drop_the_escalate_one() -> None:
    merged = ToolsConfig(gate_reasons={"send_email": "sends as you"}).gate_reason_map
    assert merged[ESCALATE_TOOL_NAME] == ESCALATE_GATE_REASON
    assert merged["send_email"] == "sends as you"


def test_restating_the_escalate_gate_reason_overrides_it() -> None:
    merged = ToolsConfig(gate_reasons={ESCALATE_TOOL_NAME: "my own words"}).gate_reason_map
    assert merged[ESCALATE_TOOL_NAME] == "my own words"


def test_a_blank_gate_reason_fails_at_boot() -> None:
    with pytest.raises(ValidationError, match=r"GATE_REASONS must be non-empty.*send_email"):
        ToolsConfig(gate_reasons={"send_email": "   "})


def test_tools_costs_price_only_the_fan_out_tool_by_default() -> None:
    policy = ToolsConfig().cost_policy
    assert policy.cost_of(SPAWN_TOOL_NAME) == DEFAULT_SPAWN_COST
    assert DEFAULT_SPAWN_COST * 4 == MAX_TOOL_DISPATCHES
    assert policy.cost_of("send_email") == DEFAULT_TOOL_COST


def test_tools_env_prices_one_tool_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_COSTS__READ_FILE", "3")
    assert ToolsConfig().costs == {"read_file": 3}


def test_pricing_one_tool_does_not_silently_unprice_the_built_in_one() -> None:
    policy = ToolsConfig(costs={"read_file": 3}).cost_policy
    assert policy.cost_of("read_file") == 3
    assert policy.cost_of(SPAWN_TOOL_NAME) == DEFAULT_SPAWN_COST
    assert policy.cost_of("anything_else") == DEFAULT_TOOL_COST


def test_restating_a_built_in_price_overrides_it() -> None:
    assert ToolsConfig(costs={SPAWN_TOOL_NAME: 2}).cost_policy.cost_of(SPAWN_TOOL_NAME) == 2


@pytest.mark.parametrize("cost", [0, -2, MAX_TOOL_DISPATCHES + 1])
def test_a_tool_cost_outside_the_budget_range_fails_at_boot(cost: int) -> None:
    expected = rf"CORTEX_TOOLS_COSTS must be 1\.\.{MAX_TOOL_DISPATCHES}: \['read_file'\]"
    with pytest.raises(ValidationError, match=expected):
        ToolsConfig(costs={"read_file": cost})


def test_salience_defaults_to_refusing_a_repeat() -> None:
    assert ToolsConfig().salience_policy == RepeatSalience(limit=MAX_IDENTICAL_DISPATCHES)


def test_salience_off_restores_the_unfiltered_loop() -> None:
    assert ToolsConfig(salience="off").salience_policy is ALWAYS_SALIENT


def test_the_configured_salience_limit_reaches_the_policy() -> None:
    assert ToolsConfig(salience_limit=3).salience_policy == RepeatSalience(limit=3)


@pytest.mark.parametrize("limit", [0, -1])
def test_a_salience_limit_below_one_fails_at_boot(limit: int) -> None:
    expected = f"CORTEX_TOOLS_SALIENCE_LIMIT must be positive: {limit}"
    with pytest.raises(ValidationError, match=expected):
        ToolsConfig(salience_limit=limit)


def test_the_salience_limit_is_inert_when_salience_is_off() -> None:
    assert ToolsConfig(salience="off", salience_limit=5).salience_policy is ALWAYS_SALIENT


@pytest.mark.parametrize("timeout_s", [0.0, -1.0])
def test_a_call_timeout_that_is_not_a_duration_fails_at_boot(timeout_s: float) -> None:
    with pytest.raises(ValidationError):
        ToolsConfig(call_timeout_s=timeout_s)


def test_the_shipped_call_timeout_is_the_cores_own_bound() -> None:
    assert ToolsConfig().call_timeout_s == DEFAULT_TOOL_CALL_TIMEOUT_S


def test_an_unknown_salience_name_fails_at_boot() -> None:
    with pytest.raises(ValidationError):
        ToolsConfig(salience="sometimes")  # pyright: ignore[reportArgumentType]


def test_the_dispatch_policy_carries_all_three_declarations() -> None:
    policy = ToolsConfig(
        gated=("send_email",), costs={"read_file": 3}, salience="off"
    ).dispatch_policy
    assert policy.gated_names == frozenset({"send_email"})
    assert policy.costs.cost_of("read_file") == 3
    assert policy.salience is ALWAYS_SALIENT
