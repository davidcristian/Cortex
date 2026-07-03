"""Config behavior: defaults and env overrides for the settings models."""

import os

import pytest
from pydantic import ValidationError

from cortex_orchestrator import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    SeamServerConfig,
    SubagentsConfig,
    ToolsConfig,
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CORTEX_SEAM_HOST",
        "CORTEX_SEAM_PORT",
        "CORTEX_REDIS_URL",
        "CORTEX_MODEL_CORTEX",
        "CORTEX_INFERENCE_BACKEND",
        "CORTEX_INFERENCE_ENDPOINT",
        "CORTEX_MEMORY_BACKEND",
        "CORTEX_MEMORY_DSN",
        "CORTEX_MEMORY_EMBEDDER_ENDPOINT",
        "CORTEX_MEMORY_EMBEDDER_MODEL",
        "CORTEX_TOOLS_BACKEND",
        "CORTEX_TOOLS_ENDPOINT",
        "CORTEX_SUBAGENTS_BACKEND",
        "CORTEX_SUBAGENTS_ENDPOINT",
        "CORTEX_SUBAGENTS_MODEL",
        "CORTEX_SUBAGENTS_MAX_CONCURRENCY",
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
def test_memory_defaults_to_disabled() -> None:
    config = MemoryConfig()
    assert config.backend == "none"
    assert config.dsn == ""
    assert config.embedder_endpoint == ""


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
