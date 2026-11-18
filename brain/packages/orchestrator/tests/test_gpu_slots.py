import asyncio
import logging

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from redis.asyncio import Redis

from cortex_orchestrator import ToolCallDeadlineError, run_from_env
from cortex_orchestrator.config import BrainRuntimeConfig
from cortex_orchestrator.config_subagents import SubagentsConfig
from cortex_orchestrator.gpu_slots import (
    UNPLACED_GPU_SLOTS,
    gpu_slots,
    placed_at_once,
    warn_of_unplaced_gpu_slots,
)
from cortex_session import RedisSessionStore

_CPU = "http://llama-subagent:8082"
_ONE = "http://model-host:8083"
_TWO = "http://model-host:8083,http://model-host:8084"


def _subagents(gpu_endpoint: str, gpu_parallel: int = 1) -> SubagentsConfig:
    return SubagentsConfig(
        backend="llamacpp", endpoint=_CPU, gpu_endpoint=gpu_endpoint, gpu_parallel=gpu_parallel
    )


def _runtime(soft_cap_gb: float = 14.0) -> BrainRuntimeConfig:
    return BrainRuntimeConfig(vram_soft_cap_gb=soft_cap_gb, cortex_reservation_gb=8.6)


def _warned(caplog: pytest.LogCaptureFixture) -> list[tuple[object, object]]:
    return [
        (getattr(record, "gpu_slots", None), getattr(record, "placed_at_once", None))
        for record in caplog.records
        if record.getMessage() == UNPLACED_GPU_SLOTS
    ]


@pytest.mark.parametrize(
    ("gpu_endpoint", "gpu_parallel", "slots"),
    [(_CPU, 2, 0), (_ONE, 1, 1), (_TWO, 1, 2), (_ONE, 2, 2), (_TWO, 2, 4)],
)
def test_the_gpu_slots_are_those_of_servers_the_gpu_target_names_for_itself(
    gpu_endpoint: str, gpu_parallel: int, slots: int
) -> None:
    assert gpu_slots(_subagents(gpu_endpoint, gpu_parallel)) == slots


def test_a_deployment_that_never_delegates_has_no_gpu_slot() -> None:
    assert gpu_slots(SubagentsConfig(backend="none", gpu_endpoint=_TWO)) == 0


@pytest.mark.parametrize(("soft_cap_gb", "placed"), [(12.0, 0), (14.0, 1), (16.0, 2), (24.0, 3)])
def test_the_shipped_ask_is_placed_as_often_as_the_headroom_holds_it(
    soft_cap_gb: float, placed: int
) -> None:
    assert placed_at_once(_subagents(_TWO), _runtime(soft_cap_gb), 3) == placed


@pytest.mark.parametrize(
    ("gpu_endpoint", "gpu_parallel", "soft_cap_gb", "warned"),
    [
        (_CPU, 2, 14.0, []),
        (_ONE, 1, 14.0, []),
        (_TWO, 1, 16.0, []),
        (_TWO, 1, 14.0, [(2, 1)]),
        (_ONE, 2, 14.0, [(2, 1)]),
        (_ONE, 1, 12.0, [(1, 0)]),
    ],
)
def test_a_gpu_slot_the_budget_never_places_a_spawn_on_is_reported_at_boot(
    caplog: pytest.LogCaptureFixture,
    gpu_endpoint: str,
    gpu_parallel: int,
    soft_cap_gb: float,
    warned: list[tuple[int, int]],
) -> None:
    subagents = _subagents(gpu_endpoint, gpu_parallel)
    with caplog.at_level(logging.WARNING):
        assert warn_of_unplaced_gpu_slots(subagents, _runtime(soft_cap_gb)) is subagents
    assert _warned(caplog) == warned


async def test_run_from_env_reports_a_second_gpu_server_the_shipped_budget_cannot_use(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINT", "http://tools:9000/mcp")
    monkeypatch.setenv("CORTEX_TOOLS_CALL_TIMEOUT_S", "3000")
    monkeypatch.setenv("CORTEX_SUBAGENTS_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", _CPU)
    monkeypatch.setenv("CORTEX_SUBAGENTS_GPU_ENDPOINT", _TWO)
    for name in ("CORTEX_VRAM_SOFT_CAP_GB", "CORTEX_VRAM_CORTEX_GB", "CORTEX_SUBAGENTS_VRAM_GB"):
        monkeypatch.delenv(name, raising=False)
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
    assert _warned(caplog) == [(2, 1)]
