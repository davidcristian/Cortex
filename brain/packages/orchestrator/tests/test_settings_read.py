import logging
import traceback

import pytest
from pydantic_settings import BaseSettings

from cortex_orchestrator.config import (
    BrainRuntimeConfig,
    InferenceConfig,
    MemoryConfig,
    RpcServerConfig,
)
from cortex_orchestrator.config_body import BodyConfig
from cortex_orchestrator.config_reply import ReplyBoundsConfig
from cortex_orchestrator.config_schedule import ScheduleConfig
from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.config_swap import SwapConfig
from cortex_orchestrator.config_tools import ToolsConfig
from cortex_orchestrator.entry import main
from cortex_settings import ConfigError, read_settings

MALFORMED: list[tuple[type[BaseSettings], str, str]] = [
    (RpcServerConfig, "CORTEX_SEAM_PORT", "23o51"),
    (BrainRuntimeConfig, "CORTEX_HISTORY_CHAR_BUDGET", "lots"),
    (BrainRuntimeConfig, "CORTEX_VRAM_CORTEX_GB", "-7.5"),
    (InferenceConfig, "CORTEX_VISION", "maybe"),
    (MemoryConfig, "CORTEX_MEMORY_RECALL_POOL_FACTOR", "four"),
    (ToolsConfig, "CORTEX_TOOLS_GATED", "[read_text_file"),
    (ToolsConfig, "CORTEX_TOOLS_ENDPOINTS", "{fs: http"),
    (ToolsConfig, "CORTEX_TOOLS_COSTS", '{"fetch": "dear"}'),
    (BodyConfig, "CORTEX_BODY_CAPTURE_MAX_EDGE", "wide"),
    (SubagentsConfig, "CORTEX_SUBAGENTS_VRAM_GB", "big"),
    (ScheduleConfig, "CORTEX_SCHEDULE_TZ", "Mars/Olympus"),
    (SwapConfig, "CORTEX_SWAP_BRAIN_VRAM_MIB", "lots"),
    (SwapConfig, "CORTEX_MODELHOST_TIMEOUT_S", "soon"),
    (ReplyBoundsConfig, "CORTEX_REPLY_THINKING", "perhaps"),
]


def _refusal(cls: type[BaseSettings]) -> ConfigError:
    with pytest.raises(ConfigError) as caught:
        read_settings(cls)
    return caught.value


@pytest.mark.parametrize(("cls", "variable", "value"), MALFORMED)
def test_a_malformed_value_is_named_by_its_variable_and_never_shown(
    monkeypatch: pytest.MonkeyPatch, cls: type[BaseSettings], variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)
    refusal = _refusal(cls)
    text = "".join(traceback.format_exception(refusal))
    assert str(refusal).startswith(variable)
    assert value not in text


def test_a_validator_message_keeps_its_reason_without_the_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_SCHEDULE_TZ", "Mars/Olympus")
    assert str(_refusal(ScheduleConfig)) == "CORTEX_SCHEDULE_TZ: unknown timezone '<value>'"


def test_a_value_that_is_not_json_is_named_as_such(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_GATED", "[read_text_file")
    assert str(_refusal(ToolsConfig)) == "CORTEX_TOOLS_GATED is not valid JSON"


def test_every_refused_field_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_PORT", "23o51")
    monkeypatch.setenv("CORTEX_SEAM_CONVERSE_BUFFER", "0")
    assert str(_refusal(RpcServerConfig)) == (
        "CORTEX_SEAM_PORT: Input should be a valid integer, unable to parse string as an "
        "integer; CORTEX_SEAM_CONVERSE_BUFFER: Input should be greater than 0"
    )


def test_a_refusal_of_the_whole_class_keeps_its_own_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORTEX_INFERENCE_BACKEND", "llamacpp")
    assert str(_refusal(InferenceConfig)) == (
        "CORTEX_INFERENCE_ENDPOINT is required when CORTEX_INFERENCE_BACKEND=llamacpp"
    )


def test_an_unreadable_redis_url_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_REDIS_URL", "redis://:qx7vault/z9@redis:6379")
    refusal = _refusal(BrainRuntimeConfig)
    assert str(refusal).startswith("CORTEX_REDIS_URL")
    assert "qx7vault" not in "".join(traceback.format_exception(refusal))


def test_a_valid_environment_reads_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SEAM_PORT", "23052")
    assert read_settings(RpcServerConfig).port == 23052


def test_the_entry_logs_a_refused_setting_and_exits_1(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CORTEX_SCHEDULE_TZ", "Mars/Olympus")

    async def serve() -> None:
        read_settings(ScheduleConfig)

    with caplog.at_level(logging.ERROR, logger="cortex_orchestrator.entry"):
        assert main(serve, configure=lambda: None) == 1
    [record] = caplog.records
    assert record.getMessage() == "setting refused"
    assert record.__dict__["reason"] == "CORTEX_SCHEDULE_TZ: unknown timezone '<value>'"


def test_the_entry_exits_0_when_serving_ends(caplog: pytest.LogCaptureFixture) -> None:
    configured: list[bool] = []

    async def serve() -> None:
        return None

    assert main(serve, configure=lambda: configured.append(True)) == 0
    assert configured == [True]
    assert caplog.records == []


def test_an_empty_value_leaves_the_reason_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_SCHEDULE_TZ", "")
    assert str(_refusal(ScheduleConfig)) == "CORTEX_SCHEDULE_TZ: unknown timezone ''"


def test_a_refused_memory_backend_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORTEX_MEMORY_BACKEND", "pgvector")
    assert str(_refusal(MemoryConfig)).startswith("CORTEX_MEMORY_DSN and")
