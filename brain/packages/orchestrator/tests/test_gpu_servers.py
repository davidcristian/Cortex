import asyncio
import logging

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis.asyncio import Redis

from cortex_orchestrator import ToolCallDeadlineError, run_from_env
from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.config_swap import SwapConfig
from cortex_orchestrator.gpu_servers import (
    UNMATCHED_GPU_SERVERS,
    hosted_gpu_servers,
    warn_of_unmatched_gpu_servers,
)
from cortex_session import RedisSessionStore

_HOST = "http://model-host:9300"
_CPU = "http://llama-subagent:8082"
_ONE = "http://model-host:8083"
_TWO = f"{_ONE},http://model-host:8084"
_THREE = f"{_TWO},http://model-host:8085"
_OWN = "http://llama-subagent-gpu:8083"
_FIRST = ("subagent-gpu",)
_BOTH = ("subagent-gpu", "subagent-gpu-2")
_SETTINGS = (
    "CORTEX_SUBAGENTS_GPU_SERVERS",
    "CORTEX_ESCALATION",
    "CORTEX_SWAP_EVICT_MODELS",
    "CORTEX_MODELHOST_BACKEND",
)


@pytest.fixture(autouse=True)
def no_deployment_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _SETTINGS:
        monkeypatch.delenv(name, raising=False)


def _subagents(gpu_endpoint: str, gpu_servers: int = 2) -> SubagentsConfig:
    return SubagentsConfig(
        backend="llamacpp", endpoint=_CPU, gpu_endpoint=gpu_endpoint, gpu_servers=gpu_servers
    )


def _swap(
    evict_models: tuple[str, ...] = (), *, escalation: bool = False, host: str = _HOST
) -> SwapConfig:
    return SwapConfig(
        escalation=escalation,
        modelhost_backend="supervisor" if escalation else "none",
        modelhost_endpoint=host,
        brain_endpoint="http://model-host:8081",
        evict_models=evict_models,
    )


def _warned(caplog: pytest.LogCaptureFixture) -> list[tuple[object, object, object]]:
    return [
        (
            getattr(record, "gpu_servers", None),
            getattr(record, "gpu_endpoints", None),
            getattr(record, "evict_models", None),
        )
        for record in caplog.records
        if record.getMessage() == UNMATCHED_GPU_SERVERS
    ]


@pytest.mark.parametrize(
    ("gpu_endpoint", "host", "hosted"),
    [
        (_TWO, _HOST, 2),
        (_CPU, _HOST, 0),
        (_OWN, _HOST, 0),
        (f"{_OWN},{_ONE}", _HOST, 1),
        (_TWO, "", 0),
        ("model-host:8083", "", 0),
        ("http://[model-host:8083", _HOST, 0),
    ],
)
def test_a_gpu_address_is_hosted_when_it_is_on_the_model_hosts_own_host_name(
    gpu_endpoint: str, host: str, hosted: int
) -> None:
    assert hosted_gpu_servers(_subagents(gpu_endpoint), _swap(host=host)) == hosted


@pytest.mark.parametrize(
    ("gpu_endpoint", "evict_models", "escalation", "warned"),
    [
        (_CPU, (), False, []),
        (_OWN, (), False, []),
        (_TWO, (), False, []),
        (_TWO, _FIRST, False, []),
        (_TWO, _BOTH, True, []),
        (_ONE, (), False, [(2, 1, 0)]),
        (_THREE, (), False, [(2, 3, 0)]),
        (_ONE, _FIRST, True, [(2, 1, 1)]),
        (_TWO, (), True, [(2, 2, 0)]),
        (_TWO, _FIRST, True, [(2, 2, 1)]),
        (_TWO, (*_BOTH, "subagent-gpu-3"), True, [(2, 2, 3)]),
        (_CPU, _BOTH, True, [(2, 0, 2)]),
    ],
)
def test_the_count_the_addresses_and_the_evict_list_are_compared_at_boot(
    caplog: pytest.LogCaptureFixture,
    gpu_endpoint: str,
    evict_models: tuple[str, ...],
    warned: list[tuple[int, int, int]],
    *,
    escalation: bool,
) -> None:
    subagents = _subagents(gpu_endpoint)
    swap = _swap(evict_models, escalation=escalation)
    with caplog.at_level(logging.WARNING):
        assert warn_of_unmatched_gpu_servers(subagents, swap) is subagents
    assert _warned(caplog) == warned


def test_a_tier_of_one_server_agrees_with_one_address_and_one_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        warn_of_unmatched_gpu_servers(_subagents(_ONE, 1), _swap(_FIRST, escalation=True))
    assert _warned(caplog) == []


def test_the_brain_reads_the_model_hosts_server_count(monkeypatch: pytest.MonkeyPatch) -> None:
    assert SubagentsConfig().gpu_servers == 2
    monkeypatch.setenv("CORTEX_SUBAGENTS_GPU_SERVERS", "3")
    assert SubagentsConfig().gpu_servers == 3


async def test_run_from_env_reports_a_gpu_server_the_endpoint_setting_leaves_out(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINT", "http://tools:9000/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_CALL_TIMEOUT_S", "3000")
    monkeypatch.setenv("CORTEX_SUBAGENTS_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", _CPU)
    monkeypatch.setenv("CORTEX_SUBAGENTS_GPU_ENDPOINT", _ONE)
    monkeypatch.setenv("CORTEX_MODELHOST_ENDPOINT", _HOST)
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    with caplog.at_level(logging.WARNING), pytest.raises(ToolCallDeadlineError):
        await asyncio.wait_for(
            run_from_env(
                store_factory=lambda _url: RedisSessionStore(FakeAsyncRedis(server=server))
            ),
            timeout=10,
        )
    assert _warned(caplog) == [(2, 1, 0)]
